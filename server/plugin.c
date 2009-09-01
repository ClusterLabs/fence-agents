/*
  Copyright Red Hat, Inc. 2002-2004, 2009

  The Magma Cluster API Library is free software; you can redistribute
  it and/or modify it under the terms of the GNU Lesser General Public
  License as published by the Free Software Foundation; either version
  2.1 of the License, or (at your option) any later version.

  The Magma Cluster API Library is distributed in the hope that it will
  be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
  of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public
  License along with this library; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
  USA.
 */
/** @file
 * Plugin loading routines
 */
#include <dlfcn.h>
#include <stdlib.h>
#include <errno.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <dirent.h>
#include <unistd.h>

#include <list.h>
#include <simpleconfig.h>
#include <server_plugin.h>
#include <malloc.h>
#include <string.h>


typedef struct _plugin_list {
	list_head();
	const listener_plugin_t *listener;
	const backend_plugin_t *backend;
	plugin_type_t type;
} plugin_list_t;

static plugin_list_t *server_plugins = NULL;

int
plugin_reg_backend(const backend_plugin_t *plugin)
{
	plugin_list_t *newplug;

	newplug = malloc(sizeof(*newplug));
	if (!newplug) 
		return -1;
	memset(newplug, 0, sizeof(*newplug));
	newplug->backend = plugin;
	newplug->type = PLUGIN_BACKEND;

	list_insert(&server_plugins, newplug);
	return 0;
}


int
plugin_reg_listener(const listener_plugin_t *plugin)
{
	plugin_list_t *newplug;

	newplug = malloc(sizeof(*newplug));
	if (!newplug) 
		return -1;
	memset(newplug, 0, sizeof(*newplug));
	newplug->listener = plugin;
	newplug->type = PLUGIN_LISTENER;

	list_insert(&server_plugins, newplug);
	return 0;
}


void
plugin_dump(void)
{
	plugin_list_t *p;
	int x;

	list_for(&server_plugins, p, x) {
		if (p->type == PLUGIN_BACKEND) {
			printf("backend: %s %s\n",
			       p->backend->name, p->backend->version);
		} else if (p->type == PLUGIN_LISTENER) {
			printf("listener: %s %s\n",
			       p->listener->name, p->listener->version);
		}
	}
}

const backend_plugin_t *
plugin_find_backend(const char *name)
{
	plugin_list_t *p;
	int x;

	list_for(&server_plugins, p, x) {
		if (p->type != PLUGIN_BACKEND)
			continue;
		if (!strcasecmp(name, p->backend->name))
			return p->backend;
	}

	return NULL;
}


const listener_plugin_t *
plugin_find_listener(const char *name)
{
	plugin_list_t *p;
	int x;

	list_for(&server_plugins, p, x) {
		if (p->type != PLUGIN_LISTENER)
			continue;
		if (!strcasecmp(name, p->listener->name))
			return p->listener;
	}

	return NULL;
}


/**
 * Load a cluster plugin .so file and map all the functions
 * provided to entries in a backend_plugin_t structure.
 *
 * @param libpath	Path to file.
 * @return		NULL on failure, or plugin-specific
 * 			(const) backend_plugin_t * structure on
 * 			success.
 */
int
plugin_load(const char *libpath)
{
	void *handle = NULL;
	const backend_plugin_t *plug = NULL;
	double (*modversion)(void);
	backend_plugin_t *(*modinfo)(void);
	struct stat sb;

	errno = 0;

	if (!libpath) {
		errno = EINVAL;
		return -1;
	}

	if (stat(libpath, &sb) != 0) {
		return -1;
	}

	/*
	   If it's not owner-readable or it's a directory,
	   ignore/fail.  Thus, a user may change the permission of
	   a plugin "u-r" and this would then prevent magma apps
	   from loading it.
	 */
	if (S_ISDIR(sb.st_mode)) {
		errno = EISDIR;
		return -1;
	}

	if (!(sb.st_mode & S_IRUSR)) {
#ifdef DEBUG
		printf("Ignoring %s (User-readable bit not set)\n",
		       libpath);
#endif
		errno = EPERM;
		return -1;
	}

	handle = dlopen(libpath, RTLD_LAZY);
	if (!handle) {
		errno = ELIBACC;
		return -1;
	}

	modversion = dlsym(handle, BACKEND_VER_STR);
	if (!modversion) {
#ifdef DEBUG
		printf("Failed to map %s\n", BACKEND_VER_STR);
#endif
		dlclose(handle);
		errno = EINVAL;
		return -1;
	}

	if (modversion() != PLUGIN_VERSION_BACKEND) {
#ifdef DEBUG
		printf("API version mismatch in %s: \n"
		       "       %f expected; %f received.\n", libpath,
			, modversion());
#endif
		dlclose(handle);
		errno = EINVAL;
		return -1;
	}

	modinfo = dlsym(handle, BACKEND_INFO_STR);
	if (!modinfo) {
#ifdef DEBUG
		printf("Failed to map %s\n", BACKEND_INFO_STR);
#endif
		dlclose(handle);
		errno = EINVAL;
		return -1;
	}

	plug = modinfo();
	if (plugin_reg_backend(plug) < 0) {
		dlclose(handle);
		errno = EINVAL;
		return -1;
	} else {
		printf("Registered plugin %s %s\n",
		       plug->name, plug->version);
	}

	return 0;
}
