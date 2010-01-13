#ifndef _VIRT_SERIAL_H_
#define _VIRT_SERIAL_H

#include <sys/select.h>

/* virt-sockets.c */
int domain_sock_setup(const char *domain, const char *socket_path);
int domain_sock_close(const char *domain);
int domain_sock_fdset(fd_set *set, int *max);

/* Find the domain name associated with a FD */
int domain_sock_name(int fd, char *outbuf, size_t buflen);
int domain_sock_cleanup(void);

/* static_map.c - permissions map functions */
void static_map_cleanup(void *info);
int static_map_check(void *info, const char *value1, const char *value2);
int static_map_init(config_object_t *config, void **perm_info);

/* virt-serial.c - event thread control functions */
int start_event_listener(const char *uri);
int stop_event_listener(void);


#endif
