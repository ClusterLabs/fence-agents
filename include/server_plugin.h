/*  */
#include <uuid/uuid.h>

#define PLUGIN_VERSION_FRONTEND ((double)0.1)
#define PLUGIN_VERSION_BACKEND  ((double)0.1)

#define FRONTEND_VER_SYM frontend_plugin_version
#define BACKEND_VER_SYM backend_plugin_version
#define FRONTEND_INFO_SYM frontend_plugin_info
#define BACKEND_INFO_SYM backend_plugin_info
#define FRONTEND_VER_STR "frontend_plugin_version"
#define BACKEND_VER_STR "backend_plugin_version"
#define FRONTEND_INFO_STR "frontend_plugin_info"
#define BACKEND_INFO_STR "backend_plugin_info"




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

typedef int (*fence_init_callback)(srv_context_t *c, config_object_t *config);
typedef int (*fence_cleanup_callback)(srv_context_t c);

typedef struct _fence_callbacks {
	fence_null_callback null;
	fence_off_callback off;
	fence_on_callback on;
	fence_reboot_callback reboot;
	fence_status_callback status;
	fence_devstatus_callback devstatus;
} fence_callbacks_t;

typedef struct _backend_plugin {
	const char *name;
	const char *version;
	const fence_callbacks_t *callbacks;
	fence_init_callback init;
	fence_cleanup_callback cleanup;
} plugin_t;

int plugin_register(const plugin_t *plugin);
const plugin_t *plugin_find(const char *name);
void plugin_dump(void);
#ifdef _MODULE
int plugin_load(const char *libpath);
#endif


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

int mcast_init(srv_context_t *, const fence_callbacks_t *,
	       mcast_options *, void *priv);
int mcast_dispatch(srv_context_t, struct timeval *timeout);
int mcast_shutdown(srv_context_t);

