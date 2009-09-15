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
#ifdef HAVE_OPENAIS_CPG_H
#include <openais/cpg.h>
#else
#ifdef HAVE_COROSYNC_CPG_H
#include <corosync/cpg.h>
#endif
#endif


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
	printf("%s (len = %d) from node %d pid %d\n)\n",
	       (char *)msg, (int)msglen, nodeid, pid);
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
	/* Don't care */
	return;
}


static cpg_callbacks_t my_callbacks = {
	.cpg_deliver_fn = cpg_deliver_func,
	.cpg_confchg_fn = cpg_config_change
};


int
cpg_send(cpg_handle_t h, void *data, size_t len)
{
	struct iovec iov;

	iov.iov_base = data;
	iov.iov_len = len;
	return cpg_mcast_joined(h, CPG_TYPE_AGREED, &iov, 1);
}


int
cpg_start(const char *name, cpg_handle_t *handle, struct cpg_name *grpname)
{
	cpg_handle_t h;
	struct cpg_name gname;
	
	errno = EINVAL;

	if (!name || !handle || !grpname)
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

	memcpy(handle, &h, sizeof(h));
	memcpy(grpname, &gname, sizeof(gname));

	return 0;
}


int
cpg_end(cpg_handle_t h, struct cpg_name *gname)
{
	cpg_leave(h, gname);
	cpg_finalize(h);
	return 0;
}


#ifdef STANDALONE
int please_quit = 0;

void
go_away(int sig)
{
	please_quit = 1;
}


int
main(int argc, char **argv)
{
	cpg_handle_t h;
	struct cpg_name gname;
	fd_set rfds;
	int fd;

	signal(SIGINT, go_away);

	if (cpg_start("lhh1", &h, &gname) < 0) {
		perror("cpg_start");
		return 1;
	}

	if (cpg_fd_get(h, &fd) != CPG_OK) {
		perror("cpg_fd_get");
		return -1;
	}

	cpg_send(h, "hi", 2);

	while (please_quit != 1) {
		FD_ZERO(&rfds);
		FD_SET(fd, &rfds);
		
		if (select(fd+1, &rfds, NULL, NULL, NULL) < 0)
			continue;

		cpg_dispatch(h, CPG_DISPATCH_ALL);
	}

	printf("going bye\n");

	cpg_leave(h, &gname);
	cpg_finalize(h);

	return 0;
}
#endif
