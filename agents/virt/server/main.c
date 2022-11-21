#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/param.h>
#include <libgen.h>
#include <stdint.h>
#include <syslog.h>

/* Local includes */
#include "simpleconfig.h"
#include "static_map.h"
#include "xvm.h"
#include "server_plugin.h"
#include "simple_auth.h"
#include "debug.h"

/* configure.c */
int daemon_init(const char *prog, const char *pid_file, int nofork);
int daemon_cleanup(void);


static void
usage(void)
{
	printf("Usage: fence_virtd [options]\n");
	printf("  -F               Do not daemonize.\n");
	printf("  -f <file>        Use <file> as configuration file.\n");
	printf("  -d <level>       Set debugging level to <level>.\n");
	printf("  -c               Configuration mode.\n");
	printf("  -l               List plugins.\n");
	printf("  -w               Wait for initialization.\n");
	printf("  -p <file>        Use <file> to record the active process id.\n");
}


static int run = 1;
static void
exit_handler(int sig)
{
	run = 0;
}


int
main(int argc, char **argv)
{
	char val[4096];
	char listener_name[80];
	char backend_name[80];
	const char *config_file = SYSCONFDIR "/fence_virt.conf";
	char *pid_file = NULL;
	config_object_t *config = NULL;
	map_object_t *map = NULL;
	const listener_plugin_t *lp;
	const backend_plugin_t *p;
	listener_context_t listener_ctx = NULL;
	backend_context_t backend_ctx = NULL;
	int debug_set = 0, foreground = 0, wait_for_init = 0;
	int opt, configure = 0;

	config = sc_init();
	map = map_init();

	if (!config || !map) {
		perror("malloc");
		return -1;
	}

	while ((opt = getopt(argc, argv, "Ff:d:cwlhp:")) != EOF) {
		switch(opt) {
		case 'F':
			printf("Background mode disabled\n");
			foreground = 1;
			break;
		case 'f':
			printf("Using %s\n", optarg);
			config_file = optarg;
			break;
		case 'p':
			printf("Using %s\n", optarg);
			pid_file = optarg;
			break;
		case 'd':
			debug_set = atoi(optarg);
			break;
		case 'c':
			configure = 1;
			break;
		case 'w':
			wait_for_init = 1;
			break;
		case 'l':
			plugin_dump();
			return 0;
		case 'h':
		case '?':
			usage();
			return 0;
		default:
			return -1;
		}
	}

	if (configure) {
		return do_configure(config, config_file);
	}

	if (sc_parse(config, config_file) != 0) {
		printf("Failed to parse %s\n", config_file);
		return -1;
	}

	if (debug_set) {
		snprintf(val, sizeof(val), "%d", debug_set);
		sc_set(config, "fence_virtd/@debug", val);
	} else {
		if (sc_get(config, "fence_virtd/@debug", val, sizeof(val))==0)
			debug_set = atoi(val);
	}

	dset(debug_set);

	if (!foreground) {
		if (sc_get(config, "fence_virtd/@foreground",
			   val, sizeof(val)) == 0)
			foreground = atoi(val);
	}

	if (!wait_for_init) {
		if (sc_get(config, "fence_virtd/@wait_for_init",
			   val, sizeof(val)) == 0)
			wait_for_init = atoi(val);
		if (!wait_for_init) {
			/* XXX compat */
			if (sc_get(config, "fence_virtd/@wait_for_backend",
				   val, sizeof(val)) == 0)
				wait_for_init = atoi(val);
		}
	}

	if (dget() > 3)
		sc_dump(config, stdout);

	if (sc_get(config, "fence_virtd/@backend", backend_name,
		   sizeof(backend_name))) {
		printf("Failed to determine backend.\n");
		printf("%s\n", val);
		return -1;
	}

	dbg_printf(1, "Backend plugin: %s\n", backend_name);

	if (sc_get(config, "fence_virtd/@listener", listener_name,
		   sizeof(listener_name))) {
		printf("Failed to determine backend.\n");
		printf("%s\n", val);
		return -1;
	}

	dbg_printf(1, "Listener plugin: %s\n", listener_name);

	if (sc_get(config, "fence_virtd/@module_path", val,
		   sizeof(val))) {
#ifdef MODULE_PATH
		snprintf(val, sizeof(val), MODULE_PATH);
#else
		printf("Failed to determine module path.\n");
		return -1;
#endif
	}

	dbg_printf(1, "Searching %s for plugins...\n", val);

	opt = plugin_search(val);
	if (opt > 0) {
		dbg_printf(1, "%d plugins found\n", opt);
	} else {
		printf("No plugins found\n");
		return 1;
	}

	if (dget() > 3)
		plugin_dump();

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

	if (pid_file == NULL) {
		pid_file = malloc(PATH_MAX);
		memset(pid_file, 0, PATH_MAX);
		snprintf(pid_file, PATH_MAX, "/var/run/%s.pid", basename(argv[0]));
	}

	if (check_file_permissions(config_file) != 0)
		return -1;

	sprintf(val, "listeners/%s/@key_file", listener_name);
	if (sc_get(config, val,
		   val, sizeof(val)-1) == 0) {
		dbg_printf(1, "Got %s for key_file\n", val);
	} else {
		snprintf(val, sizeof(val), "%s", DEFAULT_KEY_FILE);
	}

	if (check_file_permissions(val) != 0)
		return -1;

	openlog(basename(argv[0]), LOG_NDELAY | LOG_PID, LOG_DAEMON);

	daemon_init(basename(argv[0]), pid_file, foreground);

	signal(SIGINT, exit_handler);
	signal(SIGTERM, exit_handler);
	signal(SIGQUIT, exit_handler);

	syslog(LOG_NOTICE, "fence_virtd starting.  Listener: %s  Backend: %s",
		listener_name, backend_name);

	while (p->init(&backend_ctx, config) < 0) {
		if (!wait_for_init || !run) {
			if (foreground) {
				printf("Backend plugin %s failed to initialize\n",
				       backend_name);
			}
			syslog(LOG_ERR,
			       "Backend plugin %s failed to initialize\n",
			       backend_name);
			return 1;
		}
		sleep(5);
	}

	if (map_load(map, config) < 0) {
		syslog(LOG_WARNING, "Failed to load static maps\n");
	}

	/* only client we have now is mcast (fence_xvm behavior) */
	while (lp->init(&listener_ctx, p->callbacks, config, map,
			backend_ctx) != 0) {
		if (!wait_for_init || !run) {
			if (foreground) {
				printf("Listener plugin %s failed to initialize\n",
				       listener_name);
			}
			syslog(LOG_ERR,
			       "Listener plugin %s failed to initialize\n",
			       listener_name);
			return 1;
		}
		sleep(5);
	}

	while (run && lp->dispatch(listener_ctx, NULL) >= 0);

	syslog(LOG_NOTICE, "fence_virtd shutting down");

	map_release(map);
	sc_release(config);

	lp->cleanup(listener_ctx);
	p->cleanup(backend_ctx);

	plugin_unload();
	daemon_cleanup();

	return 0;
}
