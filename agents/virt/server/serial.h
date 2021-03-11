#ifndef __VIRT_SERIAL_H
#define __VIRT_SERIAL_H

#include <sys/select.h>

/* virt-sockets.c */
int domain_sock_setup(const char *domain, const char *socket_path);
int domain_sock_close(const char *domain);
int domain_sock_fdset(fd_set *set, int *max);

/* Find the domain name associated with a FD */
int domain_sock_name(int fd, char *outbuf, size_t buflen);
int domain_sock_cleanup(void);

/* virt-serial.c - event thread control functions */
int start_event_listener(const char *uri, const char *path, int mode, int *wake_fd);
int stop_event_listener(void);


#endif
