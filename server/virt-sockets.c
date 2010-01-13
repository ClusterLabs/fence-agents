#include <pthread.h>
#include <unistd.h>
#include <stdio.h>
#include <list.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <stdlib.h>
#include <debug.h>

#include "virt-sockets.h"

struct socket_list {
	list_head();
	char *domain_name;
	char *socket_path;
	int socket_fd;
};

static struct socket_list *socks = NULL;
static pthread_mutex_t sock_list_mutex = PTHREAD_MUTEX_INITIALIZER;


int
domain_sock_setup(const char *domain, const char *socket_path)
{
	struct sockaddr_un *sun = NULL;
	struct socket_list *node = NULL;
	socklen_t sun_len;
	int sock = -1;

	sun_len = sizeof(*sun) + strlen(socket_path) + 1;
	sun = malloc(sun_len);
	if (!sun)
		return -1;

	memset((char *)sun, 0, sun_len);
	sun->sun_family = PF_LOCAL;
	strncpy(sun->sun_path, socket_path, sun_len - sizeof(*sun));

	sock = socket(PF_LOCAL, SOCK_STREAM, 0);
	if (sock < 0)
		goto out_fail;

	if (connect(sock, (struct sockaddr *)sun, SUN_LEN(sun)) < 0)
		goto out_fail;

	node = malloc(sizeof(*node));
	if (!node)
		goto out_fail;

	node->domain_name = strdup(domain);
	if (!node->domain_name)
		goto out_fail;

	node->socket_path = strdup(socket_path);
	if (!node->socket_path)
		goto out_fail;

	node->socket_fd = sock;

	pthread_mutex_lock(&sock_list_mutex);
	list_insert(&socks, node);
	pthread_mutex_unlock(&sock_list_mutex);

	dbg_printf(3, "Registered %s on %d\n", domain, sock);
	return 0;

out_fail:
	if (node)
		free(node->domain_name);
	if (node)
		free(node->socket_path);
	free(node);
	free(sun);
	if (sock >= 0)
		close(sock);
	return -1;
}


int
domain_sock_close(const char *domain)
{
	struct socket_list *node = NULL;
	struct socket_list *dead = NULL;
	int x;

	pthread_mutex_lock(&sock_list_mutex);
	list_for(&socks, node, x) {
		if (!strcasecmp(domain, node->domain_name)) {
			list_remove(&socks, node);
			dead = node;
			break;
		}
	}
	pthread_mutex_unlock(&sock_list_mutex);

	if (dead) {
		dbg_printf(3, "Unregistered %s, fd%d\n",
			   dead->domain_name,
			   dead->socket_fd);
		close(dead->socket_fd);
		free(dead->domain_name);
		free(dead->socket_path);
	}

	return 0;
}


int
domain_sock_fdset(fd_set *fds, int *max)
{
	struct socket_list *node = NULL;
	int x = 0, _max = -1;

	pthread_mutex_lock(&sock_list_mutex);
	list_for(&socks, node, x) {
		FD_SET(node->socket_fd, fds);
		if (node->socket_fd > _max)
			_max = node->socket_fd;
	}
	pthread_mutex_unlock(&sock_list_mutex);

	if (max)
		*max = _max;

	return x;
}


int
domain_sock_name(int fd, char *outbuf, size_t buflen)
{
	struct socket_list *node = NULL;
	int ret = 1, x = 0;

	pthread_mutex_lock(&sock_list_mutex);
	list_for(&socks, node, x) {
		if (node->socket_fd == fd) {
			snprintf(outbuf, buflen, "%s", node->domain_name);
			ret = 0;
			break;
		}
	}
	pthread_mutex_unlock(&sock_list_mutex);

	return ret;
}

