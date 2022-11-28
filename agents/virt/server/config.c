#include "config.h"

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <net/if.h>
#include <arpa/inet.h>
#include <errno.h>

#include "simpleconfig.h"
#include "static_map.h"
#include "mcast.h"
#include "xvm.h"
#include "server_plugin.h"
#include "simple_auth.h"


static int
yesno(const char *prompt, int dfl)
{
	char result[10];

	printf("%s [%c/%c]? ", prompt, dfl?'Y':'y', dfl?'n':'N');
	fflush(stdout);

	memset(result, 0, sizeof(result));
	if (fgets(result, 9, stdin) == NULL)
		return dfl;

	if (result[0] == 'y' || result[0] == 'Y')
		return 1;
	if (result[0] == 'n' || result[0] == 'N')
		return 0;

	return dfl;
}


static int
text_input(const char *prompt, const char *dfl, char *input, size_t len)
{
	const char *tmpdfl = dfl;
	const char *nulldfl = "";

	if (dfl == NULL) {
		tmpdfl = nulldfl;
	}

	printf("%s [%s]: ", prompt, tmpdfl);
	fflush(stdout);

	memset(input, 0, len);
	if (fgets(input, len, stdin) == NULL) {
		strncpy(input, tmpdfl, len);
		return 0;
	}
	if (input[strlen(input)-1] == '\n')
		input[strlen(input)-1] = 0;

	if (strlen(input) == 0) {
		strncpy(input, tmpdfl, len);
		return 0;
	}

	return 0;
}


static int
plugin_path_configure(config_object_t *config)
{
	char val[4096];
	char inp[4096];
	int done = 0;

	if (sc_get(config, "fence_virtd/@module_path", val,
	   	   sizeof(val))) {
#ifdef MODULE_PATH
		snprintf(val, sizeof(val), MODULE_PATH);
#else
		printf("Failed to determine module search path.\n");
#endif
	}

	do {
		text_input("Module search path", val, inp, sizeof(inp));

		printf("\n");
		done = plugin_search(inp);
		if (done > 0) {
			plugin_dump();
			done = 1;
		} else {
			done = 0;
			printf("No modules found in %s!\n", inp);
			if (yesno("Use this value anyway", 0) == 1)
				done = 1;
		}
	} while (!done);

	sc_set(config, "fence_virtd/@module_path", inp);

	return 0;
}


static int
backend_config_libvirt(config_object_t *config)
{
	char val[4096];
	char inp[4096];

	printf("\n");
	printf("The libvirt backend module is designed for single desktops or\n"
	       "servers.  Do not use in environments where virtual machines\n"
	       "may be migrated between hosts.\n\n");

	/* Default backend plugin */
	if (sc_get(config, "backends/libvirt/@uri", val,
		   sizeof(val))) {
		strncpy(val, DEFAULT_HYPERVISOR_URI, sizeof(val));
	}

	text_input("Libvirt URI", val, inp, sizeof(inp));

	sc_set(config, "backends/libvirt/@uri", inp);

	return 0;
}


static int
backend_config_cpg(config_object_t *config)
{
	char val[4096];
	char inp[4096];
	int done = 0;

	printf("\n");
	printf("The CPG backend module is designed for use in clusters\n"
	       "running corosync and libvirt. It utilizes the CPG API to \n"
	       "route fencing requests, finally utilizing libvirt to perform\n"
	       "fencing actions.\n\n");

	if (sc_get(config, "backends/cpg/@uri", val,
		   sizeof(val))) {
		strncpy(val, DEFAULT_HYPERVISOR_URI, sizeof(val));
	}

	text_input("Libvirt URI", val, inp, sizeof(inp));

	sc_set(config, "backends/cpg/@uri", inp);

	printf("\n");
	printf("The name mode is how the cpg plugin stores and \n"
	       "references virtual machines.  Since virtual machine names\n"
	       "are not guaranteed to be unique cluster-wide, use of UUIDs\n"
	       "is strongly recommended.  However, for compatibility with \n"
	       "fence_xvmd, the use of 'name' mode is also supported.\n\n");

	if (sc_get(config, "backends/cpg/@name_mode", val,
		   sizeof(val))) {
		strncpy(val, "uuid", sizeof(val));
	}

	do {
		text_input("VM naming/tracking mode (name or uuid)",
			   val, inp, sizeof(inp));
		if (!strcasecmp(inp, "uuid")) {
			done = 1;
		} else if (!strcasecmp(inp, "name")) {
			done = 0;
			printf("This can be dangerous if you do not take care to"
			       "ensure that\n"
			       "virtual machine names are unique "
			       "cluster-wide.\n");
			if (yesno("Use name mode anyway", 1) == 1)
				done = 1;
		}
	} while (!done);

	sc_set(config, "backends/cpg/@name_mode", inp);

	return 0;
}


static int
listener_config_multicast(config_object_t *config)
{
	char val[4096];
	char inp[4096];
	const char *family = "ipv4";
	struct in_addr sin;
	struct in6_addr sin6;
	int done = 0;

	printf("\n");
	printf("The multicast listener module is designed for use environments\n"
	       "where the guests and hosts may communicate over a network using\n"
	       "multicast.\n\n");


	/* MULTICAST IP ADDRESS/FAMILY */
	printf("The multicast address is the address that a client will use to\n"
	       "send fencing requests to fence_virtd.\n\n");

	if (sc_get(config, "listeners/multicast/@address",
		   val, sizeof(val)-1)) {
		strncpy(val, IPV4_MCAST_DEFAULT, sizeof(val));
	}

	done = 0;
	do {
		text_input("Multicast IP Address", val, inp, sizeof(inp));

		if (inet_pton(AF_INET, inp, &sin) == 1) {
			printf("\nUsing ipv4 as family.\n\n");
			family = "ipv4";
			done = 1;
		} else if (inet_pton(AF_INET6, inp, &sin6) == 1) {
			printf("\nUsing ipv6 as family.\n\n");
			family = "ipv6";
			done = 1;
		} else
			printf("'%s' is not a valid IP address!\n", inp);
	} while (!done);

	sc_set(config, "listeners/multicast/@family", family);
	sc_set(config, "listeners/multicast/@address", inp);

	/* MULTICAST IP PORT */
	if (sc_get(config, "listeners/multicast/@port",
		   val, sizeof(val)-1)) {
		snprintf(val, sizeof(val), "%d", DEFAULT_MCAST_PORT);
	}

	done = 0;
	do {
		char *p;
		int ret;

		text_input("Multicast IP Port", val, inp, sizeof(inp));
		ret = strtol(inp, &p, 0);
		if (*p != '\0' || ret <= 0 || ret >= 65536) {
			printf("Port value '%s' is out of range\n", val);
			continue;
		} else
			done = 1;
	} while (!done);

	sc_set(config, "listeners/multicast/@port", inp);

	/* MULTICAST INTERFACE */
	printf("\nSetting a preferred interface causes fence_virtd to listen only\n"
	       "on that interface.  Normally, it listens on all interfaces.\n"
	       "In environments where the virtual machines are using the host\n"
	       "machine as a gateway, this *must* be set (typically to virbr0).\n"
	       "Set to 'none' for no interface.\n\n"
	      );

	if (sc_get(config, "listeners/multicast/@interface",
		   val, sizeof(val)-1)) {
		strncpy(val, "none", sizeof(val));
	}

	done = 0;
	do { 
		text_input("Interface", val, inp, sizeof(inp));

		if (!strcasecmp(inp, "none")) {
			break;
		}

		if (strlen(inp) > 0) {
			int ret;

			ret = if_nametoindex(inp);
			if (ret < 0) {
				printf("Invalid interface: %s\n", inp);
				if (yesno("Use anyway", 1) == 1)
					done = 1;
			} else
				done = 1;
		} else
			printf("No interface given\n");
	} while (!done);

	if (!strcasecmp(inp, "none")) {
		sc_set(config, "listeners/multicast/@interface", NULL);
	} else {
		sc_set(config, "listeners/multicast/@interface", inp);
	}


	/* KEY FILE */
	printf("\nThe key file is the shared key information which is used to\n"
	       "authenticate fencing requests.  The contents of this file must\n"
	       "be distributed to each physical host and virtual machine within\n"
	       "a cluster.\n\n");

	if (sc_get(config, "listeners/multicast/@key_file",
		   val, sizeof(val)-1)) {
		strncpy(val, DEFAULT_KEY_FILE, sizeof(val));
	}

	done = 0;
	do { 
		text_input("Key File", val, inp, sizeof(inp));

		if (!strcasecmp(inp, "none")) {
			break;
		}

		if (strlen(inp) > 0) {
			if (inp[0] != '/') {
				printf("Invalid key file: %s\n", inp);
				if (yesno("Use anyway", 1) == 1)
					done = 1;
			} else
				done = 1;
		} else
			printf("No key file given\n");
	} while (!done);

	if (!strcasecmp(inp, "none")) {
		sc_set(config, "listeners/multicast/@key_file", NULL);
	} else {
		sc_set(config, "listeners/multicast/@key_file", inp);
	}

	return 0;
}

static int
listener_config_tcp(config_object_t *config)
{
	char val[4096];
	char inp[4096];
	const char *family = "ipv4";
	struct in_addr sin;
	struct in6_addr sin6;
	int done = 0;

	printf("\n");
	printf("The TCP listener module is designed for use in environments\n"
	       "where the guests and hosts communicate over viosproxy.\n\n");

	/* IP ADDRESS/FAMILY */
	printf("The IP address is the address that a client will use to\n"
	       "send fencing requests to fence_virtd.\n\n");

	if (sc_get(config, "listeners/tcp/@address",
		   val, sizeof(val)-1)) {
		strncpy(val, IPV4_MCAST_DEFAULT, sizeof(val));
	}

	done = 0;
	do {
		text_input("TCP Listen IP Address", val, inp, sizeof(inp));

		if (inet_pton(AF_INET, inp, &sin) == 1) {
			printf("\nUsing ipv4 as family.\n\n");
			family = "ipv4";
			done = 1;
		} else if (inet_pton(AF_INET6, inp, &sin6) == 1) {
			printf("\nUsing ipv6 as family.\n\n");
			family = "ipv6";
			done = 1;
		} else {
			printf("'%s' is not a valid IP address!\n", inp);
			continue;
		}
	} while (!done);

	sc_set(config, "listeners/tcp/@family", family);
	sc_set(config, "listeners/tcp/@address", inp);

	/* MULTICAST IP PORT */
	if (sc_get(config, "listeners/tcp/@port",
		   val, sizeof(val)-1)) {
		snprintf(val, sizeof(val), "%d", DEFAULT_MCAST_PORT);
	}

	done = 0;
	do {
		char *p;
		int ret;

		text_input("TCP Listen Port", val, inp, sizeof(inp));

		ret = strtol(inp, &p, 0);
		if (*p != '\0' || ret <= 0 || ret >= 65536) {
			printf("Port value '%s' is out of range\n", val);
			continue;
		}
		done = 1;
	} while (!done);
	sc_set(config, "listeners/tcp/@port", inp);

	/* KEY FILE */
	printf("\nThe key file is the shared key information which is used to\n"
	       "authenticate fencing requests.  The contents of this file must\n"
	       "be distributed to each physical host and virtual machine within\n"
	       "a cluster.\n\n");

	if (sc_get(config, "listeners/tcp/@key_file",
		   val, sizeof(val)-1)) {
		strncpy(val, DEFAULT_KEY_FILE, sizeof(val));
	}

	done = 0;
	do { 
		text_input("Key File", val, inp, sizeof(inp));

		if (!strcasecmp(inp, "none")) {
			break;
		}

		if (strlen(inp) > 0) {
			if (inp[0] != '/') {
				printf("Invalid key file: %s\n", inp);
				if (yesno("Use anyway", 1) == 1)
					done = 1;
			} else
				done = 1;
		} else
			printf("No key file given\n");
	} while (!done);

	if (!strcasecmp(inp, "none")) {
		sc_set(config, "listeners/tcp/@key_file", NULL);
	} else {
		sc_set(config, "listeners/tcp/@key_file", inp);
	}

	return 0;
}

static int
listener_config_serial(config_object_t *config)
{
	char val[4096];
	char inp[4096];
	int done;

	printf("\n");
	printf("The serial plugin allows fence_virtd to communicate with\n"
	       "guests using serial or guest-forwarding VMChannel instead\n"
	       "of using TCP/IP networking.\n\n");
	printf("Special configuration of virtual machines is required. See\n"
	       "fence_virt.conf(5) for more details.\n\n");

	if (sc_get(config, "listeners/serial/@uri",
		   val, sizeof(val)-1)) {
		strncpy(val, DEFAULT_HYPERVISOR_URI, sizeof(val));
	}

	text_input("Libvirt URI", val, inp, sizeof(inp));
	
	printf("\nSetting a socket path prevents fence_virtd from taking\n"
	       "hold of all Unix domain sockets created when the guest\n"
	       "is started.  A value like /var/run/cluster/fence might\n"
	       "be a good value.  Don't forget to create the directory!\n\n");

	if (sc_get(config, "listeners/serial/@path",
		   val, sizeof(val)-1)) {
		strncpy(val, "none", sizeof(val));
	}

	text_input("Socket directory", val, inp, sizeof(inp));
	if (!strcasecmp(inp, "none")) {
		sc_set(config, "listeners/serial/@path", NULL);
	} else {
		sc_set(config, "listeners/serial/@path", inp);
	}

	printf("\nThe serial plugin allows two types of guest to host\n"
	       "configurations.  One is via a serial port; the other is\n"
	       "utilizing the newer VMChannel.\n\n");

	if (sc_get(config, "listeners/serial/@mode",
		   val, sizeof(val)-1)) {
		strncpy(val, "serial", sizeof(val));
	}

	if (!strcasecmp(inp, "none")) {
		sc_set(config, "listeners/serial/@path", NULL);
	} else {
		sc_set(config, "listeners/serial/@path", inp);
	}

	done = 0;
	do { 
		text_input("Mode (serial or vmchannel)", val, inp,
			   sizeof(inp));

		if (strcasecmp(inp, "serial") && strcasecmp(inp, "vmchannel")) {
			printf("Invalid mode: %s\n", inp);
			if (yesno("Use anyway", 1) == 1)
				done = 1;
		} else
			done = 1;
	} while (!done);

	sc_set(config, "listeners/serial/@mode", inp);
	return 0;
}


static int
backend_configure(config_object_t *config)
{
	char val[4096];
	char inp[4096];
	int done;

	printf("\n");
	printf("Backend modules are responsible for routing requests to\n"
	       "the appropriate hypervisor or management layer.\n\n");

	/* Default backend plugin */
	if (sc_get(config, "fence_virtd/@backend", val,
		   sizeof(val))) {
		strncpy(val, "libvirt", sizeof(val));
	}

	done = 0;
	do {
		text_input("Backend module", val, inp, sizeof(inp));
		if (plugin_find_backend(inp) == NULL) {
			printf("No backend module named %s found!\n", inp);
			if (yesno("Use this value anyway", 0) == 1)
				done = 1;
		} else
			done = 1;
	} while (!done);

	sc_set(config, "fence_virtd/@backend", inp);

	if (!strcmp(inp, "libvirt")) {
		backend_config_libvirt(config);
	} else if (!strcmp(inp, "cpg")) {
		backend_config_cpg(config);
	}

	return 0;
}


static int
listener_configure(config_object_t *config)
{
	char val[4096];
	char inp[4096];
	int done;

	printf("\n");
	printf("Listener modules are responsible for accepting requests\n"
	       "from fencing clients.\n\n");

	/* Default backend plugin */
	if (sc_get(config, "fence_virtd/@listener", val,
		   sizeof(val))) {
		strncpy(val, "multicast", sizeof(val));
	}

	done = 0;
	do {
		text_input("Listener module", val, inp, sizeof(inp));
		if (plugin_find_listener(inp) == NULL) {
			printf("No listener module named %s found!\n", inp);
			if (yesno("Use this value anyway", 0) == 1)
				done = 1;
		} else
			done = 1;
	} while (!done);

	sc_set(config, "fence_virtd/@listener", inp);
	if (!strcmp(inp, "multicast"))
		listener_config_multicast(config);
	else if (!strcmp(inp, "tcp"))
		listener_config_tcp(config);
	else if (!strcmp(inp, "serial"))
		listener_config_serial(config);
	else
		printf("Unable to configure unknown listner module '%s'\n", inp);

	return 0;
}


int
check_file_permissions(const char *fname)
{
	struct stat st;
	mode_t file_perms = 0600;
	int ret;

	ret = stat(fname, &st);
	if (ret != 0) {
		printf("stat failed on file '%s': %s\n",
			 fname, strerror(errno));
		return 1;
	}

	if ((st.st_mode & 0777) != file_perms) {
		printf("Insecure permissions on file "
			 "'%s': changing from 0%o to 0%o.\n", fname,
			 (unsigned int)(st.st_mode & 0777),
			 (unsigned int)file_perms);
		if (chmod(fname, file_perms) != 0) {
			printf("Unable to change permissions for file '%s'",
				fname);
			return 1;
		}
	}

	return 0;
}

int
do_configure(config_object_t *config, const char *config_file)
{
	FILE *fp = NULL;
	char message[80];
	char tmp_filename[4096];
	int tmp_fd = -1;
	mode_t old_umask;

	if (sc_parse(config, config_file) != 0) {
		printf("Parsing of %s failed.\n", config_file);
		if (yesno("Start from scratch", 0) == 0) {
			return 1;
		}
	}

	plugin_path_configure(config);
	listener_configure(config);
	backend_configure(config);

	printf("\nConfiguration complete.\n\n");

	printf("=== Begin Configuration ===\n");
	sc_dump(config, stdout);
	printf("=== End Configuration ===\n");

	snprintf(message, sizeof(message), "Replace %s with the above",
		 config_file);
	if (yesno(message, 0) == 0) {
		return 1;
	}

	snprintf(tmp_filename, sizeof(tmp_filename),
		 "%s.XXXXXX", config_file);

	old_umask = umask(077);
	tmp_fd = mkstemp(tmp_filename);
	umask(old_umask);

	if (tmp_fd < 0) {
		perror("fopen");
		printf("Failed to write configuration file!\n");
		return 1;
	}

	fp = fdopen(tmp_fd, "w+");
	if (fp == NULL)
		goto out_fail;

	sc_dump(config, fp);

	if (rename(tmp_filename, config_file) < 0) {
		perror("rename");
		goto out_fail;
	}

	fclose(fp);
	close(tmp_fd);

	return 0;

out_fail:
	if (fp)
		fclose(fp);
	if (tmp_fd >= 0)
		close(tmp_fd);
	if (strlen(tmp_filename))
		unlink(tmp_filename);
	printf("Failed to write configuration file!\n");
	return 1;
}
