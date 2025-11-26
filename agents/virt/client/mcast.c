/*
  Copyright Red Hat, Inc. 2006-2017

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
#include <libgen.h>
#include <nss.h>

/* Local includes */
#include "xvm.h"
#include "ip_lookup.h"
#include "simple_auth.h"
#include "options.h"
#include "tcp.h"
#include "mcast.h"
#include "debug.h"
#include "fdops.h"
#include "client.h"


static int
tcp_wait_connect(int lfd, int retry_tenths)
{
	int fd;
	fd_set rfds;
	int n;
	struct timeval tv;

	dbg_printf(3, "Waiting for connection from XVM host daemon.\n");
	FD_ZERO(&rfds);
	FD_SET(lfd, &rfds);
	tv.tv_sec = retry_tenths / 10;
	tv.tv_usec = (retry_tenths % 10) * 100000;

	n = select(lfd + 1, &rfds, NULL, NULL, &tv);
	if (n == 0) {
		errno = ETIMEDOUT;
		return -1;
	} else if (n < 0) {
		return -1;
	}

	fd = accept(lfd, NULL, 0);
	if (fd < 0)
		return -1;

	return fd;
}


void
do_read_hostlist(int fd, int timeout)
{
	host_state_t hinfo;
	fd_set rfds;
	struct timeval tv;
	int ret;

	do {
		FD_ZERO(&rfds);
		FD_SET(fd, &rfds);
		tv.tv_sec = timeout;
		tv.tv_usec = 0;

		ret = _select_retry(fd+1, &rfds, NULL, NULL, &tv);
		if (ret == 0) {
			fprintf(stderr, "Timed out!\n");
			break;
		}

		ret = _read_retry(fd, &hinfo, sizeof(hinfo), &tv);
		if (ret < sizeof(hinfo)) {
			fprintf(stderr, "Bad read!\n");
			break;
		}

		if (strlen((char *)hinfo.uuid) == 0 &&
		    strlen((char *)hinfo.domain) == 0)
			break;

		printf("%-32s %s %s\n", hinfo.domain, hinfo.uuid,
		       (hinfo.state == 1) ? "on" : "off");
	} while (1);
}


static int
tcp_exchange(int fd, fence_auth_type_t auth, void *key,
	      size_t key_len, int timeout)
{
	fd_set rfds;
	struct timeval tv;
	char ret = 1;

	/* Ok, we're connected */
	dbg_printf(3, "Issuing TCP challenge\n");
	if (sock_challenge(fd, auth, key, key_len, timeout) <= 0) {
		/* Challenge failed */
		fprintf(stderr, "Invalid response to challenge\n");
		return 1;
	}

	/* Now they'll send us one, so we need to respond here */
	dbg_printf(3, "Responding to TCP challenge\n");
	if (sock_response(fd, auth, key, key_len, timeout) <= 0) {
		fprintf(stderr, "Invalid response to challenge\n");
		return 1;
	}

	dbg_printf(2, "TCP Exchange + Authentication done... \n");

	FD_ZERO(&rfds);
	FD_SET(fd, &rfds);
	tv.tv_sec = timeout;
	tv.tv_usec = 0;

	ret = 1;
	dbg_printf(3, "Waiting for return value from XVM host\n");
	if (_select_retry(fd + 1, &rfds, NULL, NULL, &tv) <= 0)
		return -1;

	/* Read return code */
	if (_read_retry(fd, &ret, 1, &tv) < 0)
		ret = 1;

	if (ret == (char)RESP_HOSTLIST) /* hostlist */ {
		do_read_hostlist(fd, timeout);
		ret = 0;
	}

	return ret;
}


static int
send_multicast_packets(ip_list_t *ipl, fence_virt_args_t *args,
		       uint32_t seqno, void *key, size_t key_len)
{
	fence_req_t freq;
	int mc_sock;
	ip_addr_t *ipa;
	struct sockaddr_in tgt4;
	struct sockaddr_in6 tgt6;
	struct sockaddr *tgt;
	socklen_t tgt_len;

	for (ipa = ipl->tqh_first; ipa; ipa = ipa->ipa_entries.tqe_next) {

		if (ipa->ipa_family != args->net.family) {
			dbg_printf(2, "Ignoring %s: wrong family\n", ipa->ipa_address);
			continue;
		}

		if (args->net.family == PF_INET) {
			mc_sock = ipv4_send_sk(ipa->ipa_address, args->net.addr,
					       args->net.port,
					       (struct sockaddr *)&tgt4,
					       sizeof(struct sockaddr_in));
			tgt = (struct sockaddr *)&tgt4;
			tgt_len = sizeof(tgt4);
		} else if (args->net.family == PF_INET6) {
			mc_sock = ipv6_send_sk(ipa->ipa_address, args->net.addr,
					       args->net.port,
					       (struct sockaddr *)&tgt6,
					       sizeof(struct sockaddr_in6));
			tgt = (struct sockaddr *)&tgt6;
			tgt_len = sizeof(tgt6);
		} else {
			dbg_printf(2, "Unsupported family %d\n", args->net.family);
			return -1;
		}

		if (mc_sock < 0)
			continue;

		/* Build our packet */
		memset(&freq, 0, sizeof(freq));
		if (args->domain && strlen((char *)args->domain)) {
			strncpy((char *)freq.domain, args->domain,
				sizeof(freq.domain) - 1);
		}
		freq.request = args->op;
		freq.hashtype = args->net.hash;
		freq.seqno = seqno;

		/* Store source address */
		if (ipa->ipa_family == PF_INET) {
			freq.addrlen = sizeof(struct in_addr);
			/* XXX Swap order for in_addr ? XXX */
			if (inet_pton(PF_INET, ipa->ipa_address, freq.address) != 1) {
				dbg_printf(2, "Unable to convert address\n");
				close(mc_sock);
				return -1;
			}
		} else if (ipa->ipa_family == PF_INET6) {
			freq.addrlen = sizeof(struct in6_addr);
			if (inet_pton(PF_INET6, ipa->ipa_address, freq.address) != 1) {
				dbg_printf(2, "Unable to convert address\n");
				close(mc_sock);
				return -1;
			}
		}

		freq.flags = 0;
		if (args->flags & F_USE_UUID)
			freq.flags |= RF_UUID;
		freq.family = ipa->ipa_family;
		freq.port = args->net.port;

		sign_request(&freq, key, key_len);

		dbg_printf(3, "Sending to %s via %s\n", args->net.addr,
		        ipa->ipa_address);

		if(sendto(mc_sock, &freq, sizeof(freq), 0,
			  (struct sockaddr *)tgt, tgt_len) < 0) {
			dbg_printf(3, "Unable to send packet to %s via %s\n",
				   args->net.addr, ipa->ipa_address);
		}

		close(mc_sock);
	}

	return 0;
}


/* TODO: Clean this up!!! */
int
mcast_fence_virt(fence_virt_args_t *args)
{
	ip_list_t ipl;
	char key[MAX_KEY_LEN];
	struct timeval tv;
	int lfd = -1, key_len = 0, fd, ret;
	int attempts = 0;
	uint32_t seqno;

	/* Initialize NSS; required to do hashing, as silly as that
	   sounds... */
	if (NSS_NoDB_Init(NULL) != SECSuccess) {
		fprintf(stderr, "Could not initialize NSS\n");
		return 1;
	}

	if (args->net.auth != AUTH_NONE || args->net.hash != HASH_NONE) {
		key_len = read_key_file(args->net.key_file, key, sizeof(key));
		if (key_len < 0) {
			fprintf(stderr, "Could not read %s; trying without "
			       "authentication\n", args->net.key_file);
			args->net.auth = AUTH_NONE;
			args->net.hash = HASH_NONE;
			key_len = 0;
		}
	}

	/* Do the real work */
	if (ip_build_list(&ipl) < 0) {
		fprintf(stderr, "Error building IP address list\n");
		return 1;
	}

	attempts = args->timeout * 10 / args->retr_time;

	listen_loop:
	do {
		switch (args->net.auth) {
			case AUTH_NONE:
			case AUTH_SHA1:
			case AUTH_SHA256:
			case AUTH_SHA512:
				if (args->net.family == PF_INET) {
					lfd = ipv4_listen(NULL, args->net.port, 10);
				} else {
					lfd = ipv6_listen(NULL, args->net.port, 10);
				}
				break;
			/*case AUTH_X509:*/
				/* XXX Setup SSL listener socket here */
			default:
				return 1;
		}

		if (lfd < 0) {
			fprintf(stderr, "Failed to listen: %s\n", strerror(errno));
			usleep(args->retr_time * 100000);
			if (--attempts > 0)
				goto listen_loop;
		}
	} while (0);

	if (lfd < 0)
		return -1;

	gettimeofday(&tv, NULL);
	seqno = (uint32_t)tv.tv_usec;

	do {
		if (send_multicast_packets(&ipl, args, seqno,
					   key, key_len)) {
			close(lfd);
			return -1;
		}

		switch (args->net.auth) {
			case AUTH_NONE:
			case AUTH_SHA1:
			case AUTH_SHA256:
			case AUTH_SHA512:
				fd = tcp_wait_connect(lfd, args->retr_time);
				if (fd < 0 && (errno == ETIMEDOUT ||
					       errno == EINTR))
					continue;
				break;
			/* case AUTH_X509:
				... = ssl_wait_connect... */
			break;
		default:
			close(lfd);
			return 1;
		}

		break;
	} while (--attempts);

	if (lfd >= 0)
		close(lfd);

	if (fd < 0) {
		if (attempts <= 0) {
			fprintf(stderr, "Timed out waiting for response\n");
			return 1;
		}
		fprintf(stderr, "Operation failed: %s\n", strerror(errno));
		return -1;
	}

	switch (args->net.auth) {
		case AUTH_NONE:
		case AUTH_SHA1:
		case AUTH_SHA256:
		case AUTH_SHA512:
			ret = tcp_exchange(fd, args->net.auth, key, key_len,
					    args->timeout);
			break;
		/* case AUTH_X509:
			return ssl_exchange(...); */
		default:
			ret = 1;
			break;
	}

	close(fd);
	return ret;
}
