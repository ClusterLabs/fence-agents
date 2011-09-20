/*
  Copyright Red Hat, Inc. 2006

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
#include "libcman.h"
#include "debug.h"
#include "uuid-test.h"


#define NAME "libvirt"
#define VERSION "0.1"

#define MAGIC 0x1e19317a

struct libvirt_info {
	int magic;
	virConnectPtr vp;
};

#define VALIDATE(arg) \
do {\
	if (!arg || ((struct libvirt_info *)arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)


static inline int
wait_domain(const char *vm_name, virConnectPtr vp,
	    int timeout)
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
			vdp = virDomainLookupByUUIDString(vp,
					(const char *)vm_name);
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
		
		dbg_printf(4, "Domain still exists (state %d) "
			   "after %d seconds\n",
			   vdi.state, tries);
	} while (1);

	return response;
}


static int
libvirt_null(const char *vm_name, void *priv)
{
	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	printf("NULL operation: returning failure\n");
	return 1;
}


static int
libvirt_off(const char *vm_name, const char *src,
	    uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	virDomainPtr vdp;
	virDomainInfo vdi;
	int ret = -1;

	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	VALIDATE(info);

	if (is_uuid(vm_name)) {
		vdp = virDomainLookupByUUIDString(info->vp,
					    (const char *)vm_name);
	} else {
		vdp = virDomainLookupByName(info->vp, vm_name);
	}

	if (!vdp ||
	    ((virDomainGetInfo(vdp, &vdi) == 0) &&
	     (vdi.state == VIR_DOMAIN_SHUTOFF))) {
		dbg_printf(2, "Nothing to do - domain does not exist\n");

		if (vdp)
			virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Destroying domain %s\n", vm_name);
	dbg_printf(2, "[OFF] Calling virDomainDestroy\n");
	ret = virDomainDestroy(vdp);
	if (ret < 0) {
		syslog(LOG_NOTICE, "Failed to destroy domain: %d\n", ret);
		printf("virDomainDestroy() failed: %d\n", ret);
		return 1;
	}

	if (ret) {
		syslog(LOG_NOTICE,
		       "Domain %s still exists; fencing failed\n",
		       vm_name);
		printf("Domain %s still exists; fencing failed\n", vm_name);
		return 1;
	}

	return 0;
}


static int
libvirt_on(const char *vm_name, const char *src,
	   uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	virDomainPtr vdp;
	virDomainInfo vdi;
	int ret = -1;

	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	VALIDATE(info);

	if (is_uuid(vm_name)) {
		vdp = virDomainLookupByUUIDString(info->vp,
					    (const char *)vm_name);
	} else {
		vdp = virDomainLookupByName(info->vp, vm_name);
	}

	if (vdp &&
	    ((virDomainGetInfo(vdp, &vdi) == 0) &&
	     (vdi.state != VIR_DOMAIN_SHUTOFF))) {
		dbg_printf(2, "Nothing to do - domain is running\n");

		if (vdp)
			virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Starting domain %s\n", vm_name);
	dbg_printf(2, "[ON] Calling virDomainCreate\n");
	ret = virDomainCreate(vdp);
	if (ret < 0) {
		syslog(LOG_NOTICE, "Failed to start domain: %d\n", ret);
		printf("virDomainCreate() failed: %d\n", ret);
		return 1;
	}

	if (ret) {
		syslog(LOG_NOTICE,
		       "Domain %s did not start\n",
		       vm_name);
		printf("Domain %s did not start\n", vm_name);
		return 1;
	}
	syslog(LOG_NOTICE, "Domain %s started\n", vm_name);

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
	virDomainPtr vdp;
	virDomainInfo vdi;
	int ret = 0;

	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	VALIDATE(info);

	if (is_uuid(vm_name)) {
		vdp = virDomainLookupByUUIDString(info->vp,
					    (const char *)vm_name);
	} else {
		vdp = virDomainLookupByName(info->vp, vm_name);
	}

	if (!vdp || ((virDomainGetInfo(vdp, &vdi) == 0) &&
	     (vdi.state == VIR_DOMAIN_SHUTOFF))) {
		ret = RESP_OFF;
	}

	if (vdp)
		virDomainFree(vdp);
	return ret;
}


static int
libvirt_reboot(const char *vm_name, const char *src,
	       uint32_t seqno, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	virDomainPtr vdp, nvdp;
	virDomainInfo vdi;
	char *domain_desc;
	int ret;

	//uuid_unparse(vm_uuid, uu_string);
	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	VALIDATE(info);
	
	if (is_uuid(vm_name)) {
		vdp = virDomainLookupByUUIDString(info->vp,
					    (const char *)vm_name);
	} else {
		vdp = virDomainLookupByName(info->vp, vm_name);
	}

	if (!vdp || ((virDomainGetInfo(vdp, &vdi) == 0) &&
	     (vdi.state == VIR_DOMAIN_SHUTOFF))) {
		dbg_printf(2, "[libvirt:REBOOT] Nothing to "
			   "do - domain does not exist\n");
		if (vdp)
			virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Rebooting domain %s\n", vm_name);
	printf("Rebooting domain %s...\n", vm_name);
	domain_desc = virDomainGetXMLDesc(vdp, 0);

	if (!domain_desc) {
		printf("Failed getting domain description from "
		       "libvirt\n");
	}

	dbg_printf(2, "[REBOOT] Calling virDomainDestroy(%p)\n", vdp);
	ret = virDomainDestroy(vdp);
	if (ret < 0) {
		printf("virDomainDestroy() failed: %d/%d\n", ret, errno);
		free(domain_desc);
		virDomainFree(vdp);
		return 1;
	}

	ret = wait_domain(vm_name, info->vp, 15);

	if (ret) {
		syslog(LOG_NOTICE, "Domain %s still exists; fencing failed\n",
		       vm_name);
		printf("Domain %s still exists; fencing failed\n", vm_name);
		if (domain_desc)
			free(domain_desc);
		return 1;
	}
		
	if (!domain_desc)
		return 0;

	/* 'on' is not a failure */
	ret = 0;

	dbg_printf(3, "[[ XML Domain Info ]]\n");
	dbg_printf(3, "%s\n[[ XML END ]]\n", domain_desc);
	dbg_printf(2, "Calling virDomainCreateLinux()...\n");

	nvdp = virDomainCreateLinux(info->vp, domain_desc, 0);
	if (nvdp == NULL) {
		/* More recent versions of libvirt or perhaps the
		 * KVM back-end do not let you create a domain from
		 * XML if there is already a defined domain description
		 * with the same name that it knows about.  You must
		 * then call virDomainCreate() */
		dbg_printf(2, "Failed; Trying virDomainCreate()...\n");
		if (virDomainCreate(vdp) < 0) {
			syslog(LOG_NOTICE,
			       "Could not restart %s\n",
			       vm_name);
			dbg_printf(1, "Failed to recreate guest"
				   " %s!\n", vm_name);
		}
	}

	free(domain_desc);

	return ret;
}


static int
libvirt_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	struct libvirt_info *info = (struct libvirt_info *)priv;
	virt_list_t *vl;
	int x;

	dbg_printf(5, "%s\n", __FUNCTION__);
	VALIDATE(info);

	vl = vl_get(info->vp, 1);
	if (!vl)
		return 1;

	for (x = 0; x < vl->vm_count; x++) {
		dbg_printf(10, "Sending %s\n", vl->vm_states[x].v_uuid);
		callback(vl->vm_states[x].v_name,
			 vl->vm_states[x].v_uuid,
			 vl->vm_states[x].v_state.s_state, arg);
	}

	vl_free(vl);

	return 0;
}


static int
libvirt_init(backend_context_t *c, config_object_t *config)
{
	virConnectPtr vp;
	char value[256];
	struct libvirt_info *info = NULL;
	char *uri = NULL;

	info = malloc(sizeof(*info));
	if (!info)
		return -1;

	dbg_printf(5, "[%s:%d %s]\n", __FILE__, __LINE__, __FUNCTION__);
	memset(info, 0, sizeof(*info));

#ifdef _MODULE
	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value))==0)
		dset(atoi(value));
#endif

	if (sc_get(config, "backends/libvirt/@uri",
		   value, sizeof(value)) == 0) {
		uri = strdup(value);
		if (!uri) {
			free(info);
			return -1;
		}
		dbg_printf(1, "Using %s\n", uri);
	}

	/* We don't need to store the URI; we only use it once */
	vp = virConnectOpen(uri);
	if (!vp) {
		free(uri);
		free(info);
		return -1;
	}
	free(uri);

	info->magic = MAGIC;
	info->vp = vp;

	*c = (void *)info;
	return 0;
}


static int
libvirt_shutdown(backend_context_t c)
{
	struct libvirt_info *info = (struct libvirt_info *)c;

	VALIDATE(info);

	if (virConnectClose(info->vp) < 0) {
		free(info);
		return -errno;
	}

	free(info);
	return 0;
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
