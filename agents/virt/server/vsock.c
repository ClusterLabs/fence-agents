/*
  Copyright Red Hat, Inc. 2017

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
#include <linux/vm_sockets.h>

/* Local includes */
#include "list.h"
#include "simpleconfig.h"
#include "static_map.h"
#include "server_plugin.h"
#include "history.h"
#include "xvm.h"
#include "simple_auth.h"
#include "options.h"
#include "mcast.h"
#include "tcp.h"
#include "tcp_listener.h"
#include "debug.h"
#include "fdops.h"

#define NAME "vsock"
#define VSOCK_VERSION "0.2"

#define VSOCK_MAGIC 0xa32d27c1e

#define VALIDATE(info) \
do {\
	if (!info || info->magic != VSOCK_MAGIC)\
		return -EINVAL;\
} while(0)

typedef struct _vsock_options {
	char *key_file;
	int cid;
	unsigned int port;
	unsigned int hash;
	unsigned int auth;
	unsigned int flags;
} vsock_options;


typedef struct _vsock_info {
	uint64_t magic;
	void *priv;
	map_object_t *map;
	history_info_t *history;
	char key[MAX_KEY_LEN];
	vsock_options args;
	const fence_callbacks_t *cb;
	ssize_t key_len;
	int listen_sock;
} vsock_info;


struct vsock_hostlist_arg {
	map_object_t *map;
	int cid;
	int fd;
};


static int get_peer_cid(int fd, uint32_t *peer_cid) {
	struct sockaddr_vm svm;
	socklen_t len;
	int ret;

	if (!peer_cid)
		return -1;

	len = sizeof(svm);
	ret = getpeername(fd, (struct sockaddr *) &svm, &len);
	if (ret < 0) {
		printf("Error getting peer CID: %s\n", strerror(errno));
		return -1;
	}

	*peer_cid = svm.svm_cid;
	return 0;
}


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
vsock_hostlist(const char *vm_name, const char *vm_uuid,
	       int state, void *priv)
{
	struct vsock_hostlist_arg *arg = (struct vsock_hostlist_arg *) priv;
	host_state_t hinfo;
	struct timeval tv;
	int ret;
	uint32_t peer_cid = 0;
	char peer_cid_str[24];

	ret = get_peer_cid(arg->fd, &peer_cid);
	if (ret < 0) {
		printf("Unable to get peer CID: %s\n", strerror(errno));
		peer_cid_str[0] = '\0';
	} else
		snprintf(peer_cid_str, sizeof(peer_cid_str), "%u", peer_cid);

	/* Noops if auth == AUTH_NONE */

	if (map_check2(arg->map, peer_cid_str, vm_uuid, vm_name) == 0) {
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
vsock_hostlist_begin(int fd)
{
	struct timeval tv;
	char val = (char) RESP_HOSTLIST;

	tv.tv_sec = 1;
	tv.tv_usec = 0;
	return _write_retry(fd, &val, 1, &tv);
}


static int 
vsock_hostlist_end(int fd)
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


static int
do_fence_request_vsock(int fd, fence_req_t *req, vsock_info *info)
{
	char response = 1;
	struct vsock_hostlist_arg arg;
	uint32_t peer_cid = 0;
	char peer_cid_str[24];
	int ret;

	ret = get_peer_cid(fd, &peer_cid);
	if (ret < 0) {
		printf("Unable to get peer CID: %s\n", strerror(errno));
		return -1;
	}

	snprintf(peer_cid_str, sizeof(peer_cid_str), "%u", peer_cid);

	/* Noops if auth == AUTH_NONE */
	if (sock_response(fd, info->args.auth, info->key, info->key_len, 10) <= 0) {
		printf("CID %u Failed to respond to challenge\n", peer_cid);
		close(fd);
		return -1;
	}

	ret = sock_challenge(fd, info->args.auth, info->key, info->key_len, 10);
	if (ret <= 0) {
		printf("Remote CID %u failed challenge\n", peer_cid);
		close(fd);
		return -1;
	}

	dbg_printf(2, "Request %d seqno %d target %s from CID %u\n", 
		   req->request, req->seqno, req->domain, peer_cid);

	switch(req->request) {
	case FENCE_NULL:
		response = info->cb->null((char *)req->domain, info->priv);
		break;
	case FENCE_ON:
		if (map_check(info->map, peer_cid_str,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->on((char *)req->domain, peer_cid_str,
					req->seqno, info->priv);
		break;
	case FENCE_OFF:
		if (map_check(info->map, peer_cid_str,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->off((char *)req->domain, peer_cid_str,
					 req->seqno, info->priv);
		break;
	case FENCE_REBOOT:
		if (map_check(info->map, peer_cid_str,
				     (const char *)req->domain) == 0) {
			response = RESP_PERM;
			break;
		}
		response = info->cb->reboot((char *)req->domain, peer_cid_str,
					    req->seqno, info->priv);
		break;
	case FENCE_STATUS:
		if (map_check(info->map, peer_cid_str,
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
		arg.fd = fd;

		vsock_hostlist_begin(arg.fd);
		response = info->cb->hostlist(vsock_hostlist, &arg, info->priv);
		vsock_hostlist_end(arg.fd);
		break;
	}

	dbg_printf(3, "Sending response to caller CID %u...\n", peer_cid);
	if (_write_retry(fd, &response, 1, NULL) < 0)
		perror("write");

	history_record(info->history, req);

	if (fd != -1)
		close(fd);

	return 1;
}


static int
vsock_dispatch(listener_context_t c, struct timeval *timeout)
{
	vsock_info *info;
	fence_req_t data;
	fd_set rfds;
	int n;
	int client_fd;
    int ret;
	struct timeval tv;

    if (timeout != NULL)
    	memcpy(&tv, timeout, sizeof(tv));
    else {
        tv.tv_sec = 1;
        tv.tv_usec = 0;
    }

	info = (vsock_info *) c;
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

	
	client_fd = accept(info->listen_sock, NULL, NULL);
	if (client_fd < 0) {
		perror("accept");
		return -1;
	}

	dbg_printf(3, "Accepted vsock client...\n");

	ret = _read_retry(client_fd, &data, sizeof(data), &tv);
	if (ret != sizeof(data)) {
		dbg_printf(3, "Invalid request (read %d bytes)\n", ret);
		close(client_fd);
		return 0;
	}

	swab_fence_req_t(&data);

	if (!verify_request(&data, info->args.hash, info->key, info->key_len)) {
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
		printf("VSOCK request\n");
		do_fence_request_vsock(client_fd, &data, info);
		break;
	default:
		printf("XXX Unhandled authentication\n");
	}

	return 0;
}


static int
vsock_config(config_object_t *config, vsock_options *args)
{
	char value[1024];
	int errors = 0;

	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value))==0)
		dset(atoi(value));

	if (sc_get(config, "listeners/vsock/@key_file",
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
	if (sc_get(config, "listeners/vsock/@hash",
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
	if (sc_get(config, "listeners/vsock/@auth",
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
	
	args->port = DEFAULT_MCAST_PORT;
	if (sc_get(config, "listeners/vsock/@port",
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
vsock_init(listener_context_t *c, const fence_callbacks_t *cb,
	   config_object_t *config, map_object_t *map, void *priv)
{
	vsock_info *info;
	int listen_sock, ret;
	struct sockaddr_vm svm;

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

	ret = vsock_config(config, &info->args);
	if (ret < 0)
		perror("vsock_config");
	else if (ret > 0)
		printf("%d errors found during vsock listener configuration\n", ret);

	if (ret != 0) {
		if (info->args.key_file)
			free(info->args.key_file);
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

	listen_sock = socket(PF_VSOCK, SOCK_STREAM, 0);
	if (listen_sock < 0)
		goto out_fail;

	memset(&svm, 0, sizeof(svm));
	svm.svm_family = AF_VSOCK;
	svm.svm_cid = VMADDR_CID_ANY;
	svm.svm_port = info->args.port;

	if (bind(listen_sock, (struct sockaddr *) &svm, sizeof(svm)) < 0)
		goto out_fail;

	if (listen(listen_sock, 1) < 0)
		goto out_fail;

	info->magic = VSOCK_MAGIC;
	info->listen_sock = listen_sock;
	info->history = history_init(check_history, 10, sizeof(fence_req_t));
	*c = (listener_context_t)info;
	return 0;

out_fail:
	printf("Could not set up listen socket: %s\n", strerror(errno));
	if (listen_sock >= 0)
		close(listen_sock);
	if (info->args.key_file)
		free(info->args.key_file);
	free(info);
	return -1;
}


static int
vsock_shutdown(listener_context_t c)
{
	vsock_info *info = (vsock_info *)c;

	VALIDATE(info);
	info->magic = 0;
	history_wipe(info->history);
	free(info->history);
	free(info->args.key_file);
	close(info->listen_sock);
	free(info);

	return 0;
}


static listener_plugin_t vsock_plugin = {
	.name = NAME,
	.version = VSOCK_VERSION,
	.init = vsock_init,
	.dispatch = vsock_dispatch,
	.cleanup = vsock_shutdown,
};

double
LISTENER_VER_SYM(void)
{
	return PLUGIN_VERSION_LISTENER;
}

const listener_plugin_t *
LISTENER_INFO_SYM(void)
{
	return &vsock_plugin;
}
