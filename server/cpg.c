#include <config.h>
#include <stdio.h>
#include <sys/types.h>
#include <stdint.h>
#include <malloc.h>
#include <signal.h>
#include <unistd.h>
#include <sys/select.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <sys/uio.h>
#include <list.h>
#include <pthread.h>
#ifdef HAVE_OPENAIS_CPG_H
#include <openais/cpg.h>
#else
#ifdef HAVE_COROSYNC_CPG_H
#include <corosync/cpg.h>
#endif
#endif

#include "checkpoint.h"

#define NODE_ID_NONE ((uint32_t)-1)


struct msg_queue_node {
	list_head();
	uint32_t seqno;
#define STATE_CLEAR 0
#define STATE_MESSAGE 1
	uint32_t state;
	void *msg;
	size_t msglen;
};

struct wire_msg {
#define TYPE_REQUEST 0
#define TYPE_REPLY 1
	uint32_t type;
	uint32_t seqno;
	uint32_t target;
	uint32_t pad;
	char data[0];
};

static uint32_t seqnum = 0, my_node_id = NODE_ID_NONE;
static uint32_t high_id_from_callback = NODE_ID_NONE;
static struct msg_queue_node *pending= NULL;
static cpg_handle_t cpg_handle;
static struct cpg_name gname;

static pthread_mutex_t cpg_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cpg_cond = PTHREAD_COND_INITIALIZER;
static pthread_t cpg_thread = 0;
static request_callback_fn req_callback_fn;

/* <UVT> function cpg_membership_get is (probably) buggy and returns correct
count only before cpg_mcast_joined, subsequent calls set count to 0 </UVT> */
#if 0 
int
cpg_get_ids(uint32_t *my_id, uint32_t *high_id)
{
	/* This is segfaulting for some reason */
	struct cpg_address cpg_nodes[CPG_MEMBERS_MAX];
	uint32_t high = my_node_id;
	int count = CPG_MEMBERS_MAX, x;

	if (!my_id && !high_id)
		return 0;

	if (my_id)
		*my_id = my_node_id;

	if (!high_id)
		return 0;

	memset(&cpg_nodes, 0, sizeof(cpg_nodes));

	if (cpg_membership_get(cpg_handle, &gname,
			       cpg_nodes, &count) != CPG_OK)
		return -1;

	for (x = 0; x < count; x++) {
		if (cpg_nodes[x].nodeid > high) {
			high = cpg_nodes[x].nodeid;
		}
	}

	*high_id = high;

	return 0;
}
#endif

int
cpg_get_ids(uint32_t *my_id, uint32_t *high_id)
{
	if (!my_id && !high_id)
		return 0;

	if (my_id)
		*my_id = my_node_id;

	if (!high_id)
		return 0;

	*high_id = high_id_from_callback;

	return 0;
}

void
#ifdef HAVE_OPENAIS_CPG_H
cpg_deliver_func(cpg_handle_t h,
		 struct cpg_name *group_name,
		 uint32_t nodeid,
		 uint32_t pid,
		 void *msg,
		 int msglen)
#else
cpg_deliver_func(cpg_handle_t h,
		 const struct cpg_name *group_name,
		 uint32_t nodeid,
		 uint32_t pid,
		 void *msg,
		 size_t msglen)
#endif
{
	struct msg_queue_node *n;
	struct wire_msg *m = msg;
	int x, found;

	pthread_mutex_lock(&cpg_mutex);

	if (m->type == TYPE_REPLY) {
		/* Reply to a request we sent */
		found = 0;
	
		list_for(&pending, n, x) {
			if (m->seqno != n->seqno)
				continue;
			if (m->target != my_node_id)
				continue;
			found = 1;
			break;
		}

		if (!found)
			goto out_unlock;

		/* Copy our message in to a buffer */
		n->msglen = msglen - sizeof(*m);
		if (!n->msglen) {
			/* XXX do what? */
		}
		n->msg = malloc(n->msglen);
		if (!n->msg) {
			goto out_unlock;
		}
		n->state = STATE_MESSAGE;
		memcpy(n->msg, (char *)msg + sizeof(*m), n->msglen);

		list_remove(&pending, n);
		list_insert(&pending, n);

#if 0
		printf("Seqnum %d replied; removing from list",
		       n->seqno);
#endif

		pthread_cond_broadcast(&cpg_cond);
		goto out_unlock;
	}
	pthread_mutex_unlock(&cpg_mutex);

	if (m->type == TYPE_REQUEST) {
		req_callback_fn(&m->data, msglen - sizeof(*m),
				 nodeid, m->seqno);
	}

	return;

out_unlock:
	pthread_mutex_unlock(&cpg_mutex);
}


void
#ifdef HAVE_OPENAIS_CPG_H
cpg_config_change(cpg_handle_t h,
		  struct cpg_name *group_name, 
		  struct cpg_address *members, int memberlen,
		  struct cpg_address *left, int leftlen,
		  struct cpg_address *join, int joinlen)
#else
cpg_config_change(cpg_handle_t h,
		  const struct cpg_name *group_name, 
		  const struct cpg_address *members, size_t memberlen,
		  const struct cpg_address *left, size_t leftlen,
		  const struct cpg_address *join, size_t joinlen)
#endif
{
	int x;
	int high = my_node_id;

	for (x = 0; x < memberlen; x++) {
		if (members[x].nodeid > high) {
			high = members[x].nodeid;
		}
	}

	high_id_from_callback = high;

	return;
}


static cpg_callbacks_t my_callbacks = {
	.cpg_deliver_fn = cpg_deliver_func,
	.cpg_confchg_fn = cpg_config_change
};


int
cpg_send_req(void *data, size_t len, uint32_t *seqno)
{
	struct iovec iov;
	struct msg_queue_node *n;
	struct wire_msg *m;
	size_t msgsz = sizeof(*m) + len;
	int ret;

	n = malloc(sizeof(*n));
	if (!n)
		return -1;
	m = malloc(msgsz);
	if (!m)
		return -1;

	/* only incremented on send */
	n->state = STATE_CLEAR;
	n->msg = NULL;
	n->msglen = 0;

	pthread_mutex_lock(&cpg_mutex);
	list_insert(&pending, n);
	n->seqno = ++seqnum;
	m->seqno = seqnum;
	*seqno = seqnum;
	pthread_mutex_unlock(&cpg_mutex);

	m->type = TYPE_REQUEST;		/* XXX swab? */
	m->target = NODE_ID_NONE;
	memcpy(&m->data, data, len);

	iov.iov_base = m;
	iov.iov_len = msgsz;
	ret = cpg_mcast_joined(cpg_handle, CPG_TYPE_AGREED, &iov, 1);

	free(m);
	if (ret == CPG_OK)
		return 0;
	return -1;
}


int
cpg_send_reply(void *data, size_t len, uint32_t nodeid,
	       uint32_t seqno)
{
	struct iovec iov;
	struct wire_msg *m;
	size_t msgsz = sizeof(*m) + len;
	int ret;

	m = malloc(msgsz);
	if (!m)
		return -1;

	/* only incremented on send */
	m->seqno = seqno;
	m->type = TYPE_REPLY;		/* XXX swab? */
	m->target = nodeid;
	memcpy(&m->data, data, len);

	iov.iov_base = m;
	iov.iov_len = msgsz;
	ret = cpg_mcast_joined(cpg_handle, CPG_TYPE_AGREED, &iov, 1);

	free(m);
	if (ret == CPG_OK)
		return 0;
	return -1;
}


int
cpg_wait_reply(void **data, size_t *len, uint32_t seqno)
{
	struct msg_queue_node *n;
	int x, found = 0;

	while (!found) {
		found = 0;
		pthread_mutex_lock(&cpg_mutex);
		pthread_cond_wait(&cpg_cond, &cpg_mutex);

		list_for(&pending, n, x) {
			if (n->seqno != seqno)
				continue;
			if (n->state != STATE_MESSAGE)
				continue;
			found = 1;
			break;
		}
		pthread_mutex_unlock(&cpg_mutex);
	}

	list_remove(&pending, n);
	pthread_mutex_unlock(&cpg_mutex);

	*data = n->msg;
	*len = n->msglen;
	free(n);

	return 0;
}


static void *
cpg_dispatch_thread(void *arg)
{
	cpg_dispatch(cpg_handle, CPG_DISPATCH_BLOCKING);

	return NULL;
}


int
cpg_start(const char *name, request_callback_fn func)
{
	cpg_handle_t h;
	
	errno = EINVAL;

	if (!name)
		return -1;

	gname.length = snprintf(gname.value,
				sizeof(gname.value), name);
	if (gname.length >= sizeof(gname.value)) {
		errno = ENAMETOOLONG;
		return -1;
	}

	if (gname.length <= 0)
		return -1;


	memset(&h, 0, sizeof(h));
	if (cpg_initialize(&h, &my_callbacks) != CPG_OK) {
		perror("cpg_initialize");
		return -1;
	}

	if (cpg_join(h, &gname) != CPG_OK) {
		perror("cpg_join");
		return -1;
	}


	pthread_mutex_lock(&cpg_mutex);

	cpg_local_get(h, &my_node_id);

	pthread_create(&cpg_thread, NULL, cpg_dispatch_thread, NULL);

	memcpy(&cpg_handle, &h, sizeof(h));

	req_callback_fn = func;

	pthread_mutex_unlock(&cpg_mutex);

	return 0;
}


int
cpg_stop(void)
{
	pthread_cancel(cpg_thread);
	pthread_join(cpg_thread, NULL);

	cpg_leave(cpg_handle, &gname);
	cpg_finalize(cpg_handle);

	return 0;
}


#ifdef STANDALONE
int please_quit = 0;

void
go_away(int sig)
{
	please_quit = 1;
}


void
request_callback(void *data, size_t len, uint32_t nodeid, uint32_t seqno)
{
	char *msg = data;

	printf("msg = %s\n", msg);
	
	cpg_send_reply("fail.", 7, nodeid, seqno);
}


int
main(int argc, char **argv)
{
	uint32_t seqno = 0;
	int fd;
	char *data;
	size_t len;

	signal(SIGINT, go_away);

	if (cpg_start("lhh1", request_callback) < 0) {
		perror("cpg_start");
		return 1;
	}

	cpg_send_req("hi", 2, &seqno);
	cpg_wait_reply(&data, &len, seqno);

	printf("%s\n", data);

	printf("going bye\n");

	cpg_stop();

	return 0;
}
#endif
