/*
  Copyright Red Hat, Inc. 2009

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
#include <config.h>
#include <stdio.h>
#include <simpleconfig.h>
#include <static_map.h>
#include <sys/types.h>
#include <stdint.h>
#include <time.h>
#include <server_plugin.h>
#include <string.h>
#include <malloc.h>
#include <syslog.h>
#include <errno.h>
#include <unistd.h>
#include <libvirt/libvirt.h>
#include <pthread.h>
#ifdef HAVE_OPENAIS_CPG_H
#include <openais/cpg.h>
#else
#ifdef HAVE_COROSYNC_CPG_H
#include <corosync/cpg.h>
#endif
#endif

#include <libcman.h>

#include <debug.h>
#include "virt.h"
#include "xvm.h"
#include "checkpoint.h"


#define NAME "checkpoint"
#define VERSION "0.8"

#define MAGIC 0x1e017afe

struct check_info {
	int magic;
	int pad;
};

#define VALIDATE(arg) \
do {\
	if (!arg || ((struct check_info *)arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)


static void *checkpoint_handle = NULL;
static virt_list_t *local_vms = NULL;
static char *uri = NULL;
static int use_uuid = 0;

static int
virt_list_update(virConnectPtr vp, virt_list_t **vl, int my_id)
{
	virt_list_t *list = NULL;
	if (*vl)
		vl_free(*vl);
	list = vl_get(vp, my_id);
	*vl = list;

	if (!list)
		return -1;
	return 0;
}


static int
node_operational(uint32_t nodeid)
{
	cman_handle_t ch;
	cman_node_t node;

	ch = cman_init(NULL);
	if (!ch)
		return -1;

	memset(&node, 0, sizeof(node));
	if (cman_get_node(ch, nodeid, &node) == 0) {
		cman_finish(ch);
		return !!node.cn_member;
	}

	cman_finish(ch);
	return 0;
}


static int
get_domain_state_ckpt(void *hp, const char *domain, vm_state_t *state)
{
	errno = EINVAL;

	if (!hp || !domain || !state || !strlen((char *)domain))
		return -1;
	if (!strcmp(DOMAIN0NAME, (char *)domain))
		return -1;

	return ckpt_read(hp, domain, state, sizeof(*state));
}


static inline int
wait_domain(const char *vm_name, virConnectPtr vp, int timeout)
{
	int tries = 0;
	int response = 1;
	int ret;
	virDomainPtr vdp;
	virDomainInfo vdi;

	if (use_uuid) {
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
		if (use_uuid) {
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



/*
   Returns: 0 - operational
            1 - dead or presumed so
            2 - VM not local and I am not the right node to deal with it
            3 - VM status unknown; cannot operate on it
 */
static int
cluster_virt_status(const char *vm_name, uint32_t *owner)
{
	vm_state_t chk_state, temp_state;
	virt_state_t *vs;
	uint32_t me, high_id;
	int ret = 0;

	dbg_printf(80, "%s %s\n", __FUNCTION__, vm_name);

	/* if we can't find the high ID, we can't do anything useful */
	if (cpg_get_ids(&me, &high_id) != 0)
		return 2;
		
	if (use_uuid) {
		vs = vl_find_uuid(local_vms, vm_name);
	} else {
		vs = vl_find_name(local_vms, vm_name);
	}

	if (!vs) {
		ret = 2; /* not found locally */
		temp_state.s_owner = 0;
		temp_state.s_state = 0;
		
		if (get_domain_state_ckpt(checkpoint_handle,
					  vm_name, &chk_state) < 0) {
			if (me == high_id) {
				dbg_printf(2, "High ID: Unknown VM\n");
				ret = 3;
				goto out;
			}
		} else if (me == chk_state.s_owner) {
			/* <UVT> If domain has disappeared completely from libvirt (i.e., destroyed)
			 we'd end up with the checkpoing section containing its last state and last owner.
			 fence_virtd will freeze at the next status call, as no one will be willing to
			 return anything but 2. So we should delete corresponding section, but only if
			 we are high_id, because otherwise we don't know if the domain hasn't been started
			 on some other node. If checkpoint states us as an owner of the domain, but we
			 don't have it, we set s_state to a special value to let high_id know about 
			 this situation. </UVT> */
			dbg_printf(2, "I am an owner of unexisting domain, mangling field\n");
			temp_state.s_owner = me;
			temp_state.s_state = -1;
			if (ckpt_write(checkpoint_handle, vm_name,
			               &temp_state, sizeof(vm_state_t)) < 0)
				dbg_printf(2, "error storing in %s\n", __FUNCTION__);
		}

		if (me != high_id)
			goto out;

		if ((chk_state.s_state == -1) || (temp_state.s_state == -1)) {
			dbg_printf(2, "I am high id and state field is mangled, removing section\n");
			ckpt_erase (checkpoint_handle, vm_name);
			ret = 1;
			goto out;
		}

		if (node_operational(chk_state.s_owner)) {
			*owner = chk_state.s_owner;
			dbg_printf(2, "High ID: Owner is operational\n");
			ret = 2;
		} else {
			dbg_printf(2, "High ID: Owner is dead; returning 'off'\n");
			ret = 1;
		}
	} else if (vs->v_state.s_state == VIR_DOMAIN_SHUTOFF) {
		ret = 1;	/* local and off */
	}

out:
	dbg_printf(80, "%s %s %d\n", __FUNCTION__, vm_name, ret);
	return ret;
}


static void
store_domains_by_name(void *hp, virt_list_t *vl)
{
	int x;

	if (!vl)
		return;

	for (x = 0; x < vl->vm_count; x++) {
		if (!strcmp(DOMAIN0NAME, vl->vm_states[x].v_name))
			continue;
		dbg_printf(2, "Storing %s\n", vl->vm_states[x].v_name);
		if (ckpt_write(hp, vl->vm_states[x].v_name, 
			   &vl->vm_states[x].v_state,
			   sizeof(vm_state_t)) < 0)
			dbg_printf(2, "error storing in %s\n", __FUNCTION__);
	}
}


static void
store_domains_by_uuid(void *hp, virt_list_t *vl)
{
	int x;

	if (!vl)
		return;

	for (x = 0; x < vl->vm_count; x++) {
		if (!strcmp(DOMAIN0UUID, vl->vm_states[x].v_uuid))
			continue;
		dbg_printf(2, "Storing %s\n", vl->vm_states[x].v_uuid);
		if (ckpt_write(hp, vl->vm_states[x].v_uuid, 
			   &vl->vm_states[x].v_state,
			   sizeof(vm_state_t)) < 0)
			dbg_printf(2, "error storing in %s\n", __FUNCTION__);
	}
}


static void
update_local_vms(void)
{
	virConnectPtr vp = NULL;
	uint32_t my_id = 0;

	cpg_get_ids(&my_id, NULL);

	vp = virConnectOpen(uri);
	if (!vp) {
		syslog(LOG_ERR, "Failed to connect to hypervisor\n");
	}
	virt_list_update(vp, &local_vms, my_id);
	vl_print(local_vms);
	if (use_uuid) 
		store_domains_by_uuid(checkpoint_handle, local_vms);
	else
		store_domains_by_name(checkpoint_handle, local_vms);
	if (vp) virConnectClose(vp);
}


/* <UVT>
 Functions do_off and do_reboot should return error only if fencing 
 was actualy unsuccessful, i.e., domain was running and is still 
 running after fencing attempt. If domain is not running after fencing
 (did not exist before or couldn't be started after), 0 should be returned 
 </UVT> */
static int
do_off(const char *vm_name)
{
	virConnectPtr vp;
	virDomainPtr vdp;
	virDomainInfo vdi;
	int ret = -1;

	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	vp = virConnectOpen(uri);
	if (!vp)
		return 1;

	if (use_uuid) {
		vdp = virDomainLookupByUUIDString(vp,
					    (const char *)vm_name);
	} else {
		vdp = virDomainLookupByName(vp, vm_name);
	}

	if (!vdp) {
		dbg_printf(2, "Nothing to do - domain does not exist\n");
		return 0;
	}

	if (((virDomainGetInfo(vdp, &vdi) == 0) &&
	     (vdi.state == VIR_DOMAIN_SHUTOFF))) {
		dbg_printf(2, "Nothing to do - domain is off\n");
		virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Destroying domain %s\n", vm_name);
	dbg_printf(2, "[OFF] Calling virDomainDestroy\n");
	ret = virDomainDestroy(vdp);
	if (ret < 0) {
		syslog(LOG_NOTICE, "Failed to destroy domain: %d\n", ret);
		printf("virDomainDestroy() failed: %d\n", ret);

		ret = 1;
		goto out;
	}

	if (ret) {
		syslog(LOG_NOTICE,
		       "Domain %s still exists; fencing failed\n",
		       vm_name);
		printf("Domain %s still exists; fencing failed\n", vm_name);

		ret = 1;
		goto out;
	}

	ret = 0;
out:
	virConnectClose(vp);
	return ret;
}


static int
do_reboot(const char *vm_name)
{
	virConnectPtr vp;
	virDomainPtr vdp, nvdp;
	virDomainInfo vdi;
	char *domain_desc;
	int ret;

	//uuid_unparse(vm_uuid, uu_string);
	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	vp = virConnectOpen(uri);
	if (!vp)
		return 1;
	
	if (use_uuid) {
		vdp = virDomainLookupByUUIDString(vp,
					    (const char *)vm_name);
	} else {
		vdp = virDomainLookupByName(vp, vm_name);
	}

	if (!vdp) {
		dbg_printf(2, "[libvirt:REBOOT] Nothing to "
			   "do - domain does not exist\n");
		return 0;
	}

	if (((virDomainGetInfo(vdp, &vdi) == 0) &&
	     (vdi.state == VIR_DOMAIN_SHUTOFF))) {
		dbg_printf(2, "[libvirt:REBOOT] Nothing to "
			   "do - domain is off\n");
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
		ret = 1;
		goto out;
	}

	ret = wait_domain(vm_name, vp, 15);

	if (ret) {
		syslog(LOG_NOTICE, "Domain %s still exists; fencing failed\n",
		       vm_name);
		printf("Domain %s still exists; fencing failed\n", vm_name);
		if (domain_desc)
			free(domain_desc);
		ret = 1;
		goto out;
	}
		
	if (!domain_desc) {
		ret = 0;
		goto out;
	}

	/* 'on' is not a failure */
	ret = 0;

	dbg_printf(3, "[[ XML Domain Info ]]\n");
	dbg_printf(3, "%s\n[[ XML END ]]\n", domain_desc);
	dbg_printf(2, "Calling virDomainCreateLinux()...\n");

	nvdp = virDomainCreateLinux(vp, domain_desc, 0);
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

out:
	virConnectClose(vp);
	return ret;
}



/*<UVT> This function must send reply from at least one node, otherwise
 requesting fence_virtd would block forever in wait_cpt_reply </UVT> */
static void
do_real_work(void *data, size_t len, uint32_t nodeid, uint32_t seqno)
{
	struct ckpt_fence_req *req = data;
	struct ckpt_fence_req reply;
	uint32_t owner;
	int ret = 1;

	memcpy(&reply, req, sizeof(reply));

	update_local_vms();

	switch(req->request) {
	case FENCE_STATUS:
		ret = cluster_virt_status(req->vm_name, &owner);
		if (ret == 3) {
			ret = RESP_OFF;
			break;
		}
		if (ret == 2) {
			return;
		}
		if (ret == 1) {
			ret = RESP_OFF;
		}
		break;
	case FENCE_OFF:
		ret = cluster_virt_status(req->vm_name, &owner);
		if (ret == 3) {
			/* No record of this VM in the checkpoint. */
			ret = 0;
			break;
		}
		if (ret == 2) {
			return;
		}
		if (ret == 1) {
			ret = 0;
			break;
		}
		/* Must be running locally to perform 'off' */
		ret = do_off(req->vm_name);
		break;
	case FENCE_REBOOT:
		ret = cluster_virt_status(req->vm_name, &owner);
		if (ret == 3) {
			ret = 0;
			break;
		}
		if (ret == 2) {
			return;
		}
		if (ret == 1) {
			ret = 0;
			break;
		}
		/* Must be running locally to perform 'reboot' */
		ret = do_reboot(req->vm_name);
		break;
	}

	reply.response = ret;

	cpg_send_reply(&reply, sizeof(reply), nodeid, seqno);
}


static int
do_request(const char *vm_name, int request, uint32_t seqno)
{
	struct ckpt_fence_req freq, *frp;
	size_t retlen;
	uint32_t seq;
	int ret;

	memset(&freq, 0, sizeof(freq));
	snprintf(freq.vm_name, sizeof(freq.vm_name), vm_name);
	freq.request = request;
	freq.seqno = seqno;

	if (cpg_send_req(&freq, sizeof(freq), &seq) != 0) {
		printf("Failed to send\n");
		return 1;
	}

	if (cpg_wait_reply((void *)&frp, &retlen, seq) != 0) {
		printf("Failed to receive\n");
		return 1;
	}

	ret = frp->response;
	free(frp);

	return ret;
}


static int
checkpoint_null(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] Null operation on %s\n", vm_name);

	return 1;
}


static int
checkpoint_off(const char *vm_name, const char *src,
	       uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] OFF operation on %s seq %d\n", vm_name, seqno);

	return do_request(vm_name, FENCE_OFF, seqno);
}


static int
checkpoint_on(const char *vm_name, const char *src,
	      uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] ON operation on %s seq %d\n", vm_name, seqno);

	return 1;
}


static int
checkpoint_devstatus(void *priv)
{
	printf("[CKPT] Device status\n");
	VALIDATE(priv);

	return 0;
}


static int
checkpoint_status(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] STATUS operation on %s\n", vm_name);

	return do_request(vm_name, FENCE_STATUS, 0);
}


static int
checkpoint_reboot(const char *vm_name, const char *src,
		  uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] REBOOT operation on %s seq %d\n", vm_name, seqno);

	return do_request(vm_name, FENCE_REBOOT, 0);
}


static int
checkpoint_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] HOSTLIST operation\n");

	return 1;
}


static int
checkpoint_init(backend_context_t *c, config_object_t *config)
{
	char value[1024];
	struct check_info *info = NULL;
	int x;

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

	if (sc_get(config, "backends/checkpoint/@uri",
		   value, sizeof(value)) == 0) {
		if (uri)
			free(uri);
		uri = strdup(value);
		if (!uri) {
			free(info);
			return -1;
		}
		dbg_printf(1, "Using %s\n", uri);
	}

	/* Naming scheme is no longer a top-level config option.
	 * However, we retain it here for configuration compatibility with
	 * versions 0.1.3 and previous.
	 */
	if (sc_get(config, "fence_virtd/@name_mode",
		   value, sizeof(value)-1) == 0) {

		dbg_printf(1, "Got %s for name_mode\n", value);
		if (!strcasecmp(value, "uuid")) {
			use_uuid = 1;
		} else if (!strcasecmp(value, "name")) {
			use_uuid = 0;
		} else {
			dbg_printf(1, "Unsupported name_mode: %s\n", value);
		}
	}

	if (sc_get(config, "backends/checkpoint/@name_mode",
		   value, sizeof(value)-1) == 0) {

		dbg_printf(1, "Got %s for name_mode\n", value);
		if (!strcasecmp(value, "uuid")) {
			use_uuid = 1;
		} else if (!strcasecmp(value, "name")) {
			use_uuid = 0;
		} else {
			dbg_printf(1, "Unsupported name_mode: %s\n", value);
		}
	}

	if (cpg_start(PACKAGE_NAME, do_real_work) < 0) {
		return -1;
	}
	info = malloc(sizeof(*info));
	if (!info)
		return -1;

	memset(info, 0, sizeof(*info));

	info->magic = MAGIC;

	x = 0;
	while ((checkpoint_handle = ckpt_init(
			"vm_states", 262144, 4096, 64, 10
					      )) == NULL) {
		if (!x) {
			dbg_printf(1, "Could not initialize "
				   "saCkPt; retrying...\n");
			x = 1;
		}
		sleep(3);
	}
	if (x)
		dbg_printf(1, "Checkpoint initialized\n");

	update_local_vms();

	*c = (void *)info;
	return 0;
}


static int
checkpoint_shutdown(backend_context_t c)
{
	struct check_info *info = (struct check_info *)c;

	VALIDATE(info);
	info->magic = 0;
	free(info);

	cpg_stop();

	return 0;
}


static fence_callbacks_t checkpoint_callbacks = {
	.null = checkpoint_null,
	.off = checkpoint_off,
	.on = checkpoint_on,
	.reboot = checkpoint_reboot,
	.status = checkpoint_status,
	.devstatus = checkpoint_devstatus,
	.hostlist = checkpoint_hostlist
};

static backend_plugin_t checkpoint_plugin = {
	.name = NAME,
	.version = VERSION,
	.callbacks = &checkpoint_callbacks,
	.init = checkpoint_init,
	.cleanup = checkpoint_shutdown,
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
	return &checkpoint_plugin;
}
#else
static void __attribute__((constructor))
checkpoint_register_plugin(void)
{
	plugin_reg_backend(&checkpoint_plugin);
}
#endif
