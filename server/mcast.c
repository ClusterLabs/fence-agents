/*
  Copyright Red Hat, Inc. 2006

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
#include <simpleconfig.h>
#include <server_plugin.h>

/* Local includes */
#include "xvm.h"
#include "simple_auth.h"
#include "options.h"
#include "mcast.h"
#include "tcp.h"
#include "debug.h"

#define MCAST_MAGIC 0xaabab1b34b911a

#define VALIDATE(info) \
do {\
	if (!info || info->magic != MCAST_MAGIC)\
		return -EINVAL;\
} while(0)

typedef struct _mcast_info {
	uint64_t magic;
	void *priv;
	char key[MAX_KEY_LEN];
	mcast_options *args;
	const fence_callbacks_t *cb;
	ssize_t key_len;
	int mc_sock;
	int need_kill;
} mcast_info;


int cleanup_xml(char *xmldesc, char **ret, size_t *retsz);


static int
connect_tcp(fence_req_t *req, fence_auth_type_t auth,
	    void *key, size_t key_len)
{
	int fd = -1;
	struct sockaddr_in sin;
	struct sockaddr_in6 sin6;
	char buf[128];

	switch(req->family) {
	case PF_INET:
		memset(&sin, 0, sizeof(sin));
		memcpy(&sin.sin_addr, req->address,
		       sizeof(sin.sin_addr));
		sin.sin_family = PF_INET;
		fd = ipv4_connect(&sin.sin_addr, req->port,
				  5);
		if (fd < 0) {
			printf("Failed to call back\n");
			return -1;
		}
		break;
	case PF_INET6:
		memset(&sin6, 0, sizeof(sin));
		memcpy(&sin6.sin6_addr, req->address,
		       sizeof(sin6.sin6_addr));
		sin.sin_family = PF_INET6;
		fd = ipv6_connect(&sin6.sin6_addr, req->port,
				  5);

		memset(buf,0,sizeof(buf));
		inet_ntop(PF_INET6, &sin6.sin6_addr, buf, sizeof(buf));

		if (fd < 0) {
			printf("Failed to call back %s\n", buf);
			return -1;
		}
		break;
	default:
		printf("Family = %d\n", req->family);
		return -1;
	}

	/* Noops if auth == AUTH_NONE */
	if (tcp_response(fd, auth, key, key_len, 10) <= 0) {
		printf("Failed to respond to challenge\n");
		close(fd);
		return -1;
	}

	if (tcp_challenge(fd, auth, key, key_len, 10) <= 0) {
		printf("Remote failed challenge\n");
		close(fd);
		return -1;
	}
	return fd;
}


static int
do_fence_request_tcp(fence_req_t *req, mcast_info *info)
{
	int fd = -1;
	char response = 1;

	fd = connect_tcp(req, info->args->auth, info->key, info->key_len);
	if (fd < 0) {
		dbg_printf(2, "Could call back for fence request: %s\n", 
			strerror(errno));
		goto out;
	}

	switch(req->request) {
	case FENCE_NULL:
		response = info->cb->null((char *)req->domain, info->priv);
		break;
	case FENCE_ON:
		response = info->cb->on((char *)req->domain, info->priv);
		break;
	case FENCE_OFF:
		response = info->cb->off((char *)req->domain, info->priv);
		break;
	case FENCE_REBOOT:
		response = info->cb->reboot((char *)req->domain, info->priv);
		break;
	case FENCE_STATUS:
		response = info->cb->status((char *)req->domain, info->priv);
		break;
	case FENCE_DEVSTATUS:
		response = info->cb->devstatus(info->priv);
		break;
	}

	dbg_printf(3, "Sending response to caller...\n");
	if (write(fd, &response, 1) < 0) {
		perror("write");
	}
out:
	if (fd != -1)
		close(fd);

	return 1;
}


int
mcast_dispatch(srv_context_t c, struct timeval *timeout)
{
	mcast_info *info;
	fence_req_t data;
	fd_set rfds;
	struct sockaddr_in sin;
	int len;
	int n;
	socklen_t slen;

	info = (mcast_info *)c;
	VALIDATE(info);

	FD_ZERO(&rfds);
	FD_SET(info->mc_sock, &rfds);

#if 0
	if (reload_key) {
		char temp_key[MAX_KEY_LEN];
		int ret;

		reload_key = 0;

			ret = read_key_file(args->key_file, temp_key, sizeof(temp_key));
			if (ret < 0) {
				printf("Could not read %s; not updating key",
					args->key_file);
			} else {
				memcpy(key, temp_key, MAX_KEY_LEN);
				key_len = (size_t) ret;

				if (args->auth == AUTH_NONE)
					args->auth = AUTH_SHA256;
				if (args->hash == HASH_NONE)
					args->hash = HASH_SHA256;
			}
		}
#endif
		
	n = select((info->mc_sock)+1, &rfds, NULL, NULL, timeout);
	if (n < 0)
		return n;
	
	/* 
	 * If no requests, we're done 
	 */
	if (n == 0)
		return 0;

	slen = sizeof(sin);
	len = recvfrom(info->mc_sock, &data, sizeof(data), 0,
		       (struct sockaddr *)&sin, &slen);
		
	if (len <= 0) {
		perror("recvfrom");
		return len;
	}

	if (!verify_request(&data, info->args->hash, info->key,
			    info->key_len)) {
		printf("Key mismatch; dropping packet\n");
		return 0;
	}

#if 0
	if ((args->flags & F_USE_UUID) &&
	    !(data.flags & RF_UUID)) {
			printf("Dropping packet: Request to fence by "
			       "name while using UUIDs\n");
			continue;
		}

		if (!(args->flags & F_USE_UUID) &&
		    (data.flags & RF_UUID)) {
			printf("Dropping packet: Request to fence by "
			       "UUID while using names\n");
			continue;
		}
#endif

	printf("Request %d domain %s\n", data.request, data.domain);
		
	switch(info->args->auth) {
	case AUTH_NONE:
	case AUTH_SHA1:
	case AUTH_SHA256:
	case AUTH_SHA512:
		printf("Plain TCP request\n");
		do_fence_request_tcp(&data, info);
		break;
	default:
		printf("XXX Unhandled authentication\n");
	}

	return 0;
}


int
mcast_init(srv_context_t *c, const fence_callbacks_t *cb,
	   mcast_options *args, void *priv)
{
	mcast_info *info;
	int mc_sock;

	/* Initialize NSS; required to do hashing, as silly as that
	   sounds... */
	if (NSS_NoDB_Init(NULL) != SECSuccess) {
		printf("Could not initialize NSS\n");
		return 1;
	}

	info = malloc(sizeof(*info));
	if (!info)
		return -1;
	memset(info, 0, sizeof(*info));

	info->args = args;
	info->priv = priv;
	info->cb = cb;

	if (!info->args) {
		info->args = malloc(sizeof(*info->args));
		if (!info->args) {
			free(info);
			return -ENOMEM;
		}
		info->need_kill = 1;
		info->args->key_file = strdup(DEFAULT_KEY_FILE);
		info->args->hash = DEFAULT_HASH;
		info->args->auth = DEFAULT_AUTH;
		info->args->addr = strdup(IPV4_MCAST_DEFAULT);
		info->args->port = 1229;
		info->args->ifindex = if_nametoindex("eth0");
		info->args->family = PF_INET;
	}

	dbg_printf(6, "info->args->ifindex = %d\n", info->args->ifindex);

	if (info->args->auth != AUTH_NONE || info->args->hash != HASH_NONE) {
		info->key_len = read_key_file(info->args->key_file,
					info->key, sizeof(info->key));
		if (info->key_len < 0) {
			printf("Could not read %s; operating without "
			       "authentication\n", info->args->key_file);
			info->args->auth = AUTH_NONE;
			info->args->hash = HASH_NONE;
		}
	}

	if (info->args->family == PF_INET)
		mc_sock = ipv4_recv_sk(info->args->addr,
				       info->args->port,
				       info->args->ifindex);
	else
		mc_sock = ipv6_recv_sk(info->args->addr,
				       info->args->port,
				       info->args->ifindex);
	if (mc_sock < 0) {
		printf("Could not set up multicast listen socket\n");
		free(info);
		return 1;
	}

	info->magic = MCAST_MAGIC;
	info->mc_sock = mc_sock;
	*c = (srv_context_t)info;
	return 0;
}


int
mcast_shutdown(srv_context_t c)
{
	mcast_info *info = (mcast_info *)c;

	VALIDATE(info);
	info->magic = 0;
	if (info->need_kill) {
		free(info->args->key_file);
		free(info->args->addr);
		free(info->args);
	}
	close(info->mc_sock);
	free(info);

	return 0;
}
