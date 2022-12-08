/*
  Copyright Red Hat, Inc. 2006-2012

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

#include "config.h"

#include <unistd.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <errno.h>
#include <nss.h>
#include <sys/socket.h>
#include <netdb.h>

/* Local includes */
#include "xvm.h"
#include "simple_auth.h"
#include "options.h"
#include "mcast.h"
#include "tcp.h"
#include "tcp_listener.h"
#include "debug.h"
#include "fdops.h"
#include "list.h"
#include "simpleconfig.h"
#include "static_map.h"
#include "server_plugin.h"
#include "history.h"

#define NAME "tcp"
#define TCP_VERSION "0.2"

#define TCP_MAGIC 0xc3dff7a9

#define VALIDATE(info) \
do {\
	if (!info || info->magic != TCP_MAGIC)\
		return -EINVAL;\
} while(0)

typedef struct _tcp_options {
	char *key_file;
	char *addr;
	int family;
	unsigned int port;
	unsigned int hash;
	unsigned int auth;
	unsigned int flags;
} tcp_options;


typedef struct _tcp_info {
	uint64_t magic;
	void *priv;
	map_object_t *map;
	history_info_t *history;
	char key[MAX_KEY_LEN];
	tcp_options args;
	const fence_callbacks_t *cb;
	ssize_t key_len;
	int listen_sock;
} tcp_info;


struct tcp_hostlist_arg {
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
	fence_req_t *old = a, *current = b;

	if (old->request == current->request &&
	    old->seqno == current->seqno &&
	    !strcasecmp((const char *)old->domain,
			(const char *)current->domain)) {
		return 1;
	}
	return 0;
}

static int 
tcp_hostlist(const char *vm_name, const char *vm_uuid,
	       int state, void *priv)
{
	struct tcp_hostlist_arg *arg = (struct tcp_hostlist_arg *)priv;
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
tcp_hostlist_begin(int fd)
{
	struct timeval tv;
	char val = (char)RESP_HOSTLIST;

	tv.tv_sec = 1;
	tv.tv_usec = 0;
	return _write_retry(fd, &val, 1, &tv);
}


static int 
tcp_hostlist_end(int fd)
{
	host_state_t hinfo;
	struct timeval tv;
	int ret;

	printf("Sending terminator packet\n");

	memset(&hinfo, 0, sizeof(hinfo));

	tv.tv_sec = 1;
	tv.tv_usec = 0;
	ret = _write_retry(fd, &hinfo, sizeof(hinfo), &tv);
	if (ret == sizeof(hinfo))
		return 0;
	return 1;
}

static socklen_t
sockaddr_len(const struct sockaddr_storage *ss)
{
	if (ss->ss_family == AF_INET) {
		return sizeof(struct sockaddr_in);
	} else {
		return sizeof(struct sockaddr_in6);
	}
}

static int
do_fence_request_tcp(int fd, struct sockaddr_storage *ss, socklen_t sock_len, fence_req_t *req, tcp_info *info)
{
	char ip_addr_src[1024];
	char response = 1;
	struct tcp_hostlist_arg arg;
	int ret;

	/* Noops if auth == AUTH_NONE */
	if (sock_response(fd, info->args.auth, info->key, info->key_len, 10) <= 0) {
		printf("Failed to respond to challenge\n");
		close(fd);
		return -1;
	}

	ret = sock_challenge(fd, info->args.auth, info->key, info->key_len, 10);
	if (ret <= 0) {
		printf("Remote failed challenge\n");
		close(fd);
		return -1;
	}


	if (getnameinfo((struct sockaddr *)ss, sockaddr_len(ss),
			ip_addr_src, sizeof(ip_addr_src),
			NULL, 0,
			NI_NUMERICHOST | NI_NUMERICSERV) < 0) {
		printf("Unable to resolve!\n");
		close(fd);
		return -1;
	}

	dbg_printf(2, "Request %d seqno %d src %s target %s\n",
		   req->request, req->seqno, ip_addr_src, req->domain);

	switch(req->request) {
	case FENCE_NULL:
		response = info->cb->null((char *)req->domain, info->priv);
		break;
	case FENCE_ON:
		if (map_check(info->map, ip_addr_src,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->on((char *)req->domain, ip_addr_src,
					req->seqno, info->priv);
		break;
	case FENCE_OFF:
		if (map_check(info->map, ip_addr_src,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->off((char *)req->domain, ip_addr_src,
					 req->seqno, info->priv);
		break;
	case FENCE_REBOOT:
		if (map_check(info->map, ip_addr_src,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->reboot((char *)req->domain, ip_addr_src,
					    req->seqno, info->priv);
		break;
	case FENCE_STATUS:
		if (map_check(info->map, ip_addr_src,
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
		arg.map = info->map;
		arg.src = ip_addr_src;
		arg.fd = fd;

		tcp_hostlist_begin(arg.fd);
		response = info->cb->hostlist(tcp_hostlist, &arg,
					      info->priv);
		tcp_hostlist_end(arg.fd);
		break;
	}

	dbg_printf(3, "Sending response to caller...\n");
	if (_write_retry(fd, &response, 1, NULL) < 0) {
		perror("write");
	}

	history_record(info->history, req);

	if (fd != -1)
		close(fd);

	return 1;
}


static int
tcp_dispatch(listener_context_t c, struct timeval *timeout)
{
	tcp_info *info;
	fence_req_t data;
	fd_set rfds;
	int n;
	int client_fd;
    int ret;
	struct timeval tv;
	struct sockaddr_storage ss;
	socklen_t sock_len = sizeof(ss);

    if (timeout != NULL)
    	memcpy(&tv, timeout, sizeof(tv));
    else {
        tv.tv_sec = 1;
        tv.tv_usec = 0;
    }

	info = (tcp_info *)c;
	VALIDATE(info);

	FD_ZERO(&rfds);
	FD_SET(info->listen_sock, &rfds);

	n = select(info->listen_sock + 1, &rfds, NULL, NULL, timeout);
	if (n <= 0) {
		if (errno == EINTR || errno == EAGAIN)
			n = 0;
		else
			dbg_printf(2, "select: %s\n", strerror(errno));
		return n;
	}
	
	client_fd = accept(info->listen_sock, (struct sockaddr *)&ss, &sock_len);
	if (client_fd < 0) {
		perror("accept");
		return -1;
	}

	dbg_printf(3, "Accepted client...\n");

	ret = _read_retry(client_fd, &data, sizeof(data), &tv);
	if (ret != sizeof(data)) {
		dbg_printf(3, "Invalid request (read %d bytes)\n", ret);
		close(client_fd);
		return 0;
	}

	swab_fence_req_t(&data);

	if (!verify_request(&data, info->args.hash, info->key,
			    info->key_len)) {
		printf("Key mismatch; dropping client\n");
        close(client_fd);
		return 0;
	}

	dbg_printf(3, "Request %d seqno %d domain %s\n",
		data.request, data.seqno, data.domain);

	if (history_check(info->history, &data) == 1) {
		printf("We just did this request; dropping client\n");
        close(client_fd);
		return 0;
	}
		
	switch(info->args.auth) {
	case AUTH_NONE:
	case AUTH_SHA1:
	case AUTH_SHA256:
	case AUTH_SHA512:
		printf("Plain TCP request\n");
		do_fence_request_tcp(client_fd, &ss, sock_len, &data, info);
		break;
	default:
		printf("XXX Unhandled authentication\n");
	}

	return 0;
}


static int
tcp_config(config_object_t *config, tcp_options *args)
{
	char value[1024];
	int errors = 0;

	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value))==0)
		dset(atoi(value));

	if (sc_get(config, "listeners/tcp/@key_file",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for key_file\n", value);
		args->key_file = strdup(value);
	} else {
		args->key_file = strdup(DEFAULT_KEY_FILE);
		if (!args->key_file) {
			dbg_printf(1, "Failed to allocate memory\n");
			return -1;
		}
	}

	args->hash = DEFAULT_HASH;
	if (sc_get(config, "listeners/tcp/@hash",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for hash\n", value);
		if (!strcasecmp(value, "none")) {
			args->hash = HASH_NONE;
		} else if (!strcasecmp(value, "sha1")) {
			args->hash = HASH_SHA1;
		} else if (!strcasecmp(value, "sha256")) {
			args->hash = HASH_SHA256;
		} else if (!strcasecmp(value, "sha512")) {
			args->hash = HASH_SHA512;
		} else {
			dbg_printf(1, "Unsupported hash: %s\n", value);
			++errors;
		}
	}
	
	args->auth = DEFAULT_AUTH;
	if (sc_get(config, "listeners/tcp/@auth",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for auth\n", value);
		if (!strcasecmp(value, "none")) {
			args->hash = AUTH_NONE;
		} else if (!strcasecmp(value, "sha1")) {
			args->hash = AUTH_SHA1;
		} else if (!strcasecmp(value, "sha256")) {
			args->hash = AUTH_SHA256;
		} else if (!strcasecmp(value, "sha512")) {
			args->hash = AUTH_SHA512;
		} else {
			dbg_printf(1, "Unsupported auth: %s\n", value);
			++errors;
		}
	}
	
	args->family = PF_INET;
	if (sc_get(config, "listeners/tcp/@family",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for family\n", value);
		if (!strcasecmp(value, "ipv4")) {
			args->family = PF_INET;
		} else if (!strcasecmp(value, "ipv6")) {
			args->family = PF_INET6;
		} else {
			dbg_printf(1, "Unsupported family: %s\n", value);
			++errors;
		}
	}

	if (sc_get(config, "listeners/tcp/@address",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for address\n", value);
		args->addr = strdup(value);
	} else {
		if (args->family == PF_INET) {
			args->addr = strdup(IPV4_TCP_ADDR_DEFAULT);
		} else {
			args->addr = strdup(IPV6_TCP_ADDR_DEFAULT);
		}
	}
	if (!args->addr) {
		return -1;
	}

	args->port = DEFAULT_MCAST_PORT;
	if (sc_get(config, "listeners/tcp/@port",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for port\n", value);
		args->port = atoi(value);
		if (args->port <= 0) {
			dbg_printf(1, "Invalid port: %s\n", value);
			++errors;
		}
	}

	return errors;
}


static int
tcp_init(listener_context_t *c, const fence_callbacks_t *cb,
	   config_object_t *config, map_object_t *map, void *priv)
{
	tcp_info *info;
	int listen_sock, ret;

	/* Initialize NSS; required to do hashing, as silly as that
	   sounds... */
	if (NSS_NoDB_Init(NULL) != SECSuccess) {
		printf("Could not initialize NSS\n");
		return 1;
	}

	info = calloc(1, sizeof(*info));
	if (!info)
		return -1;

	info->priv = priv;
	info->cb = cb;
	info->map = map;

	ret = tcp_config(config, &info->args);
	if (ret < 0)
		perror("tcp_config");
	else if (ret > 0)
		printf("%d errors found during configuration\n",ret);

    if (ret != 0) {
		if (info->args.key_file)
			free(info->args.key_file);
		if (info->args.addr)
			free(info->args.addr);
		free(info);
		return -1;
	}

	if (info->args.auth != AUTH_NONE || info->args.hash != HASH_NONE) {
		info->key_len = read_key_file(info->args.key_file,
					info->key, sizeof(info->key));
		if (info->key_len < 0) {
			printf("Could not read %s; operating without "
			       "authentication\n", info->args.key_file);
			info->args.auth = AUTH_NONE;
			info->args.hash = HASH_NONE;
			info->key_len = 0;
		}
	}

	if (info->args.family == PF_INET) {
		listen_sock = ipv4_listen(info->args.addr, info->args.port, 10);
	} else {
		listen_sock = ipv6_listen(info->args.addr, info->args.port, 10);
	}

	if (listen_sock < 0) {
		printf("Could not set up listen socket\n");
		if (info->args.key_file)
			free(info->args.key_file);
		if (info->args.addr)
			free(info->args.addr);
		free(info);
		return -1;
	}

	info->magic = TCP_MAGIC;
	info->listen_sock = listen_sock;
	info->history = history_init(check_history, 10, sizeof(fence_req_t));
	*c = (listener_context_t)info;
	return 0;
}


static int
tcp_shutdown(listener_context_t c)
{
	tcp_info *info = (tcp_info *)c;

	VALIDATE(info);
	info->magic = 0;
	history_wipe(info->history);
	free(info->history);
	free(info->args.key_file);
	free(info->args.addr);
	close(info->listen_sock);
	free(info);

	return 0;
}


static listener_plugin_t tcp_plugin = {
	.name = NAME,
	.version = TCP_VERSION,
	.init = tcp_init,
	.dispatch = tcp_dispatch,
	.cleanup = tcp_shutdown,
};

double
LISTENER_VER_SYM(void)
{
	return PLUGIN_VERSION_LISTENER;
}

const listener_plugin_t *
LISTENER_INFO_SYM(void)
{
	return &tcp_plugin;
}
