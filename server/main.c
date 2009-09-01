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
	char val[4096];
	char listener_name[80];
	char backend_name[80];
	const char *config_file = DEFAULT_CONFIG_FILE;
	config_object_t *config;
	const listener_plugin_t *lp;
	const backend_plugin_t *p;
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
	if (sc_get(config, "fence_virtd/@module_path", val,
		   sizeof(val))) {
		printf("Failed to determine module path.\n");
		return -1;
	}

	printf("Searching %s for plugins...\n", val);

	opt = plugin_search(val);
	if (opt > 0) {
		printf("%d plugins found\n", opt);
	} else {
		printf("No plugins found\n");
		return 1;
	}

	plugin_dump();
#endif

	lp = plugin_find_listener(listener_name);
	if (!lp) {
		printf("Could not find listener \"%s\"\n", listener_name);
		return 1;
	}

	p = plugin_find_backend(backend_name);
	if (!p) {
		printf("Could not find backend \"%s\"\n", backend_name);
		return 1;
	}

	if (p->init(&backend_ctx, config) < 0) {
		printf("%s failed to initialize\n", backend_name);
		return 1;
	}

	/* only client we have now is mcast (fence_xvm behavior) */
	if (lp->init(&listener_ctx, p->callbacks, config,
		       backend_ctx) < 0) {
		printf("%s failed to initialize\n", listener_name);
		return 1;
	}

	while (lp->dispatch(listener_ctx, NULL) >= 0);

	lp->cleanup(listener_ctx);
	p->cleanup(backend_ctx);

	return 0;
}
