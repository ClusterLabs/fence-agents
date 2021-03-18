/*  */

#ifndef _SERVER_PLUGIN_H
#define _SERVER_PLUGIN_H

#include "config.h"

#define PLUGIN_VERSION_LISTENER ((double)0.3)
#define PLUGIN_VERSION_BACKEND  ((double)0.2)

typedef void * listener_context_t;
typedef void * backend_context_t;

/* These callbacks hand requests off to the
   appropriate backend. */
   
/* Do nothing.  Returns 1 (failure) to caller */
typedef int (*fence_null_callback)(const char *vm_name,
				   void *priv);

/* Turn the VM 'off'.  Returns 0 to caller if successful or
   nonzero if unsuccessful. */
typedef int (*fence_off_callback)(const char *vm_name, const char *src,
				  uint32_t seqno, void *priv);

/* Turn the VM 'on'.  Returns 0 to caller if successful or
   nonzero if unsuccessful. */
typedef int (*fence_on_callback)(const char *vm_name, const char *src,
				 uint32_t seqno, void *priv);

/* Reboot a VM.  Returns 0 to caller if successful or
   nonzero if unsuccessful. */
typedef int (*fence_reboot_callback)(const char *vm_name, const char *src,
				     uint32_t seqno, void *priv);

/* Get status of a VM.  Returns 0 to caller if VM is alive or
   nonzero if VM is not alive. */
typedef int (*fence_status_callback)(const char *vm_name,
				     void *priv);

/* Get status of backend.  Returns 0 to caller if backend
   is responding to requests. */
typedef int (*fence_devstatus_callback)(void *priv);


/* VMs available to fence.  Returns 0 to caller if backend
   is responding to requests and a host list can be produced */
typedef int (*hostlist_callback)(const char *vm_name, const char *uuid,
				 int state, void *arg);
typedef int (*fence_hostlist_callback)(hostlist_callback cb,
				       void *arg, void *priv);

typedef int (*backend_init_fn)(backend_context_t *c,
    			       config_object_t *config);
typedef int (*backend_cleanup_fn)(backend_context_t c);

typedef struct _fence_callbacks {
	fence_null_callback null;
	fence_off_callback off;
	fence_on_callback on;
	fence_reboot_callback reboot;
	fence_status_callback status;
	fence_devstatus_callback devstatus;
	fence_hostlist_callback hostlist;
} fence_callbacks_t;

typedef struct backend_plugin {
	const char *name;
	const char *version;
	const fence_callbacks_t *callbacks;
	backend_init_fn init;
	backend_cleanup_fn cleanup;
} backend_plugin_t;

double backend_plugin_version(void);
const backend_plugin_t * backend_plugin_info(void);

#define BACKEND_VER_SYM backend_plugin_version
#define BACKEND_INFO_SYM backend_plugin_info
#define BACKEND_VER_STR "backend_plugin_version"
#define BACKEND_INFO_STR "backend_plugin_info"

typedef int (*listener_init_fn)(listener_context_t *c,
				const fence_callbacks_t *cb,
				config_object_t *config, 
				map_object_t *map,
				void *priv);
typedef int (*listener_dispatch_fn)(listener_context_t c,
				    struct timeval *timeout);
typedef int (*listener_cleanup_fn)(listener_context_t c);


typedef struct listener_plugin {
	const char *name;
	const char *version;
	listener_init_fn init;
	listener_dispatch_fn dispatch;
	listener_cleanup_fn cleanup;
} listener_plugin_t;

double listener_plugin_version(void);
const listener_plugin_t * listener_plugin_info(void);

#define LISTENER_VER_SYM listener_plugin_version
#define LISTENER_INFO_SYM listener_plugin_info
#define LISTENER_VER_STR "listener_plugin_version"
#define LISTENER_INFO_STR "listener_plugin_info"

typedef enum {
	PLUGIN_NONE = 0,
	PLUGIN_LISTENER = 1,
	PLUGIN_BACKEND = 2
} plugin_type_t;

#ifdef __cplusplus
extern "C" {
#endif

const backend_plugin_t *plugin_find_backend(const char *name);
const listener_plugin_t *plugin_find_listener(const char *name);

void plugin_dump(void);
int plugin_load(const char *filename);
void plugin_unload(void);
int plugin_search(const char *pathname);

#ifdef __cplusplus
}
#endif
#endif
