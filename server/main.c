#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>

/* Local includes */
#include <server_plugin.h>
#include <debug.h>

extern fence_callbacks_t libvirt_callbacks; /* should be in a header */

int
main(int argc, char **argv)
{
	const char *plugin_name = "libvirt";
	const plugin_t *p;
	srv_context_t mcast_context;
	srv_context_t libvirt_context; /*XXX these should be differently
					 named context types */

	dset(99);

#ifdef _MODULE
	if (plugin_load("./libvirt.so") < 0) {
		printf("Doom\n");
	}
#endif
	plugin_dump();

	p = plugin_find(plugin_name);
	if (!p) {
		printf("Could not find plugin \"%s\n", plugin_name);
	}

	if (p->init(&libvirt_context) < 0) {
		printf("%s failed to initialize\n", plugin_name);
		return 1;
	}

	/* only client we have now is mcast (fence_xvm behavior) */
	if (mcast_init(&mcast_context, p->callbacks, NULL,
		       libvirt_context) < 0) {
		printf("Failed initialization!\n");
		return 1;
	}

	while (mcast_dispatch(mcast_context, NULL) >= 0);

	mcast_shutdown(mcast_context);
	p->cleanup(libvirt_context);

	return 0;
}
