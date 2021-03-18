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

#include "config.h"

#include <dlfcn.h>
#include <stdlib.h>
#include <errno.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdint.h>
#include <malloc.h>
#include <string.h>
#include <dirent.h>

#include "list.h"
#include "simpleconfig.h"
#include "static_map.h"
#include "server_plugin.h"
#include "debug.h"

typedef struct _plugin_list {
	list_head();
	const listener_plugin_t *listener;
	const backend_plugin_t *backend;
	void *handle;
	plugin_type_t type;
} plugin_list_t;

static plugin_list_t *server_plugins = NULL;


static int
plugin_reg_backend(void *handle, const backend_plugin_t *plugin)
{
	plugin_list_t *newplug;

	if (plugin_find_backend(plugin->name)) {
		errno = EEXIST;
		return -1;
	}

	newplug = malloc(sizeof(*newplug));
	if (!newplug) 
		return -1;
	memset(newplug, 0, sizeof(*newplug));
	newplug->backend = plugin;
	newplug->type = PLUGIN_BACKEND;
	newplug->handle = handle;

	list_insert(&server_plugins, newplug);
	return 0;
}


static int
plugin_reg_listener(void *handle, const listener_plugin_t *plugin)
{
	plugin_list_t *newplug;

	if (plugin_find_listener(plugin->name)) {
		errno = EEXIST;
		return -1;
	}

	newplug = malloc(sizeof(*newplug));
	if (!newplug) 
		return -1;
	memset(newplug, 0, sizeof(*newplug));
	newplug->listener = plugin;
	newplug->type = PLUGIN_LISTENER;
	newplug->handle = handle;

	list_insert(&server_plugins, newplug);
	return 0;
}


void
plugin_dump(void)
{
	plugin_list_t *p;
	int x, y;

	y = 0;
	list_for(&server_plugins, p, x) {
		if (p->type == PLUGIN_BACKEND) {
			if (!y) {
				y = 1;
				printf("Available backends:\n");
			}
			printf("    %s %s\n",
			       p->backend->name, p->backend->version);
		}
	}

	y = 0;
	list_for(&server_plugins, p, x) {
		if (p->type == PLUGIN_LISTENER) {
			if (!y) {
				y = 1;
				printf("Available listeners:\n");
			}
			printf("    %s %s\n",
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


static int
backend_plugin_load(void *handle, const char *libpath)
{
	const backend_plugin_t *plug = NULL;
	double (*modversion)(void);
	backend_plugin_t *(*modinfo)(void);

	modversion = dlsym(handle, BACKEND_VER_STR);
	if (!modversion) {
		dbg_printf(1, "Failed to map %s\n", BACKEND_VER_STR);
		errno = EINVAL;
		return -1;
	}

	if (modversion() != PLUGIN_VERSION_BACKEND) {
		dbg_printf(1, "API version mismatch in %s: \n"
			   "       %f expected; %f received.\n", libpath,
			   PLUGIN_VERSION_BACKEND, modversion());
		errno = EINVAL;
		return -1;
	}

	modinfo = dlsym(handle, BACKEND_INFO_STR);
	if (!modinfo) {
		dbg_printf(1, "Failed to map %s\n", BACKEND_INFO_STR);
		errno = EINVAL;
		return -1;
	}

	plug = modinfo();
	if (plugin_reg_backend(handle, plug) < 0) {
		dbg_printf(1, "Failed to register %s %s\n", plug->name,
			   plug->version);
		errno = EINVAL;
		return -1;
	} else {
		dbg_printf(1, "Registered backend plugin %s %s\n",
			   plug->name, plug->version);
	}

	return 0;
}


static int
listener_plugin_load(void *handle, const char *libpath)
{
	const listener_plugin_t *plug = NULL;
	double (*modversion)(void);
	listener_plugin_t *(*modinfo)(void);

	modversion = dlsym(handle, LISTENER_VER_STR);
	if (!modversion) {
		dbg_printf(1, "Failed to map %s\n", LISTENER_VER_STR);
		errno = EINVAL;
		return -1;
	}

	if (modversion() != PLUGIN_VERSION_LISTENER) {
		dbg_printf(1, "API version mismatch in %s: \n"
		       	   "       %f expected; %f received.\n", libpath,
			   PLUGIN_VERSION_LISTENER, modversion());
		dlclose(handle);
		errno = EINVAL;
		return -1;
	}

	modinfo = dlsym(handle, LISTENER_INFO_STR);
	if (!modinfo) {
		dbg_printf(1, "Failed to map %s\n", LISTENER_INFO_STR);
		errno = EINVAL;
		return -1;
	}

	plug = modinfo();
	if (plugin_reg_listener(handle, plug) < 0) {
		dbg_printf(1, "Failed to register %s %s\n", plug->name,
			   plug->version);
		errno = EINVAL;
		return -1;
	} else {
		dbg_printf(1, "Registered listener plugin %s %s\n",
			   plug->name, plug->version);
	}

	return 0;
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

	errno = 0;

	if (!libpath) {
		errno = EINVAL;
		return -1;
	}

	dbg_printf(3, "Loading plugin from %s\n", libpath);
	handle = dlopen(libpath, RTLD_NOW);
	if (!handle) {
		dbg_printf(3, "Could not dlopen %s: %s\n", libpath, dlerror());
		errno = ELIBACC;
		return -1;
	}

	if (!backend_plugin_load(handle, libpath) ||
	    !listener_plugin_load(handle, libpath))
		return 0;

	dbg_printf(3, "%s is not a valid plugin\n", libpath);
	dlclose(handle);
	errno = EINVAL;
	return -1;
}

void
plugin_unload(void)
{
	plugin_list_t *p;
	int x;

	list_for(&server_plugins, p, x) {
		dlclose(p->handle);
	}
}

/**
  Free up a null-terminated array of strings
 */
static void
free_dirnames(char **dirnames)
{
	int x = 0;

	for (; dirnames[x]; x++)
		free(dirnames[x]);

	free(dirnames);
}


static int
_compare(const void *a, const void *b)
{
	return strcmp((const char *)a, (const char *)b);
}


/**
  Read all entries in a directory and return them in a NULL-terminated,
  sorted array.
 */
static int
read_dirnames_sorted(const char *directory, char ***dirnames)
{
	DIR *dir;
	struct dirent *entry;
	char filename[1024];
	int count = 0, x = 0;

	dir = opendir(directory);
	if (!dir)
		return -1;

	/* Count the number of plugins */
	while ((entry = readdir(dir)) != NULL)
		++count;

	/* Malloc the entries */
	*dirnames = malloc(sizeof(char *) * (count+1));
	if (!*dirnames) {
#ifdef DEBUG
		printf("%s: Failed to malloc %d bytes",
		       __FUNCTION__, (int)(sizeof(char *) * (count+1)));
#endif
		closedir(dir);
		errno = ENOMEM;
		return -1;
	}
	memset(*dirnames, 0, sizeof(char *) * (count + 1));
	rewinddir(dir);

	/* Store the directory names. */
	while ((entry = readdir(dir)) != NULL) {
		snprintf(filename, sizeof(filename), "%s/%s", directory,
			 entry->d_name);

		(*dirnames)[x] = strdup(filename);
		if (!(*dirnames)[x]) {
#ifdef DEBUG
			printf("Failed to duplicate %s\n",
			       filename);
#endif
			free_dirnames(*dirnames);
			closedir(dir);
			errno = ENOMEM;
			return -1;
		}
		++x;
	}

	closedir(dir);

	/* Sort the directory names. */
	qsort((*dirnames), count, sizeof(char *), _compare);

	return 0;
}


/**
 */
int
plugin_search(const char *pathname)
{
	int found = 0;
	int fcount = 0;
	char **filenames;

	dbg_printf(1, "Searching for plugins in %s\n", pathname);
	if (read_dirnames_sorted(pathname, &filenames) != 0) {
		return -1;
	}

	for (fcount = 0; filenames[fcount]; fcount++) {

		if (plugin_load(filenames[fcount]) == 0)
			++found;
	}

	free_dirnames(filenames);
	if (!found) {
		dbg_printf(1, "No usable plugins found.\n");
		errno = ELIBACC;
		return -1;
	}

	return found;
}
