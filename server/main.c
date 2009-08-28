#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>

/* Local includes */
#include <fence_virt.h>
#include <simpleconfig.h>
#include <server_plugin.h>
#include <debug.h>


int
main(int argc, char **argv)
{
	char val[80];
	char listener_name[80];
	char backend_name[80];
	const char *config_file = DEFAULT_CONFIG_FILE;
	config_object_t *config;
	const plugin_t *p;
	listener_context_t listener_ctx = NULL;
	backend_context_t backend_ctx = NULL;
	int debug_set = 0;
	int opt;

	config = sc_init();

	while ((opt = getopt(argc, argv, "f:d:")) != EOF) {
		switch(opt) {
		case 'f':
			printf("Using %s\n", optarg);
			config_file = optarg;
			break;
		case 'd':
			dset(atoi(optarg));
			debug_set = 1;
			break;
		default: 
			break;
		}
	}

	if (sc_parse(config, config_file) != 0) {
		printf("Failed to parse %s\n", config_file);
		return -1;
	}

	if (!debug_set) {
		if (sc_get(config, "fence_virtd/@debug",
			   val, sizeof(val)) == 0)
			dset(atoi(val));
	}

	sc_dump(config, stdout);

	if (sc_get(config, "fence_virtd/@backend", backend_name,
		   sizeof(backend_name))) {
		printf("Failed to determine backend.\n");
		printf("%s\n", val);
		return -1;
	}

	if (sc_get(config, "fence_virtd/@listener", listener_name,
		   sizeof(listener_name))) {
		printf("Failed to determine backend.\n");
		printf("%s\n", val);
		return -1;
	}

	printf("Backend plugin: %s\n", backend_name);

#ifdef _MODULE
	if (plugin_load("./libvirt.so") < 0) {
		printf("Doom\n");
	}
	if (plugin_load("/usr/lib64/fence_virt/libvirt.so") < 0) {
		printf("Doom\n");
	}
#endif
	plugin_dump();

	p = plugin_find(val);
	if (!p) {
		printf("Could not find plugin \"%s\n", val);
		return 1;
	}

	if (p->init(&backend_ctx, config) < 0) {
		printf("%s failed to initialize\n", val);
		return 1;
	}

	/* only client we have now is mcast (fence_xvm behavior) */
	if (mcast_init(&listener_ctx, p->callbacks, config,
		       backend_ctx) < 0) {
		printf("Failed initialization!\n");
		return 1;
	}

	while (mcast_dispatch(listener_ctx, NULL) >= 0);

	mcast_shutdown(listener_ctx);
	p->cleanup(backend_ctx);

	return 0;
}
