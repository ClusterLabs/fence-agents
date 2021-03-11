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

#include "config.h"

#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdlib.h>
#include <libvirt/libvirt.h>
#include <string.h>
#include <malloc.h>
#include <stdint.h>
#include <errno.h>
#include <syslog.h>

#include "debug.h"
#include "uuid-test.h"
#include "virt.h"

static int
_compare_virt(const void *_left, const void *_right)
{
	virt_state_t *left = (virt_state_t *)_left,
		     *right = (virt_state_t *)_right;

	return strcasecmp(left->v_name, right->v_name);
}


static void
_free_dom_list(virDomainPtr *dom_list, int len) {
	int x;

	if (!dom_list || len <= 0)
		return;
	for (x = 0 ; x < len; x++)
		virDomainFree(dom_list[x]);

	free(dom_list);
}


virt_list_t *vl_get(virConnectPtr *vp, int vp_count, int my_id)
{
	virt_list_t *vl = NULL;
	int d_count = 0;
	int i;

	errno = EINVAL;
	if (!vp || vp_count < 1)
		return NULL;

	for (i = 0 ; i < vp_count ; i++) {
		int x;
		virDomainPtr *dom_list;
		virt_list_t *new_vl;

		int ret = virConnectListAllDomains(vp[i], &dom_list, 0);
		if (ret == 0)
			continue;

		if (ret < 0) {
			int saved_errno = errno;
			dbg_printf(2, "Error: virConnectListAllDomains: %d %d\n",
				ret, saved_errno);
			if (vl)
				free(vl);
			errno = saved_errno;
			return NULL;
		}

		d_count += ret;
		new_vl = realloc(vl, sizeof(uint32_t) + sizeof(virt_state_t) * d_count);
		if (!new_vl) {
			_free_dom_list(dom_list, ret);
			free(vl);
			return NULL;
		}
		vl = new_vl;
		vl->vm_count = d_count;

		/* Ok, we have the domain IDs - let's get their names and states */
		for (x = 0; x < ret; x++) {
			char *d_name;
			virDomainInfo d_info;
			char d_uuid[MAX_DOMAINNAME_LENGTH];
			virDomainPtr dom = dom_list[x];

			if (!(d_name = (char *)virDomainGetName(dom))) {
				_free_dom_list(dom_list, ret);
				free(vl);
				return NULL;
			}

			if (virDomainGetUUIDString(dom, d_uuid) != 0) {
				_free_dom_list(dom_list, ret);
				free(vl);
				return NULL;
			}

			if (virDomainGetInfo(dom, &d_info) < 0) {
				_free_dom_list(dom_list, ret);
				free(vl);
				return NULL;
			}

			/* Store the name & state */
			strncpy(vl->vm_states[x].v_name, d_name, MAX_DOMAINNAME_LENGTH);
			strncpy(vl->vm_states[x].v_uuid, d_uuid, MAX_DOMAINNAME_LENGTH);
			vl->vm_states[x].v_state.s_state = d_info.state;
			vl->vm_states[x].v_state.s_owner = my_id;
		}

		_free_dom_list(dom_list, ret);
	}
	/* No domains found */
	if (!vl)
		return NULL;

	/* We have all the locally running domains & states now */
	/* Sort */
	qsort(&vl->vm_states[0], vl->vm_count, sizeof(vl->vm_states[0]),
	      _compare_virt);
	return vl;	
}

int
vl_add(virt_list_t **vl, virt_state_t *vm) {
	virt_list_t *new_vl;
	size_t oldlen;
	size_t newlen;

	if (!vl)
		return -1;

	if (!*vl) {
		*vl = malloc(sizeof(uint32_t) + sizeof(virt_state_t));
		if (!*vl)
			return -1;
		(*vl)->vm_count = 1;
		memcpy(&(*vl)->vm_states[0], vm, sizeof(virt_state_t));
		return 0;
	}

	oldlen = sizeof(uint32_t) + sizeof(virt_state_t) * (*vl)->vm_count;
	newlen = oldlen + sizeof(virt_state_t);

	new_vl = malloc(newlen);
	if (!new_vl)
		return -1;

	memcpy(new_vl, *vl, oldlen);
	memcpy(&new_vl->vm_states[(*vl)->vm_count], vm, sizeof(virt_state_t));
	new_vl->vm_count++;

	free(*vl);
	*vl = new_vl;
	return 0;
}

int vl_remove_by_owner(virt_list_t **vl, uint32_t owner) {
	int i;
	int removed = 0;
	virt_list_t *new_vl;

	if (!vl || !*vl)
		return 0;

	for (i = 0 ; i < (*vl)->vm_count ; i++) {
		if ((*vl)->vm_states[i].v_state.s_owner == owner) {
			dbg_printf(2, "Removing %s\n", (*vl)->vm_states[i].v_name);
			memset(&(*vl)->vm_states[i].v_state, 0,
				sizeof((*vl)->vm_states[i].v_state));
			(*vl)->vm_states[i].v_name[0] = 0xff;
			(*vl)->vm_states[i].v_uuid[0] = 0xff;
			removed++;
		}
	}

	if (!removed)
		return 0;

	qsort(&(*vl)->vm_states[0], (*vl)->vm_count, sizeof((*vl)->vm_states[0]),
	      _compare_virt);
	(*vl)->vm_count -= removed;

	new_vl = realloc(*vl, sizeof(uint32_t) + (sizeof(virt_state_t) * ((*vl)->vm_count)));
	if (new_vl)
		*vl = new_vl;
	return removed;
}


int
vl_update(virt_list_t **vl, virt_state_t *vm) {
	virt_state_t *v = NULL;

	if (!vl)
		return -1;

	if (!*vl)
		return vl_add(vl, vm);

	if (strlen(vm->v_uuid) > 0)
		v = vl_find_uuid(*vl, vm->v_uuid);

	if (v == NULL && strlen(vm->v_name) > 0)
		v = vl_find_name(*vl, vm->v_name);

	if (v == NULL) {
		dbg_printf(2, "Adding new entry for VM %s\n", vm->v_name);
		vl_add(vl, vm);
	} else {
		dbg_printf(2, "Updating entry for VM %s\n", vm->v_name);
		memcpy(&v->v_state, &vm->v_state, sizeof(v->v_state));
	}

	return 0;
}


void
vl_print(virt_list_t *vl)
{
	int x;

	printf("%-24.24s %-36.36s %-5.5s %-5.5s\n", "Domain", "UUID",
	       "Owner", "State");
	printf("%-24.24s %-36.36s %-5.5s %-5.5s\n", "------", "----",
	       "-----", "-----");

	if (!vl || !vl->vm_count)
		return;

	for (x = 0; x < vl->vm_count; x++) {
		printf("%-24.24s %-36.36s %-5.5d %-5.5d\n",
		       vl->vm_states[x].v_name,
		       vl->vm_states[x].v_uuid,
		       vl->vm_states[x].v_state.s_owner,
		       vl->vm_states[x].v_state.s_state);
	}
}


virt_state_t *
vl_find_name(virt_list_t *vl, const char *name)
{
	int x;

	if (!vl || !name || !vl->vm_count)
		return NULL;

	for (x = 0; x < vl->vm_count; x++) {
		if (!strcasecmp(vl->vm_states[x].v_name, name))
			return &vl->vm_states[x];
	}

	return NULL;
}


virt_state_t *
vl_find_uuid(virt_list_t *vl, const char *uuid)
{
	int x;

	if (!vl || !uuid || !vl->vm_count)
		return NULL;

	for (x = 0; x < vl->vm_count; x++) {
		if (!strcasecmp(vl->vm_states[x].v_uuid, uuid))
			return &vl->vm_states[x];
	}

	return NULL;
}


void
vl_free(virt_list_t *old)
{
	free(old);
}


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


int
vm_off(virConnectPtr *vp, int vp_count, const char *vm_name)
{
	virDomainPtr vdp = NULL;
	virDomainInfo vdi;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);
	int ret = -1;
	int i;

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < vp_count ; i++) {
		vdp = virt_lookup_fn(vp[i], vm_name);
		if (vdp)
			break;
	}

	if (!vdp) {
		dbg_printf(2, "[virt:OFF] Domain %s does not exist\n", vm_name);
		return 1;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state == VIR_DOMAIN_SHUTOFF)
	{
		dbg_printf(2, "[virt:OFF] Nothing to do - "
			"domain %s is already off\n",
			vm_name);
		virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Destroying domain %s\n", vm_name);
	dbg_printf(2, "[virt:OFF] Calling virDomainDestroy for %s\n", vm_name);

	ret = virDomainDestroy(vdp);
	virDomainFree(vdp);

	if (ret < 0) {
		syslog(LOG_NOTICE,
			"Failed to destroy domain %s: %d\n", vm_name, ret);
		dbg_printf(2, "[virt:OFF] Failed to destroy domain: %s %d\n",
			vm_name, ret);
		return 1;
	}

	if (ret) {
		syslog(LOG_NOTICE, "Domain %s still exists; fencing failed\n",
			vm_name);
		dbg_printf(2,
			"[virt:OFF] Domain %s still exists; fencing failed\n",
			vm_name);
		return 1;
	}

	dbg_printf(2, "[virt:OFF] Success for %s\n", vm_name);
	return 0;
}


int
vm_on(virConnectPtr *vp, int vp_count, const char *vm_name)
{
	virDomainPtr vdp = NULL;
	virDomainInfo vdi;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);
	int ret = -1;
	int i;

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < vp_count ; i++) {
		vdp = virt_lookup_fn(vp[i], vm_name);
		if (vdp)
			break;
	}

	if (!vdp) {
		dbg_printf(2, "[virt:ON] Domain %s does not exist\n", vm_name);
		return 1;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state != VIR_DOMAIN_SHUTOFF) {
		dbg_printf(2, "Nothing to do - domain %s is already running\n",
			vm_name);
		virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Starting domain %s\n", vm_name);
	dbg_printf(2, "[virt:ON] Calling virDomainCreate for %s\n", vm_name);

	ret = virDomainCreate(vdp);
	virDomainFree(vdp);

	if (ret < 0) {
		syslog(LOG_NOTICE, "Failed to start domain %s: %d\n", vm_name, ret);
		dbg_printf(2, "[virt:ON] virDomainCreate() failed for %s: %d\n",
			vm_name, ret);
		return 1;
	}

	if (ret) {
		syslog(LOG_NOTICE, "Domain %s did not start\n", vm_name);
		dbg_printf(2, "[virt:ON] Domain %s did not start\n", vm_name);
		return 1;
	}

	syslog(LOG_NOTICE, "Domain %s started\n", vm_name);
	dbg_printf(2, "[virt:ON] Success for %s\n", vm_name);
	return 0;
}


int
vm_status(virConnectPtr *vp, int vp_count, const char *vm_name)
{
	virDomainPtr vdp = NULL;
	virDomainInfo vdi;
	int ret = 0;
	int i;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < vp_count ; i++) {
		vdp = virt_lookup_fn(vp[i], vm_name);
		if (vdp)
			break;
	}

	if (!vdp) {
		dbg_printf(2, "[virt:STATUS] Unknown VM %s - return OFF\n", vm_name);
		return RESP_OFF;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state == VIR_DOMAIN_SHUTOFF) {
		dbg_printf(2, "[virt:STATUS] VM %s is OFF\n", vm_name);
		ret = RESP_OFF;
	}

	if (vdp)
		virDomainFree(vdp);
	return ret;
}


int
vm_reboot(virConnectPtr *vp, int vp_count, const char *vm_name)
{
	virDomainPtr vdp = NULL, nvdp;
	virDomainInfo vdi;
	char *domain_desc;
	virConnectPtr vcp = NULL;
	virDomainPtr (*virt_lookup_fn)(virConnectPtr, const char *);
	int ret;
	int i;

	if (is_uuid(vm_name))
		virt_lookup_fn = virDomainLookupByUUIDString;
	else
		virt_lookup_fn = virDomainLookupByName;

	for (i = 0 ; i < vp_count ; i++) {
		vdp = virt_lookup_fn(vp[i], vm_name);
		if (vdp) {
			vcp = vp[i];
			break;
		}
	}

	if (!vdp || !vcp) {
		dbg_printf(2,
			"[virt:REBOOT] Nothing to do - domain %s does not exist\n",
			vm_name);
		return 1;
	}

	if (virDomainGetInfo(vdp, &vdi) == 0 && vdi.state == VIR_DOMAIN_SHUTOFF) {
		dbg_printf(2, "[virt:REBOOT] Nothing to do - domain %s is off\n",
			vm_name);
		virDomainFree(vdp);
		return 0;
	}

	syslog(LOG_NOTICE, "Rebooting domain %s\n", vm_name);
	dbg_printf(5, "[virt:REBOOT] Rebooting domain %s...\n", vm_name);

	domain_desc = virDomainGetXMLDesc(vdp, 0);

	if (!domain_desc) {
		dbg_printf(5, "[virt:REBOOT] Failed getting domain description "
			"from libvirt for %s...\n", vm_name);
	}

	dbg_printf(2, "[virt:REBOOT] Calling virDomainDestroy(%p) for %s\n",
		vdp, vm_name);

	ret = virDomainDestroy(vdp);
	if (ret < 0) {
		dbg_printf(2,
			"[virt:REBOOT] virDomainDestroy() failed for %s: %d/%d\n",
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
			"[virt:REBOOT] Domain %s still exists; fencing failed\n",
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

	dbg_printf(2, "[virt:REBOOT] Calling virDomainCreateLinux() for %s\n",
		vm_name);

	nvdp = virDomainCreateLinux(vcp, domain_desc, 0);
	if (nvdp == NULL) {
		/* More recent versions of libvirt or perhaps the
		 * KVM back-end do not let you create a domain from
		 * XML if there is already a defined domain description
		 * with the same name that it knows about.  You must
		 * then call virDomainCreate() */
		dbg_printf(2,
			"[virt:REBOOT] virDomainCreateLinux() failed for %s; "
			"Trying virDomainCreate()\n",
			vm_name);

		if (virDomainCreate(vdp) < 0) {
			syslog(LOG_NOTICE, "Could not restart %s\n", vm_name);
			dbg_printf(1, "[virt:REBOOT] Failed to recreate guest %s!\n",
				vm_name);
		}
	}

	free(domain_desc);
	virDomainFree(vdp);
	return ret;
}
