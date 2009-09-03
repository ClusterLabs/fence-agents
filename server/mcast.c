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
#include <list.h>
#include <simpleconfig.h>
#include <server_plugin.h>

/* Local includes */
#include "xvm.h"
#include "simple_auth.h"
#include "options.h"
#include "mcast.h"
#include "tcp.h"
#include "debug.h"

#define NAME "multicast"
#define VERSION "1.0"

#define MCAST_MAGIC 0xaabab1b34b911a

#define VALIDATE(info) \
do {\
	if (!info || info->magic != MCAST_MAGIC)\
		return -EINVAL;\
} while(0)

typedef struct _mcast_options {
	char *addr;
	char *key_file;
	int ifindex;
	int family;
	unsigned int port;
	unsigned int hash;
	unsigned int auth;
	unsigned int flags;
} mcast_options;


typedef struct _history_node {
	list_head();
	fence_req_t req;
	time_t when;
} history_node;


typedef struct _mcast_info {
	uint64_t magic;
	void *priv;
	history_node *history;
	char key[MAX_KEY_LEN];
	mcast_options args;
	const fence_callbacks_t *cb;
	ssize_t key_len;
	int mc_sock;
	int need_kill;
} mcast_info;


/*
 * See if we fenced this node recently (successfully)
 * If so, ignore the request for a few seconds.
 *
 * We purge our history when the entries time out.
 */
static int
check_history(history_node **list, fence_req_t *req)
{
	history_node *entry = NULL;
	time_t now;
	int x;

	now = time(NULL);

loop_again:
	list_for(list, entry, x) {
		if (entry->when < (now - 10)) {
			list_remove(list, entry);
			free(entry);
			goto loop_again;
		}

		if (entry->req.request == req->request &&
		    !strcasecmp((const char *)entry->req.domain,
				(const char *)req->domain)) {
			return 1;
		}
	}
	return 0;
}


static int
record_history(history_node **list, fence_req_t *req)
{
	history_node *entry = NULL;

	entry = malloc(sizeof(*entry));
	if (!entry)
		return -1;	/* non-fatal */

	memset(entry, 0, sizeof(*entry));
	memcpy(&entry->req, req, sizeof(*req));
	entry->when = time(NULL);
	list_insert(list, entry);
	return 0;
}


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

	fd = connect_tcp(req, info->args.auth, info->key, info->key_len);
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

	/* XVM shotguns multicast packets, so we want to avoid 
	 * acting on the same request multiple times if the first
	 * attempt was successful.
	 */
	record_history(&info->history, req);
out:
	if (fd != -1)
		close(fd);

	return 1;
}


static int
mcast_dispatch(listener_context_t c, struct timeval *timeout)
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

	if (!verify_request(&data, info->args.hash, info->key,
			    info->key_len)) {
		printf("Key mismatch; dropping packet\n");
		return 0;
	}

	if ((info->args.flags & F_USE_UUID) &&
	    !(data.flags & RF_UUID)) {
		printf("Dropping packet: Request to fence by "
		       "name while using UUIDs\n");
		return 0;
	}

	if (!(info->args.flags & F_USE_UUID) &&
	    (data.flags & RF_UUID)) {
		printf("Dropping packet: Request to fence by "
		       "UUID while using names\n");
		return 0;
	}

	printf("Request %d domain %s\n", data.request, data.domain);

	if (check_history(&info->history, &data) == 1) {
		printf("We just did this request; dropping packet\n");
		return 0;
	}
		
	switch(info->args.auth) {
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


static int
mcast_config(config_object_t *config, mcast_options *args)
{
	char value[1024];
	int errors = 0;

	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value))==0)
		dset(atoi(value));

	if (sc_get(config, "listeners/multicast/@key_file",
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

	if (sc_get(config, "fence_virtd/@name_mode",
		   value, sizeof(value)-1) == 0) {
		/*
		 * This is just an optimization.  If an administrator
		 * configured something at the top level, we can use it
		 * to explicitly ignore UUID vs. name
		 */
		dbg_printf(1, "Got %s for name_mode\n", value);
		if (!strcasecmp(value, "uuid")) {
			args->flags |= RF_UUID;
		} else if (!strcasecmp(value, "name")) {
			args->flags &= ~RF_UUID;
		} else {
			dbg_printf(1, "Unsupported name_mode: %s\n", value);
			++errors;
		}
	}

	args->hash = DEFAULT_HASH;
	if (sc_get(config, "listeners/multicast/@hash",
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
	if (sc_get(config, "listeners/multicast/@auth",
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
	if (sc_get(config, "listeners/multicast/@family",
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

	if (sc_get(config, "listeners/multicast/@address",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for address\n", value);
		args->addr = strdup(value);
	} else {
		if (args->family == PF_INET) {
			args->addr = strdup(IPV4_MCAST_DEFAULT);
		} else {
			args->addr = strdup(IPV6_MCAST_DEFAULT);
		}
	}
	if (!args->addr) {
		return -1;
	}

	args->port = DEFAULT_MCAST_PORT;
	if (sc_get(config, "listeners/multicast/@port",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for port\n", value);
		args->port = atoi(value);
		if (args->port <= 0) {
			dbg_printf(1, "Invalid port: %s\n", value);
			++errors;
		}
	}

	args->ifindex = 0;
	if (sc_get(config, "listeners/multicast/@interface",
		   value, sizeof(value)-1) == 0) {
		dbg_printf(1, "Got %s for interface\n", value);
		args->ifindex = if_nametoindex(value);
		if (args->ifindex < 0) {
			dbg_printf(1, "Invalid interface: %s\n", value);
			++errors;
		}
	}

	return errors;
}


static int
mcast_init(listener_context_t *c, const fence_callbacks_t *cb,
	   config_object_t *config, void *priv)
{
	mcast_info *info;
	int mc_sock, ret;

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

	info->priv = priv;
	info->cb = cb;

	ret = mcast_config(config, &info->args);
	if (ret < 0) {
		perror("mcast_config");
		return -1;
	} else if (ret > 0) {
		printf("%d errors found during configuration\n",ret);
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
		}
	}

	if (info->args.family == PF_INET)
		mc_sock = ipv4_recv_sk(info->args.addr,
				       info->args.port,
				       info->args.ifindex);
	else
		mc_sock = ipv6_recv_sk(info->args.addr,
				       info->args.port,
				       info->args.ifindex);
	if (mc_sock < 0) {
		printf("Could not set up multicast listen socket\n");
		free(info);
		return 1;
	}

	info->magic = MCAST_MAGIC;
	info->mc_sock = mc_sock;
	*c = (listener_context_t)info;
	return 0;
}


static int
mcast_shutdown(listener_context_t c)
{
	mcast_info *info = (mcast_info *)c;

	VALIDATE(info);
	info->magic = 0;
	free(info->args.key_file);
	free(info->args.addr);
	close(info->mc_sock);
	free(info);

	return 0;
}


static listener_plugin_t mcast_plugin = {
	.name = NAME,
	.version = VERSION,
	.init = mcast_init,
	.dispatch = mcast_dispatch,
	.cleanup = mcast_shutdown,
};


#ifdef _MODULE
double
LISTENER_VER_SYM(void)
{
	return PLUGIN_VERSION_LISTENER;
}

const listener_plugin_t *
LISTENER_INFO_SYM(void)
{
	return &mcast_plugin;
}
#else
static void __attribute__((constructor))
mcast_register_plugin(void)
{
	plugin_reg_listener(&mcast_plugin);
}
#endif

