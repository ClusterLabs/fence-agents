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
	srv_context_t mcast_context;
	srv_context_t libvirt_context; /*XXX these should be differently
					 named context types */

	dset(99);

	/* Only backend we have right now is basic libvirt */

	if (libvirt_init(&libvirt_context) < 0) {
		printf("Libvirt failed to initialize\n");
		return 1;
	}

	/* only client we have now is mcast (fence_xvm behavior) */
	if (mcast_init(&mcast_context, &libvirt_callbacks, NULL,
		       libvirt_context) < 0) {
		printf("Failed initialization!\n");
		return 1;
	}

	while (mcast_dispatch(mcast_context, NULL) >= 0);

	mcast_shutdown(mcast_context);
	libvirt_shutdown(libvirt_context);

	return 0;
}
