#ifndef _CLIENT_H
#define _CLIENT_H

int tcp_fence_virt(fence_virt_args_t *args);
int serial_fence_virt(fence_virt_args_t *args);
int mcast_fence_virt(fence_virt_args_t *args);
int vsock_fence_virt(fence_virt_args_t *args);
void do_read_hostlist(int fd, int timeout);
#endif
