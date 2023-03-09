#include "config.h"

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

#include <corosync/cpg.h>

#include "debug.h"
#include "virt.h"
#include "cpg.h"

#define NODE_ID_NONE ((uint32_t) -1)

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
#define TYPE_STORE_VM 2
	uint32_t type;
	uint32_t seqno;
	uint32_t target;
	uint32_t pad;
	char data[0];
};

static uint32_t seqnum = 0;
static struct msg_queue_node *pending = NULL;
static cpg_handle_t cpg_handle;
static struct cpg_name gname;

static pthread_mutex_t cpg_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cpg_cond = PTHREAD_COND_INITIALIZER;
static pthread_t cpg_thread = 0;

static pthread_mutex_t cpg_ids_mutex = PTHREAD_MUTEX_INITIALIZER;
static uint32_t my_node_id = NODE_ID_NONE;
static uint32_t high_id_from_callback = NODE_ID_NONE;

static request_callback_fn req_callback_fn;
static request_callback_fn store_callback_fn;
static confchange_callback_fn conf_leave_fn;
static confchange_callback_fn conf_join_fn;


int
cpg_get_ids(uint32_t *my_id, uint32_t *high_id)
{
	if (!my_id && !high_id)
		return -1;

	pthread_mutex_lock(&cpg_ids_mutex);
	if (my_id)
		*my_id = my_node_id;

	if (high_id)
		*high_id = high_id_from_callback;
	pthread_mutex_unlock(&cpg_ids_mutex);

	return 0;
}

static void
cpg_deliver_func(cpg_handle_t h,
		 const struct cpg_name *group_name,
		 uint32_t nodeid,
		 uint32_t pid,
		 void *msg,
		 size_t msglen)
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

		dbg_printf(2, "Seqnum %d replied; removing from list\n", n->seqno);

		pthread_cond_broadcast(&cpg_cond);
		goto out_unlock;
	}
	pthread_mutex_unlock(&cpg_mutex);

	if (m->type == TYPE_REQUEST) {
		req_callback_fn(&m->data, msglen - sizeof(*m),
				 nodeid, m->seqno);
	}
	if (m->type == TYPE_STORE_VM) {
		store_callback_fn(&m->data, msglen - sizeof(*m),
				 nodeid, m->seqno);
	}

	return;

out_unlock:
	pthread_mutex_unlock(&cpg_mutex);
}


static void
cpg_config_change(cpg_handle_t h,
		  const struct cpg_name *group_name,
		  const struct cpg_address *members, size_t memberlen,
		  const struct cpg_address *left, size_t leftlen,
		  const struct cpg_address *join, size_t joinlen)
{
	int x;
	int high;

	pthread_mutex_lock(&cpg_ids_mutex);
	high = my_node_id;

	for (x = 0; x < memberlen; x++) {
		if (members[x].nodeid > high)
			high = members[x].nodeid;
	}

	high_id_from_callback = high;
	pthread_mutex_unlock(&cpg_ids_mutex);

	if (joinlen > 0)
		conf_join_fn(join, joinlen);

	if (leftlen > 0)
		conf_leave_fn(left, leftlen);
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
	if (!m) {
		free(n);
		return -1;
	}

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
	if (ret == CS_OK)
		return 0;
	return -1;
}


int
cpg_send_vm_state(virt_state_t *vs)
{
	struct iovec iov;
	struct msg_queue_node *n;
	struct wire_msg *m;
	size_t msgsz = sizeof(*m) + sizeof(*vs);
	int ret;

	n = calloc(1, (sizeof(*n)));
	if (!n)
		return -1;

	m = calloc(1, msgsz);
	if (!m) {
		free(n);
		return -1;
	}

	n->state = STATE_MESSAGE;
	n->msg = NULL;
	n->msglen = 0;

	pthread_mutex_lock(&cpg_mutex);
	list_insert(&pending, n);
	pthread_mutex_unlock(&cpg_mutex);

	m->type = TYPE_STORE_VM;
	m->target = NODE_ID_NONE;

	memcpy(&m->data, vs, sizeof(*vs));

	iov.iov_base = m;
	iov.iov_len = msgsz;
	ret = cpg_mcast_joined(cpg_handle, CPG_TYPE_AGREED, &iov, 1);

	free(m);
	if (ret == CS_OK)
		return 0;

	return -1;
}


int
cpg_send_reply(void *data, size_t len, uint32_t nodeid, uint32_t seqno)
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
	if (ret == CS_OK)
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
			goto out;
		}
		pthread_mutex_unlock(&cpg_mutex);
	}

out:
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
	cpg_dispatch(cpg_handle, CS_DISPATCH_BLOCKING);

	return NULL;
}


int
cpg_start(	const char *name,
			request_callback_fn req_cb_fn,
			request_callback_fn store_cb_fn,
			confchange_callback_fn join_fn,
			confchange_callback_fn leave_fn)
{
	cpg_handle_t h;
	int ret;

	errno = EINVAL;

	if (!name)
		return -1;

	ret = snprintf(gname.value, sizeof(gname.value), "%s", name);
	if (ret <= 0)
		return -1;

	if (ret >= sizeof(gname.value)) {
		errno = ENAMETOOLONG;
		return -1;
	}
	gname.length = ret;

	memset(&h, 0, sizeof(h));
	if (cpg_initialize(&h, &my_callbacks) != CS_OK) {
		perror("cpg_initialize");
		return -1;
	}

	if (cpg_join(h, &gname) != CS_OK) {
		perror("cpg_join");
		return -1;
	}

	cpg_local_get(h, &my_node_id);
	dbg_printf(2, "My CPG nodeid is %d\n", my_node_id);

	pthread_mutex_lock(&cpg_mutex);
	pthread_create(&cpg_thread, NULL, cpg_dispatch_thread, NULL);

	memcpy(&cpg_handle, &h, sizeof(h));

	req_callback_fn = req_cb_fn;
	store_callback_fn = store_cb_fn;
	conf_join_fn = join_fn;
	conf_leave_fn = leave_fn;

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
