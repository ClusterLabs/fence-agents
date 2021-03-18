/*
  Copyright Red Hat, Inc. 2006-2017

  This program is free software; you can redistribute it and/or modify it
  under the terms of the GNU General Public License as published by the
  Free Software Foundation; either version 2, or (at your option) any
  later version.

  This program is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; see the file COPYING.  If not, write to the
  Free Software Foundation, Inc.,  675 Mass Ave, Cambridge, 
  MA 02139, USA.
*/
/*
 * Author: Lon Hohberger <lhh at redhat.com>
 */

#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/un.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/ioctl.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <netinet/in.h>
#include <netdb.h>
#include <sys/time.h>
#include <fcntl.h>
#include <errno.h>
#include <pthread.h>
#include <libvirt/virterror.h>
#include <nss.h>
#include <libgen.h>
#include <syslog.h>

/* Local includes */
#include "xvm.h"
#include "simple_auth.h"
#include "options.h"
#include "mcast.h"
#include "tcp.h"
#include "virt.h"
#include "debug.h"
#include "uuid-test.h"
#include "simpleconfig.h"
#include "static_map.h"
#include "server_plugin.h"

#define NAME "libvirt"
#define LIBVIRT_VERSION "0.3"

#define MAGIC 0x1e19317a

struct libvirt_info {
	int magic;
	config_object_t *config;
	int vp_count;
	virConnectPtr *vp;
};

#define VALIDATE(arg) \
do {\
	if (!arg || ((struct libvirt_info *)arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)


static void
libvirt_init_libvirt_conf(struct libvirt_info *info) {
	config_object_t *config = info->config;
	int i = 0;

	if (info->vp) {
		dbg_printf(2, "Lost libvirtd connection. Reinitializing.\n");
		for (i = 0 ; i < info->vp_count ; i++)
			virConnectClose(info->vp[i]);
		free(info->vp);
		info->vp = NULL;
	}
	info->vp_count = 0;

	do {
		virConnectPtr vp;
		virConnectPtr *vpl = NULL;
		char conf_attr[256];
		char value[1024];
		char *uri;

		if (i != 0) {
			snprintf(conf_attr, sizeof(conf_attr),
				"backends/libvirt/@uri%d", i);
		} else
			snprintf(conf_attr, sizeof(conf_attr), "backends/libvirt/@uri");
		++i;

		if (sc_get(config, conf_attr, value, sizeof(value)) != 0)
			break;

		uri = value;
		vp = virConnectOpen(uri);
		if (!vp) {
			dbg_printf(1, "[libvirt:INIT] Failed to connect to URI: %s\n", uri);
			continue;
		}

		vpl = realloc(info->vp, sizeof(*info->vp) * (info->vp_count + 1));
		if (!vpl) {
			dbg_printf(1, "[libvirt:INIT] Out of memory allocating URI: %s\n",
				uri);
			virConnectClose(vp);
			continue;
		}

		info->vp = vpl;
		info->vp[info->vp_count++] = vp;

		if (i > 1)
			dbg_printf(1, "[libvirt:INIT] Added URI%d %s\n", i - 1, uri);
		else
			dbg_printf(1, "[libvirt:INIT] Added URI %s\n", uri);
	} while (1);
}


static int
libvirt_bad_connections(struct libvirt_info *info) {
	int bad = 0;
	int i;

	for (i = 0 ; i < info->vp_count ; i++) {
		/*
		** Send a dummy command to trigger an error if libvirtd
		** died or restarted
		*/
		virConnectNumOfDomains(info->vp[i]);
		if (!virConnectIsAlive(info->vp[i])) {
			dbg_printf(1, "libvirt connection %d is dead\n", i);
			bad++;
		}
	}

	if (info->vp_count < 1 || bad)
		libvirt_init_libvirt_conf(info);

	return bad || info->vp_count < 1;
}

static void
libvirt_validate_connections(struct libvirt_info *info) {
	while (1) {
		if (libvirt_bad_connections(info))
			sleep(1);
		else
			break;
	}
}

static int
libvirt_null(const char *vm_name, void *priv)
{
	dbg_printf(5, "ENTER %s %s\n", __FUNCTION__, vm_name);
	printf("NULL operation: returning failure\n");
	return 1;
}


static int
libvirt_off(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;

	dbg_printf(5, "ENTER %s %s %u\n", __FUNCTION__, vm_name, seqno);
	VALIDATE(info);

	libvirt_validate_connections(info);
	return vm_off(info->vp, info->vp_count, vm_name);
}


static int
libvirt_on(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;

	dbg_printf(5, "ENTER %s %s %u\n", __FUNCTION__, vm_name, seqno);
	VALIDATE(info);

	libvirt_validate_connections(info);
	return vm_on(info->vp, info->vp_count, vm_name);
}


static int
libvirt_devstatus(void *priv)
{
	dbg_printf(5, "%s ---\n", __FUNCTION__);

	if (priv)
		return 0;
	return 1;
}


static int
libvirt_status(const char *vm_name, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;

	dbg_printf(5, "ENTER %s %s\n", __FUNCTION__, vm_name);
	VALIDATE(info);

	libvirt_validate_connections(info);
	return vm_status(info->vp, info->vp_count, vm_name);
}


static int
libvirt_reboot(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;

	dbg_printf(5, "ENTER %s %s %u\n", __FUNCTION__, vm_name, seqno);
	VALIDATE(info);

	libvirt_validate_connections(info);
	return vm_reboot(info->vp, info->vp_count, vm_name);
}


static int
libvirt_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	virt_list_t *vl;
	int x;

	dbg_printf(5, "ENTER %s\n", __FUNCTION__);
	VALIDATE(info);

	libvirt_validate_connections(info);

	vl = vl_get(info->vp, info->vp_count, 1);
	if (!vl)
		return 0;

	for (x = 0; x < vl->vm_count; x++) {
		callback(vl->vm_states[x].v_name,
				 vl->vm_states[x].v_uuid,
				 vl->vm_states[x].v_state.s_state, arg);

		dbg_printf(10, "[libvirt:HOSTLIST] Sent %s %s %d\n",
			vl->vm_states[x].v_name,
			vl->vm_states[x].v_uuid,
			vl->vm_states[x].v_state.s_state);
	}

	vl_free(vl);
	return 0;
}


static int
libvirt_init(backend_context_t *c, config_object_t *config)
{
	char value[256];
	struct libvirt_info *info = NULL;

	dbg_printf(5, "ENTER [%s:%d %s]\n", __FILE__, __LINE__, __FUNCTION__);

	info = calloc(1, sizeof(*info));
	if (!info)
		return -1;
	info->magic = MAGIC;
	info->config = config;

	libvirt_init_libvirt_conf(info);

	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value)) == 0)
		dset(atoi(value));

	if (info->vp_count < 1) {
		dbg_printf(1, "[libvirt:INIT] Could not connect to any hypervisors\n");
		if (info->vp)
			free(info->vp);
		free(info);
		return -1;
	}

	*c = (void *) info;
	return 0;
}


static int
libvirt_shutdown(backend_context_t c)
{
	struct libvirt_info *info = (struct libvirt_info *)c;
	int i;
	int ret = 0;

	VALIDATE(info);

	for (i = 0 ; i < info->vp_count ; i++) {
		if (virConnectClose(info->vp[i]) < 0)
			ret = -errno;
	}

	free(info->vp);
	free(info);
	return ret;
}


static fence_callbacks_t libvirt_callbacks = {
	.null = libvirt_null,
	.off = libvirt_off,
	.on = libvirt_on,
	.reboot = libvirt_reboot,
	.status = libvirt_status,
	.devstatus = libvirt_devstatus,
	.hostlist = libvirt_hostlist
};

static backend_plugin_t libvirt_plugin = {
	.name = NAME,
	.version = LIBVIRT_VERSION,
	.callbacks = &libvirt_callbacks,
	.init = libvirt_init,
	.cleanup = libvirt_shutdown,
};

double
BACKEND_VER_SYM(void)
{
	return PLUGIN_VERSION_BACKEND;
}

const backend_plugin_t *
BACKEND_INFO_SYM(void)
{
	return &libvirt_plugin;
}
