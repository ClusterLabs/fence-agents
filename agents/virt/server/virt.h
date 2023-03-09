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

#ifndef _VIRT_H
#define _VIRT_H

#include <stdint.h>
#include <netinet/in.h>
#include <libvirt/libvirt.h>

#include "xvm.h"

typedef struct {
	uint32_t s_owner;
	int32_t s_state;
} vm_state_t;

typedef struct {
	char v_name[MAX_DOMAINNAME_LENGTH + 1];
	char v_uuid[MAX_DOMAINNAME_LENGTH + 1];
	vm_state_t v_state;
} virt_state_t;

/**
  This is stored in our private checkpoint section.
 */
typedef struct _virt_list {
	uint32_t	vm_count;
	virt_state_t	vm_states[0];
} virt_list_t;

virt_list_t *vl_get(virConnectPtr *vp, int vp_count, int my_id);
void vl_print(virt_list_t *vl);
void vl_free(virt_list_t *old);
virt_state_t *vl_find_uuid(virt_list_t *vl, const char *name);
virt_state_t *vl_find_name(virt_list_t *vl, const char *name);
int vl_add(virt_list_t **vl, virt_state_t *vm);
int vl_update(virt_list_t **vl, virt_state_t *vm);
int vl_remove_by_owner(virt_list_t **vl, uint32_t owner);

int vm_off(virConnectPtr *vp, int vp_count, const char *vm_name);
int vm_on(virConnectPtr *vp, int vp_count, const char *vm_name);
int vm_status(virConnectPtr *vp, int vp_count, const char *vm_name);
int vm_reboot(virConnectPtr *vp, int vp_count, const char *vm_name);

#endif
