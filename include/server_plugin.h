
/*  */

#include <uuid/uuid.h>

typedef void * srv_context_t;

/* These callbacks hand requests off to the
   appropriate backend. */
   
/* Do nothing.  Returns 1 (failure) to caller */
typedef int (*fence_null_callback)(const char *vm_name,
				   void *priv);

/* Turn the VM 'off'.  Returns 0 to caller if successful or
   nonzero if unsuccessful. */
typedef int (*fence_off_callback)(const char *vm_name,
				  void *priv);

/* Turn the VM 'on'.  Returns 0 to caller if successful or
   nonzero if unsuccessful. */
typedef int (*fence_on_callback)(const char *vm_name,
				 void *priv);

/* Reboot a VM.  Returns 0 to caller if successful or
   nonzero if unsuccessful. */
typedef int (*fence_reboot_callback)(const char *vm_name,
				     void *priv);

/* Get status of a VM.  Returns 0 to caller if VM is alive or
   nonzero if VM is not alive. */
typedef int (*fence_status_callback)(const char *vm_name,
				     void *priv);

/* Get status of backend.  Returns 0 to caller if backend
   is responding to requests. */
typedef int (*fence_devstatus_callback)(void *priv);

typedef struct _fence_callbacks {
	fence_null_callback null;
	fence_off_callback off;
	fence_on_callback on;
	fence_reboot_callback reboot;
	fence_status_callback status;
	fence_devstatus_callback devstatus;
} fence_callbacks_t;


extern fence_callbacks_t libvirt_callbacks;
int libvirt_init(srv_context_t *c);
int libvirt_shutdown(srv_context_t c);


/* TODO: make these 'plugins' instead of static uses */
typedef void serial_options;
/* Directory path / hypervisor uri if using libvirt...
   .. whatever you think you need...  */

int serial_init(srv_context_t *, fence_callbacks_t *,
		serial_options *, void *priv);

/* NULL = no timeout; wait forever */
int serial_dispatch(srv_context_t, struct timeval *timeout);
int serial_shutdown(srv_context_t);

typedef struct {
	char *addr;
	char *key_file;
	int ifindex;
	int family;
	unsigned int port;
	unsigned int hash;
	unsigned int auth;
} mcast_options;

int mcast_init(srv_context_t *, fence_callbacks_t *,
	       mcast_options *, void *priv);
int mcast_dispatch(srv_context_t, struct timeval *timeout);
int mcast_shutdown(srv_context_t);

