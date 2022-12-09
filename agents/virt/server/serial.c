/*
  Copyright Red Hat, Inc. 2010

  This program is free software; you can redistribute it and/or modify it
  under the terms of the GNU General Public License as published by the
  Free Software Foundation; either version 2, or (at your option) any
  later version.

  This program is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; see the file COPYING.  If not, write to the
  Free Software Foundation, Inc.,  675 Mass Ave, Cambridge, 
  MA 02139, USA.
*/
/*
 * Author: Lon Hohberger <lhh at redhat.com>
 */

#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/un.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/ioctl.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <netinet/in.h>
#include <netdb.h>
#include <sys/time.h>
#include <fcntl.h>
#include <errno.h>
#include <pthread.h>
#include <nss.h>
#include <libgen.h>

/* Local includes */
#include "debug.h"
#include "fdops.h"
#include "serial.h"
#include "list.h"
#include "simpleconfig.h"
#include "static_map.h"
#include "server_plugin.h"
#include "history.h"
#include "xvm.h"

#define NAME "serial"
#define SERIAL_VERSION "0.5"

#define SERIAL_PLUG_MAGIC 0x1227a000

#define VALIDATE(info) \
do {\
	if (!info || info->magic != SERIAL_PLUG_MAGIC)\
		return -EINVAL;\
} while(0)


typedef struct _serial_info {
	uint64_t magic;
	const fence_callbacks_t *cb;
	void *priv;
	char *uri;
	char *path;
	history_info_t *history;
	map_object_t *maps;
	int mode;
	int wake_fd;
} serial_info;


struct serial_hostlist_arg {
	map_object_t *map;
	const char *src;
	int fd;
};


/*
 * See if we fenced this node recently (successfully)
 * If so, ignore the request for a few seconds.
 *
 * We purge our history when the entries time out.
 */
static int
check_history(void *a, void *b) {
	serial_req_t *old = a, *current = b;

	if (old->request == current->request &&
	    old->seqno == current->seqno &&
	    !strcasecmp((const char *)old->domain,
			(const char *)current->domain)) {
		return 1;
	}
	return 0;
}


static int 
serial_hostlist(const char *vm_name, const char *vm_uuid,
	 	int state, void *priv)
{
	struct serial_hostlist_arg *arg = (struct serial_hostlist_arg *)priv;
	host_state_t hinfo;
	struct timeval tv;
	int ret;

	if (map_check2(arg->map, arg->src, vm_uuid, vm_name) == 0) {
		/* if we don't have access to fence this VM,
		 * we should not see it in a hostlist either */
		return 0;
	}

	strncpy((char *)hinfo.domain, vm_name, sizeof(hinfo.domain) - 1);
	strncpy((char *)hinfo.uuid, vm_uuid, sizeof(hinfo.uuid) - 1);
	hinfo.state = state;

	tv.tv_sec = 1;
	tv.tv_usec = 0;

	ret = _write_retry(arg->fd, &hinfo, sizeof(hinfo), &tv);
	if (ret == sizeof(hinfo))
		return 0;
	return 1;
}


static int
serial_hostlist_begin(int fd)
{
	struct timeval tv;
	serial_resp_t resp;

	resp.magic = SERIAL_MAGIC;
	resp.response = RESP_HOSTLIST;

	tv.tv_sec = 1;
	tv.tv_usec = 0;
	return _write_retry(fd, &resp, sizeof(resp), &tv);
}


static int 
serial_hostlist_end(int fd)
{
	host_state_t hinfo;
	struct timeval tv;
	int ret;

	//printf("Sending terminator packet\n");

	memset(&hinfo, 0, sizeof(hinfo));

	tv.tv_sec = 1;
	tv.tv_usec = 0;
	ret = _write_retry(fd, &hinfo, sizeof(hinfo), &tv);
	if (ret == sizeof(hinfo))
		return 0;
	return 1;
}


static int
do_fence_request(int fd, const char *src, serial_req_t *req, serial_info *info)
{
	char response = RESP_FAIL;
	struct serial_hostlist_arg arg;
	serial_resp_t resp;

	arg.fd = fd;

	switch(req->request) {
	case FENCE_NULL:
		response = info->cb->null((char *)req->domain, info->priv);
		break;
	case FENCE_ON:
		if (map_check(info->maps, src,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->on((char *)req->domain, src,
				       	req->seqno, info->priv);
		break;
	case FENCE_OFF:
		if (map_check(info->maps, src,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->off((char *)req->domain, src,
					 req->seqno, info->priv);
		break;
	case FENCE_REBOOT:
		if (map_check(info->maps, src,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->reboot((char *)req->domain, src,
					    req->seqno, info->priv);
		break;
	case FENCE_STATUS:
		if (map_check(info->maps, src,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->status((char *)req->domain, info->priv);
		break;
	case FENCE_DEVSTATUS:
		response = info->cb->devstatus(info->priv);
		break;
	case FENCE_HOSTLIST:
		arg.map = info->maps;
		arg.src = src;
		arg.fd = fd;

		serial_hostlist_begin(arg.fd);
		response = info->cb->hostlist(serial_hostlist, &arg,
					      info->priv);
		serial_hostlist_end(arg.fd);
		break;
	}

	resp.magic = SERIAL_MAGIC;
	resp.response = response;
	swab_serial_resp_t(&resp);

	dbg_printf(3, "Sending response to caller...\n");
	if (_write_retry(fd, &resp, sizeof(resp), NULL) < 0)
		perror("write");

	/* XVM shotguns multicast packets, so we want to avoid 
	 * acting on the same request multiple times if the first
	 * attempt was successful.
	 */
	history_record(info->history, req);

	return 1;
}


static int
serial_dispatch(listener_context_t c, struct timeval *timeout)
{
	char src_domain[MAX_DOMAINNAME_LENGTH];
	serial_info *info;
	serial_req_t data;
	fd_set rfds;
	struct timeval tv;
	int max;
	int n, x, ret;

	info = (serial_info *)c;
	VALIDATE(info);

	FD_ZERO(&rfds);
	domain_sock_fdset(&rfds, &max);
	FD_SET(info->wake_fd, &rfds);
	if (info->wake_fd > max)
		max = info->wake_fd;

	n = select(max+1, &rfds, NULL, NULL, timeout);
	if (n < 0) {
		if (errno == EINTR || errno == EAGAIN)
			n = 0;
		else
			dbg_printf(2, "select: %s\n", strerror(errno));
		return n;
	}

	/*
	 * See if the goal was just to be woken up in order to refill our
	 * file descriptor set.  For example, if multiple domains were 
	 * created simultaneously, we would have to refill our fd_set
	 */
	if (FD_ISSET(info->wake_fd, &rfds)) {
		tv.tv_sec = 0;
		tv.tv_usec = 10000;
		_read_retry(info->wake_fd, &c, 1, &tv);
		return 0;
	}

	/* 
	 * If no requests, we're done 
	 */
	if (n == 0)
		return 0;

	/* find & read request */
	for (x = 0; x <= max; x++) {
		if (FD_ISSET(x, &rfds)) {
			tv.tv_sec = 1;
			tv.tv_usec = 0;

			ret = _read_retry(x, &data, sizeof(data), &tv);

			if (ret != sizeof(data)) {
				if (--n > 0)
					continue;
				else
					return 0;
			} else {
				swab_serial_req_t(&data);
				break;
			}
		}
	}

	src_domain[0] = 0;
	domain_sock_name(x, src_domain, sizeof(src_domain));

	dbg_printf(2, "Sock %d Request %d seqno %d src %s target %s\n", x,
	       data.request, data.seqno, src_domain, data.domain);

	if (history_check(info->history, &data) == 1) {
		dbg_printf(3, "We just did this request; dropping packet\n");
		return 0;
	}

	do_fence_request(x, src_domain[0] == 0 ? NULL : src_domain,
			 &data, info);
		
	return 0;
}


static int
serial_config(config_object_t *config, serial_info *args)
{
	char value[1024];
	int errors = 0;

	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value))==0)
		dset(atoi(value));

	if (sc_get(config, "listeners/serial/@uri",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for uri\n", value);
		args->uri = strdup(value);
	} 

	if (sc_get(config, "listeners/serial/@path",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for path\n", value);
		args->path = strdup(value);
	} 

	if (sc_get(config, "listeners/serial/@mode",
		   value, sizeof(value)-1) == 0) {
		if (!strcasecmp(value, "vmchannel")) {
			args->mode = 1;
		} else if (!strcasecmp(value, "serial")) {
			args->mode = 0;
		} else {
			args->mode = atoi(value);
			if (args->mode < 0)
				args->mode = 0;
		}

		dbg_printf(1, "Got %s for mode\n",
			   args->mode?"VMChannel":"serial");

	} 

	return errors;
}


static int
serial_init(listener_context_t *c, const fence_callbacks_t *cb,
	   config_object_t *config, map_object_t *map, void *priv)
{
	serial_info *info;
	int ret;

	info = malloc(sizeof(*info));
	if (!info)
		return -1;
	memset(info, 0, sizeof(*info));

	info->priv = priv;
	info->cb = cb;

	ret = serial_config(config, info);
	if (ret < 0) {
		perror("serial_config");
		return -1;
	} else if (ret > 0) {
		printf("%d errors found during configuration\n",ret);
		return -1;
	}

	info->maps = map;

	info->magic = SERIAL_PLUG_MAGIC;
	info->history = history_init(check_history, 10, sizeof(fence_req_t));
	*c = (listener_context_t)info;
	start_event_listener(info->uri, info->path, info->mode, &info->wake_fd);
	sleep(1);

	return 0;
}


static int
serial_shutdown(listener_context_t c)
{
	serial_info *info = (serial_info *)c;
	
	dbg_printf(3, "Shutting down serial\n");

	VALIDATE(info);
	info->magic = 0;
	stop_event_listener();
	domain_sock_cleanup();
	history_wipe(info->history);
	free(info->history);
	free(info->uri);
	free(info->path);
	free(info);

	return 0;
}


static listener_plugin_t serial_plugin = {
	.name = NAME,
	.version = SERIAL_VERSION,
	.init = serial_init,
	.dispatch = serial_dispatch,
	.cleanup = serial_shutdown,
};

double
LISTENER_VER_SYM(void)
{
	return PLUGIN_VERSION_LISTENER;
}

const listener_plugin_t *
LISTENER_INFO_SYM(void)
{
	return &serial_plugin;
}
