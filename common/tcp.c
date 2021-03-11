/*
  Copyright Red Hat, Inc. 2002-2004, 2006
  Copyright Mission Critical Linux, 2000

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
/** @file
 *
 * @author Lon H. Hohberger <lhh at redhat.com>
 * @author Jeff Moyer <jmoyer at redhat.com>
 */

#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <netdb.h>

#include "debug.h"

static int connect_nb(int fd, struct sockaddr *dest, socklen_t len, int timeout);
static int get_addr(const char *hostname, int family, struct sockaddr_storage *addr);

/**
  Set close-on-exec bit option for a socket.

   @param fd		Socket to set CLOEXEC flag
   @return		0 on success, -1 on failure
   @see			fcntl
 */
static int 
set_cloexec(int fd)
{
	int flags = fcntl(fd, F_GETFD, 0);
	flags |= FD_CLOEXEC;
	return fcntl(fd, F_SETFD, flags);
}


/**
  Bind to a port on the local IPv6 stack

  @param addr_str	Address to listen on, NULL for inaddr6_any
  @param port		Port to bind to
  @param backlog	same as backlog for listen(2)
  @return		0 on success, -1 on failure
  @see			ipv4_bind
 */
int
ipv6_listen(const char *addr_str, uint16_t port, int backlog)
{
	struct sockaddr_in6 _sin6;
	int fd, ret;

	dbg_printf(4, "%s: Setting up ipv6 listen socket for %s:%d\n",
		__FUNCTION__, addr_str, port);

	memset(&_sin6, 0, sizeof(_sin6));
	_sin6.sin6_family = PF_INET6;
	_sin6.sin6_port = htons(port);
	_sin6.sin6_flowinfo = 0;

	if (addr_str == NULL) {
		_sin6.sin6_addr = in6addr_any;
	} else {
		struct sockaddr_storage ss;

		if (get_addr(addr_str, AF_INET6, &ss) == -1) {
			dbg_printf(4, "%s: Can't get addr for %s\n",
				__FUNCTION__, addr_str);
			return -1;
		}

		memcpy(&_sin6.sin6_addr,
			&((struct sockaddr_in6 *)&ss)->sin6_addr, sizeof(_sin6.sin6_addr));
	}

	fd = socket(PF_INET6, SOCK_STREAM, 0);
	if (fd < 0)
		return -1;

	ret = 1;
	setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, (void *)&ret, sizeof (ret));

	ret = set_cloexec(fd);
	if (ret < 0) {
		close(fd);
		return -1;
	}

	ret = bind(fd, (struct sockaddr *)&_sin6, sizeof(_sin6));
	if (ret < 0) {
		close(fd);
		return -1;
	}

	if (listen(fd, backlog) < 0){
		close(fd);
		return -1;
	}

	dbg_printf(4, "%s: Success; fd = %d\n", __FUNCTION__, fd);
	return fd;
}


/**
  Bind to a port on the local IPv4 stack

  @param addr_str	Address to listen on, NULL for inaddr_any
  @param port		Port to bind to
  @param backlog	same as backlog for listen(2)
  @return		0 on success, -1 on failure
  @see			ipv6_bind
 */
int
ipv4_listen(const char *addr_str, uint16_t port, int backlog)
{
	struct sockaddr_in _sin;
	int fd, ret;

	dbg_printf(4, "%s: Setting up ipv4 listen socket for %s:%d\n",
		__FUNCTION__, addr_str, port);

	_sin.sin_family = PF_INET;
	_sin.sin_port = htons(port);

	if (addr_str == NULL) {
		_sin.sin_addr.s_addr = htonl(INADDR_ANY);
	} else {
		struct sockaddr_storage ss;

		if (get_addr(addr_str, AF_INET, &ss) == -1) {
			dbg_printf(4, "%s: Can't get addr for %s\n",
				__FUNCTION__, addr_str);
			return -1;
		}

		memcpy(&_sin.sin_addr,
			&((struct sockaddr_in *)&ss)->sin_addr, sizeof(_sin.sin_addr));
	}

	fd = socket(PF_INET, SOCK_STREAM, 0);
	if (fd < 0)
		return -1;

	ret = 1;
	setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, (void *)&ret, sizeof (ret));
	
	ret = set_cloexec(fd);
	if (ret < 0) {
		close(fd);
		return -1;
	}

	ret = bind(fd, (struct sockaddr *)&_sin, sizeof(_sin));
	if (ret < 0) {
		close(fd);
		return -1;
	}

	if (listen(fd, backlog) < 0){
		close(fd);
		return -1;
	}

	dbg_printf(4, "%s: Success; fd = %d\n", __FUNCTION__, fd);
	return fd;
}



/**
  Connect via ipv6 socket to a given IP address and port.

  @param in6_addr	IPv6 address to connect to
  @param port		Port to connect to
  @param timeout	Timeout, in seconds, to wait for a completed
  			connection
  @return 		0 on success, -1 on failure
  @see			connect_nb, ipv4_connect
 */
int
ipv6_connect(struct in6_addr *in6_addr, uint16_t port, int timeout)
{
	struct sockaddr_in6 _sin6;
	int fd, ret;

	dbg_printf(4, "%s: Connecting to client\n", __FUNCTION__);
	fd = socket(PF_INET6, SOCK_STREAM, 0);
	if (fd < 0)
		return -1;

	memset(&_sin6, 0, sizeof(_sin6));
	_sin6.sin6_family = PF_INET6;
	_sin6.sin6_port = htons(port);
	_sin6.sin6_flowinfo = 0;
	memcpy(&_sin6.sin6_addr, in6_addr, sizeof(_sin6.sin6_addr));

	ret = connect_nb(fd, (struct sockaddr *)&_sin6, sizeof(_sin6), timeout);
	if (ret < 0) {
		close(fd);
		return -1;
	}
	dbg_printf(4, "%s: Success; fd = %d\n", __FUNCTION__, fd);
	return fd;
}


/**
  Connect via ipv4 socket to a given IP address and port.

  @param in_addr	IPv4 address to connect to
  @param port		Port to connect to
  @param timeout	Timeout, in seconds, to wait for a completed
  			connection
  @return 		0 on success, -1 on failure
  @see			connect_nb, ipv6_connect
 */
int
ipv4_connect(struct in_addr *in_addr, uint16_t port, int timeout)
{
	struct sockaddr_in _sin;
	int fd, ret;

	dbg_printf(4, "%s: Connecting to client\n", __FUNCTION__);
	fd = socket(PF_INET, SOCK_STREAM, 0);
	if (fd < 0)
		return -1;

	_sin.sin_family = PF_INET;
	_sin.sin_port = htons(port);
	memcpy(&_sin.sin_addr, in_addr, sizeof(_sin.sin_addr));

	ret = connect_nb(fd, (struct sockaddr *)&_sin, sizeof(_sin), timeout);
	if (ret < 0) {
		close(fd);
		return -1;
	}

	dbg_printf(4, "%s: Success; fd = %d\n", __FUNCTION__, fd);
	return fd;
}


/**
  Connect in a non-blocking fashion to the designated address.

  @param fd		File descriptor to connect
  @param dest		sockaddr (ipv4 or ipv6) to connect to.
  @param len		Length of dest
  @param timeout	Timeout, in seconds, to wait for a completed
  			connection.
  @return		0 on success, -1 on failure.
 */
static int
connect_nb(int fd, struct sockaddr *dest, socklen_t len, int timeout)
{
	int ret, flags = 1, err;
	unsigned l;
	fd_set rfds, wfds;
	struct timeval tv;

	/*
	 * Use TCP Keepalive
	 */
	if (setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, (void *)&flags,
		       sizeof(flags))<0)
		return -1;
			
	/*
	   Set up non-blocking connect
	 */
	flags = fcntl(fd, F_GETFL, 0);
	fcntl(fd, F_SETFL, flags | O_NONBLOCK);

	ret = connect(fd, dest, len);

	if ((ret < 0) && (errno != EINPROGRESS))
		return -1;

	if (ret != 0) {
		FD_ZERO(&rfds);
		FD_SET(fd, &rfds);
		FD_ZERO(&wfds);
		FD_SET(fd, &wfds);

		tv.tv_sec = timeout;
		tv.tv_usec = 0;
		
		if (select(fd + 1, &rfds, &wfds, NULL, &tv) == 0) {
			errno = ETIMEDOUT;
			return -1;
		}
		/* XXX check for -1 from select */

		if (FD_ISSET(fd, &rfds) || FD_ISSET(fd, &wfds)) {
			l = sizeof(err);
			if (getsockopt(fd, SOL_SOCKET, SO_ERROR,
				       (void *)&err, &l) < 0) {
				close(fd);
				return -1;
			}

			if (err != 0) {
				close(fd);
				errno = err;
				return -1;
			}

			fcntl(fd, F_SETFL, flags);
			return 0;
		}
	}

	errno = EIO;
	return -1;
}

static int
get_addr(const char *hostname, int family, struct sockaddr_storage *addr)
{
	struct addrinfo *res;
	size_t len;
	struct addrinfo ai;

	memset(&ai, 0, sizeof(ai));
	ai.ai_family = family;

	if (getaddrinfo(hostname, NULL, &ai, &res) != 0)
		return -1;

	switch (res->ai_addr->sa_family) {
		case AF_INET:
			len = sizeof(struct sockaddr_in);
			break;
		case AF_INET6:
			len = sizeof(struct sockaddr_in6);
			break;
		default:
			goto out_fail;
	}

	if (len < (size_t) res->ai_addrlen)
		goto out_fail;

	memcpy(addr, res->ai_addr, res->ai_addrlen);
	freeaddrinfo(res);

	return 0;

out_fail:
	freeaddrinfo(res);
	return -1;
}
