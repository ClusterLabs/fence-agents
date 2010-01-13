#ifndef _VIRT_SOCKETS_H
#define _VIRT_SOCKETS_H

#include <sys/select.h>

int domain_sock_setup(const char *domain, const char *socket_path);
int domain_sock_close(const char *domain);
int domain_sock_fdset(fd_set *set, int *max);

#endif
