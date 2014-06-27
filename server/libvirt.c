/*
  Copyright Red Hat, Inc. 2006-2014

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
#include <simpleconfig.h>
#include <static_map.h>

#include <server_plugin.h>

/* Local includes */
#include "xvm.h"
#include "simple_auth.h"
#include "options.h"
#include "mcast.h"
#include "tcp.h"
#include "virt.h"
#include "debug.h"
#include "uuid-test.h"


#define NAME "libvirt"
#define VERSION "0.1"

#define MAGIC 0x1e19317a

struct libvirt_info {
	int magic;
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


static inline int
wait_domain(const char *vm_name, virConnectPtr vp, int timeout)
{
	int tries = 0;
	int response = 1;
	int ret;
	virDomainPtr vdp;
	virDomainInfo vdi;
	int uuid_check;

	uuid_check = is_uuid(vm_name);

	if (uuid_check) {
		vdp = virDomainLookupByUUIDString(vp, (const char *)vm_name);
	} else {
		vdp = virDomainLookupByName(vp, vm_name);
	}
	if (!vdp)
		return 0;

	/* Check domain liveliness.  If the domain is still here,
	   we return failure, and the client must then retry */
	/* XXX On the xen 3.0.4 API, we will be able to guarantee
	   synchronous virDomainDestroy, so this check will not
	   be necessary */
	do {
		if (++tries > timeout)
			break;

		sleep(1);
		if (uuid_check) {
			vdp = virDomainLookupByUUIDString(vp, (const char *)vm_name);
		} else {
			vdp = virDomainLookupByName(vp, vm_name);
		}
		if (!vdp) {
			dbg_printf(2, "Domain no longer exists\n");
			response = 0;
			break;
		}

		memset(&vdi, 0, sizeof(vdi));
		ret = virDomainGetInfo(vdp, &vdi);
		virDomainFree(vdp);
		if (ret < 0)
			continue;

		if (vdi.state == VIR_DOMAIN_SHUTOFF) {
			dbg_printf(2, "Domain has been shut off\n");
			response = 0;
			break;
		}

		dbg_printf(4, "Domain still exists (state %d) after %d seconds\n",
			vdi.state, tries);
	} while (1);

	return response;
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
	virDomainPtr vdp = NULL;
	virDomainInfo vdi;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);
	int ret = -1;
	int i;

	dbg_printf(5, "ENTER %s %s %u\n", __FUNCTION__, vm_name, seqno);
	VALIDATE(info);

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < info->vp_count ; i++) {
		vdp = virt_lookup_fn(info->vp[i], vm_name);
		if (vdp)
			break;
	}

	if (!vdp) {
		dbg_printf(2, "[libvirt:OFF] Domain %s does not exist\n", vm_name);
		return 1;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state == VIR_DOMAIN_SHUTOFF) {
		dbg_printf(2, "[libvirt:OFF] Nothing to do - "
			"domain %s is already off\n",
			vm_name);
		virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Destroying domain %s\n", vm_name);
	dbg_printf(2, "[libvirt:OFF] Calling virDomainDestroy for %s\n", vm_name);

	ret = virDomainDestroy(vdp);
	virDomainFree(vdp);

	if (ret < 0) {
		syslog(LOG_NOTICE, "Failed to destroy domain %s: %d\n", vm_name, ret);
		dbg_printf(2, "[libvirt:OFF] Failed to destroy domain: %s %d\n",
			vm_name, ret);
		return 1;
	}

	if (ret) {
		syslog(LOG_NOTICE, "Domain %s still exists; fencing failed\n", vm_name);
		dbg_printf(2, "[libvirt:OFF] Domain %s still exists; fencing failed\n",
			vm_name);
		return 1;
	}

	dbg_printf(2, "[libvirt:OFF] Success for %s\n", vm_name);
	return 0;
}


static int
libvirt_on(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	virDomainPtr vdp = NULL;
	virDomainInfo vdi;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);
	int ret = -1;
	int i;

	dbg_printf(5, "ENTER %s %s %u\n", __FUNCTION__, vm_name, seqno);
	VALIDATE(info);

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < info->vp_count ; i++) {
		vdp = virt_lookup_fn(info->vp[i], vm_name);
		if (vdp)
			break;
	}

	if (!vdp) {
		dbg_printf(2, "[libvirt:ON] Domain %s does not exist\n", vm_name);
		return 1;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state != VIR_DOMAIN_SHUTOFF) {
		dbg_printf(2, "Nothing to do - domain %s is already running\n",
			vm_name);
		virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Starting domain %s\n", vm_name);
	dbg_printf(2, "[libvirt:ON] Calling virDomainCreate for %s\n", vm_name);

	ret = virDomainCreate(vdp);
	virDomainFree(vdp);

	if (ret < 0) {
		syslog(LOG_NOTICE, "Failed to start domain %s: %d\n", vm_name, ret);
		dbg_printf(2, "[libvirt:ON] virDomainCreate() failed for %s: %d\n",
			vm_name, ret);
		return 1;
	}

	if (ret) {
		syslog(LOG_NOTICE, "Domain %s did not start\n", vm_name);
		dbg_printf(2, "[libvirt:ON] Domain %s did not start\n", vm_name);
		return 1;
	}

	syslog(LOG_NOTICE, "Domain %s started\n", vm_name);
	dbg_printf(2, "[libvirt:ON] Success for %s\n", vm_name);
	return 0;
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
	virDomainPtr vdp = NULL;
	virDomainInfo vdi;
	int ret = 0;
	int i;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);

	dbg_printf(5, "ENTER %s %s\n", __FUNCTION__, vm_name);
	VALIDATE(info);

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < info->vp_count ; i++) {
		vdp = virt_lookup_fn(info->vp[i], vm_name);
		if (vdp)
			break;
	}

	if (!vdp) {
		dbg_printf(2, "[libvirt:STATUS] Unknown VM %s - return OFF\n", vm_name);
		return RESP_OFF;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state == VIR_DOMAIN_SHUTOFF) {
		dbg_printf(2, "[libvirt:STATUS] VM %s is OFF\n", vm_name);
		ret = RESP_OFF;
	}

	if (vdp)
		virDomainFree(vdp);
	return ret;
}


static int
libvirt_reboot(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	virDomainPtr vdp = NULL, nvdp;
	virDomainInfo vdi;
	char *domain_desc;
	virConnectPtr vcp = NULL;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);
	int ret;
	int i;

	dbg_printf(5, "ENTER %s %s %u\n", __FUNCTION__, vm_name, seqno);
	VALIDATE(info);

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < info->vp_count ; i++) {
		vdp = virt_lookup_fn(info->vp[i], vm_name);
		if (vdp) {
			vcp = info->vp[i];
			break;
		}
	}

	if (!vdp || !vcp) {
		dbg_printf(2,
			"[libvirt:REBOOT] Nothing to do - domain %s does not exist\n",
			vm_name);
		return 1;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state == VIR_DOMAIN_SHUTOFF) {
		dbg_printf(2, "[libvirt:REBOOT] Nothing to do - domain %s is off\n",
			vm_name);
		virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Rebooting domain %s\n", vm_name);
	dbg_printf(5, "[libvirt:REBOOT] Rebooting domain %s...\n", vm_name);

	domain_desc = virDomainGetXMLDesc(vdp, 0);

	if (!domain_desc) {
		dbg_printf(5, "[libvirt:REBOOT] Failed getting domain description "
			"from libvirt for %s...\n", vm_name);
	}

	dbg_printf(2, "[libvirt:REBOOT] Calling virDomainDestroy(%p) for %s\n",
		vdp, vm_name);

	ret = virDomainDestroy(vdp);
	if (ret < 0) {
		dbg_printf(2,
			"[libvirt:REBOOT] virDomainDestroy() failed for %s: %d/%d\n",
			vm_name, ret, errno);

		if (domain_desc)
			free(domain_desc);
		virDomainFree(vdp);
		return 1;
	}

	ret = wait_domain(vm_name, vcp, 15);

	if (ret) {
		syslog(LOG_NOTICE, "Domain %s still exists; fencing failed\n", vm_name);
		dbg_printf(2,
			"[libvirt:REBOOT] Domain %s still exists; fencing failed\n",
			vm_name);

		if (domain_desc)
			free(domain_desc);
		virDomainFree(vdp);
		return 1;
	}

	if (!domain_desc)
		return 0;

	/* 'on' is not a failure */
	ret = 0;

	dbg_printf(3, "[[ XML Domain Info ]]\n");
	dbg_printf(3, "%s\n[[ XML END ]]\n", domain_desc);

	dbg_printf(2, "[libvirt:REBOOT] Calling virDomainCreateLinux() for %s\n",
		vm_name);

	nvdp = virDomainCreateLinux(vcp, domain_desc, 0);
	if (nvdp == NULL) {
		/* More recent versions of libvirt or perhaps the
		 * KVM back-end do not let you create a domain from
		 * XML if there is already a defined domain description
		 * with the same name that it knows about.  You must
		 * then call virDomainCreate() */
		dbg_printf(2,
			"[libvirt:REBOOT] virDomainCreateLinux() failed for %s; "
			"Trying virDomainCreate()\n",
			vm_name);

		if (virDomainCreate(vdp) < 0) {
			syslog(LOG_NOTICE, "Could not restart %s\n", vm_name);
			dbg_printf(1, "[libvirt:REBOOT] Failed to recreate guest %s!\n",
				vm_name);
		}
	}

	free(domain_desc);
	virDomainFree(vdp);
	return ret;
}


static int
libvirt_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	int i;

	dbg_printf(5, "ENTER %s\n", __FUNCTION__);
	VALIDATE(info);

	for (i = 0 ; i < info->vp_count ; i++) {
		int x;
		virt_list_t *vl;

		vl = vl_get(info->vp[i], 1);
		if (!vl)
			continue;

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
	}

	return 0;
}


static int
libvirt_init(backend_context_t *c, config_object_t *config)
{
	virConnectPtr vp;
	char value[256];
	struct libvirt_info *info = NULL;
	int i = 0;

	info = malloc(sizeof(*info));
	if (!info)
		return -1;

	dbg_printf(5, "ENTER [%s:%d %s]\n", __FILE__, __LINE__, __FUNCTION__);
	memset(info, 0, sizeof(*info));

#ifdef _MODULE
	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value)) == 0)
		dset(atoi(value));
#endif

	do {
		virConnectPtr *vpl = NULL;
		char conf_attr[256];
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

	if (info->vp_count < 1) {
		dbg_printf(1, "[libvirt:INIT] Could not connect to any hypervisors\n");
		if (info->vp)
			free(info->vp);
		free(info);
		return -1;
	}

	info->magic = MAGIC;

	*c = (void *)info;
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
	.version = VERSION,
	.callbacks = &libvirt_callbacks,
	.init = libvirt_init,
	.cleanup = libvirt_shutdown,
};


#ifdef _MODULE
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
#else
static void __attribute__((constructor))
libvirt_register_plugin(void)
{
	plugin_reg_backend(&libvirt_plugin);
}
#endif
