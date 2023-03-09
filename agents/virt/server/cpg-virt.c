/*
  Copyright Red Hat, Inc. 2017

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
 * Author: Ryan McCabe <rmccabe@redhat.com>
 */
#include "config.h"

#include <stdio.h>
#include <sys/types.h>
#include <stdint.h>
#include <time.h>
#include <string.h>
#include <syslog.h>
#include <errno.h>
#include <unistd.h>
#include <pthread.h>
#include <corosync/cpg.h>

#include "debug.h"
#include "virt.h"
#include "xvm.h"
#include "cpg.h"
#include "simpleconfig.h"
#include "static_map.h"
#include "server_plugin.h"

#define NAME "cpg"
#define CPG_VERSION "0.1"

#define MAGIC 0x38e93fc2

struct cpg_info {
	int magic;
	config_object_t *config;
	int vp_count;
	virConnectPtr *vp;
};

#define VALIDATE(arg) \
do {\
	if (!arg || ((struct cpg_info *) arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)

static struct cpg_info *cpg_virt_handle = NULL;
static int use_uuid = 0;
pthread_mutex_t local_vm_list_lock = PTHREAD_MUTEX_INITIALIZER;
static virt_list_t *local_vm_list = NULL;

pthread_mutex_t remote_vm_list_lock = PTHREAD_MUTEX_INITIALIZER;
static virt_list_t *remote_vm_list = NULL;

static void cpg_virt_init_libvirt(struct cpg_info *info);

static int
virt_list_update(struct cpg_info *info, virt_list_t **vl, int my_id)
{
	virt_list_t *list = NULL;

	if (*vl)
		vl_free(*vl);

	list = vl_get(info->vp, info->vp_count, my_id);
	if (!list && (errno == EPIPE || errno == EINVAL)) {
		do {
			cpg_virt_init_libvirt(info);
		} while (info->vp_count == 0);
		list = vl_get(info->vp, info->vp_count, my_id);
	}

	*vl = list;
	if (!list)
		return -1;

	return 0;
}


static void
store_domains(virt_list_t *vl)
{
	int i;

	if (!vl)
		return;

	for (i = 0 ; i < vl->vm_count ; i++) {
		int ret;

		if (!strcmp(DOMAIN0NAME, vl->vm_states[i].v_name))
			continue;

		ret = cpg_send_vm_state(&vl->vm_states[i]);
		if (ret < 0) {
			printf("Error storing VM state for %s|%s\n",
				vl->vm_states[i].v_name, vl->vm_states[i].v_uuid);
		}
	}
}


static void
update_local_vms(struct cpg_info *info)
{
	uint32_t my_id = 0;

	if (!info)
		return;

	cpg_get_ids(&my_id, NULL);
	virt_list_update(info, &local_vm_list, my_id);
	store_domains(local_vm_list);
}


static int
do_off(struct cpg_info *info, const char *vm_name)
{
	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	return vm_off(info->vp, info->vp_count, vm_name);

}

static int
do_on(struct cpg_info *info, const char *vm_name)
{
	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	return vm_on(info->vp, info->vp_count, vm_name);

}

static int
do_reboot(struct cpg_info *info, const char *vm_name)
{
	dbg_printf(5, "%s %s\n", __FUNCTION__, vm_name);
	return vm_reboot(info->vp, info->vp_count, vm_name);
}

static void
cpg_join_cb(const struct cpg_address *join, size_t joinlen) {
	struct cpg_info *info = cpg_virt_handle;

	pthread_mutex_lock(&local_vm_list_lock);
	update_local_vms(info);
	pthread_mutex_unlock(&local_vm_list_lock);
}

static void
cpg_leave_cb(const struct cpg_address *left, size_t leftlen) {
	struct cpg_info *info = cpg_virt_handle;
	int i;

	pthread_mutex_lock(&remote_vm_list_lock);
	for (i = 0 ; i < leftlen ; i++) {
		dbg_printf(2, "Removing VMs owned by nodeid %u\n", left[i].nodeid);
		vl_remove_by_owner(&remote_vm_list, left[i].nodeid);
	}
	pthread_mutex_unlock(&remote_vm_list_lock);

	pthread_mutex_lock(&local_vm_list_lock);
	update_local_vms(info);
	pthread_mutex_unlock(&local_vm_list_lock);
}

static void
store_cb(void *data, size_t len, uint32_t nodeid, uint32_t seqno)
{
	uint32_t my_id;
	virt_state_t *vs = (virt_state_t *) data;
	struct cpg_info *info = cpg_virt_handle;

	cpg_get_ids(&my_id, NULL);

	if (nodeid == my_id)
		return;

	pthread_mutex_lock(&local_vm_list_lock);
	if (!local_vm_list)
		update_local_vms(info);
	pthread_mutex_unlock(&local_vm_list_lock);

	pthread_mutex_lock(&remote_vm_list_lock);
	vl_update(&remote_vm_list, vs);
	pthread_mutex_unlock(&remote_vm_list_lock);
}

/*
** This function must a send reply from at least one node, otherwise
** the requesting fence_virtd will block forever in wait_cpt_reply.
*/
static void
do_real_work(void *data, size_t len, uint32_t nodeid, uint32_t seqno)
{
	struct cpg_info *info = cpg_virt_handle;
	struct cpg_fence_req *req = data;
	struct cpg_fence_req reply;
	int reply_code = -1;
	virt_state_t *vs = NULL;
	int cur_state;
	uint32_t cur_owner = 0;
	int local = 0;
	uint32_t my_id, high_id;

	dbg_printf(2, "Request %d for VM %s\n", req->request, req->vm_name);

	if (cpg_get_ids(&my_id, &high_id) == -1) {
		syslog(LOG_WARNING, "Unable to get CPG IDs");
		printf("Should never happen: Can't get CPG node ids - can't proceed\n");
		return;
	}

	memcpy(&reply, req, sizeof(reply));

	pthread_mutex_lock(&local_vm_list_lock);
	update_local_vms(info);
	if (strlen(req->vm_name)) {
		if (use_uuid)
			vs = vl_find_uuid(local_vm_list, req->vm_name);
		else
			vs = vl_find_name(local_vm_list, req->vm_name);

		if (vs) {
			local = 1;
			cur_owner = vs->v_state.s_owner;
			cur_state = vs->v_state.s_state;
			dbg_printf(2, "Found VM %s locally state %d\n",
				req->vm_name, cur_state);
		}
	}
	pthread_mutex_unlock(&local_vm_list_lock);

	if (vs == NULL) {
		pthread_mutex_lock(&remote_vm_list_lock);
		if (strlen(req->vm_name)) {
			if (use_uuid)
				vs = vl_find_uuid(remote_vm_list, req->vm_name);
			else
				vs = vl_find_name(remote_vm_list, req->vm_name);

			if (vs) {
				cur_owner = vs->v_state.s_owner;
				cur_state = vs->v_state.s_state;
				dbg_printf(2, "Found VM %s remotely on %u state %d\n",
					req->vm_name, cur_owner, cur_state);
			}
		}
		pthread_mutex_unlock(&remote_vm_list_lock);
	}

	if (!vs) {
		/*
		** We know about all domains on all nodes in the CPG group.
		** If we didn't find it, and we're high ID, act on the request.
		** We can safely assume the VM is OFF because it wasn't found
		** on any current members of the CPG group.
		*/
		if (my_id == high_id) {
			if (req->request == FENCE_STATUS)
				reply_code = RESP_OFF;
			else if (req->request == FENCE_OFF || req->request == FENCE_REBOOT)
				reply_code = RESP_SUCCESS;
			else
				reply_code = 1;

			dbg_printf(2, "Acting on request %d for unknown domain %s -> %d\n",
				req->request, req->vm_name, reply_code);
			goto out;
		}

		dbg_printf(2, "Not acting on request %d for unknown domain %s\n",
			req->request, req->vm_name);
		return;
	}

	if (local) {
		if (req->request == FENCE_STATUS) {
			/* We already have the status */
			if (cur_state == VIR_DOMAIN_SHUTOFF)
				reply_code = RESP_OFF;
			else
				reply_code = RESP_SUCCESS;
		} else if (req->request == FENCE_OFF) {
			reply_code = do_off(info, req->vm_name);
		} else if (req->request == FENCE_ON) {
			reply_code = do_on(info, req->vm_name);
		} else if (req->request == FENCE_REBOOT) {
			reply_code = do_reboot(info, req->vm_name);
		} else {
			dbg_printf(2, "Not explicitly handling request type %d for %s\n",
				req->request, req->vm_name);
			reply_code = 0;
		}
		goto out;
	}

	/*
	** This is a request for a non-local domain that exists on a
	** current CPG group member, so that member will see the request
	** and act on it. We don't need to do anything.
	*/
	dbg_printf(2, "Nothing to do for non-local domain %s seq %d owner %u\n",
		req->vm_name, seqno, cur_owner);
	return;

out:
	dbg_printf(2, "[%s] sending reply code seq %d -> %d\n",
		req->vm_name, seqno, reply_code);

	reply.response = reply_code;
	if (cpg_send_reply(&reply, sizeof(reply), nodeid, seqno) < 0) {
		dbg_printf(2, "cpg_send_reply failed for %s [%d %d]: %s\n",
			req->vm_name, nodeid, seqno, strerror(errno));
	}
}


static int
do_request(const char *vm_name, int request, uint32_t seqno)
{
	struct cpg_fence_req freq, *frp;
	size_t retlen;
	uint32_t seq;
	int ret;

	memset(&freq, 0, sizeof(freq));
	if (!vm_name) {
		dbg_printf(1, "No VM name\n");
		return 1;
	}

	if (strlen(vm_name) >= sizeof(freq.vm_name)) {
		dbg_printf(1, "VM name %s too long\n", vm_name);
		return 1;
	}

	strcpy(freq.vm_name, vm_name);

	freq.request = request;
	freq.seqno = seqno;

	if (cpg_send_req(&freq, sizeof(freq), &seq) != 0) {
		dbg_printf(1, "Failed to send request %d for VM %s\n",
			freq.request, vm_name);
		return 1;
	}

	dbg_printf(2, "Sent request %d for VM %s got seqno %d\n",
		request, vm_name, seq);

	if (cpg_wait_reply((void *) &frp, &retlen, seq) != 0) {
		dbg_printf(1, "Failed to receive reply seq %d for %s\n", seq, vm_name);
		return 1;
	}

	dbg_printf(2, "Received reply [%d] seq %d for %s\n",
		frp->response, seq, vm_name);

	ret = frp->response;
	free(frp);

	return ret;
}


static int
cpg_virt_null(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[cpg-virt] Null operation on %s\n", vm_name);

	return 1;
}


static int
cpg_virt_off(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[cpg-virt] OFF operation on %s seq %d\n", vm_name, seqno);

	return do_request(vm_name, FENCE_OFF, seqno);
}


static int
cpg_virt_on(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[cpg-virt] ON operation on %s seq %d\n", vm_name, seqno);

	return do_request(vm_name, FENCE_ON, seqno);
}


static int
cpg_virt_devstatus(void *priv)
{
	printf("[cpg-virt] Device status\n");
	VALIDATE(priv);

	return 0;
}


static int
cpg_virt_status(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[cpg-virt] STATUS operation on %s\n", vm_name);

	return do_request(vm_name, FENCE_STATUS, 0);
}


static int
cpg_virt_reboot(const char *vm_name, const char *src,
		  uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[cpg-virt] REBOOT operation on %s seq %d\n", vm_name, seqno);

	return do_request(vm_name, FENCE_REBOOT, 0);
}


static int
cpg_virt_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	struct cpg_info *info = (struct cpg_info *) priv;
	int i;

	VALIDATE(priv);
	printf("[cpg-virt] HOSTLIST operation\n");

	pthread_mutex_lock(&local_vm_list_lock);
	update_local_vms(info);
	for (i = 0 ; i < local_vm_list->vm_count ; i++) {
		callback(local_vm_list->vm_states[i].v_name,
				 local_vm_list->vm_states[i].v_uuid,
				 local_vm_list->vm_states[i].v_state.s_state, arg);
	}
	pthread_mutex_unlock(&local_vm_list_lock);

	return 1;
}

static void
cpg_virt_init_libvirt(struct cpg_info *info) {
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
				"backends/cpg/@uri%d", i);
		} else
			snprintf(conf_attr, sizeof(conf_attr), "backends/cpg/@uri");
		++i;

		if (sc_get(config, conf_attr, value, sizeof(value)) != 0)
			break;

		uri = value;
		vp = virConnectOpen(uri);
		if (!vp) {
			dbg_printf(1, "[cpg-virt:INIT] Failed to connect to URI: %s\n", uri);
			continue;
		}

		vpl = realloc(info->vp, sizeof(*info->vp) * (info->vp_count + 1));
		if (!vpl) {
			dbg_printf(1, "[cpg-virt:INIT] Out of memory allocating URI: %s\n",
				uri);
			virConnectClose(vp);
			continue;
		}

		info->vp = vpl;
		info->vp[info->vp_count++] = vp;

		if (i > 1)
			dbg_printf(1, "[cpg-virt:INIT] Added URI%d %s\n", i - 1, uri);
		else
			dbg_printf(1, "[cpg_virt:INIT] Added URI %s\n", uri);
	} while (1);
}

static int
cpg_virt_init(backend_context_t *c, config_object_t *config)
{
	char value[1024];
	struct cpg_info *info = NULL;
	int ret;

	ret = cpg_start(PACKAGE_NAME,
		do_real_work, store_cb, cpg_join_cb, cpg_leave_cb);
	if (ret < 0)
		return -1;

	info = calloc(1, sizeof(*info));
	if (!info)
		return -1;
	info->magic = MAGIC;
	info->config = config;

	if (sc_get(config, "fence_virtd/@debug", value, sizeof(value)) == 0)
		dset(atoi(value));

	cpg_virt_init_libvirt(info);

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

	if (sc_get(config, "backends/cpg/@name_mode",
		   value, sizeof(value)-1) == 0)
	{
		dbg_printf(1, "Got %s for name_mode\n", value);
		if (!strcasecmp(value, "uuid")) {
			use_uuid = 1;
		} else if (!strcasecmp(value, "name")) {
			use_uuid = 0;
		} else {
			dbg_printf(1, "Unsupported name_mode: %s\n", value);
		}
	}

	if (info->vp_count < 1) {
		dbg_printf(1, "[cpg_virt:INIT] Could not connect to any hypervisors\n");
		cpg_stop();
		free(info);
		return -1;
	}

	pthread_mutex_lock(&local_vm_list_lock);
	update_local_vms(info);
	pthread_mutex_unlock(&local_vm_list_lock);

	*c = (void *) info;
	cpg_virt_handle = info;
	return 0;
}


static int
cpg_virt_shutdown(backend_context_t c)
{
	struct cpg_info *info = (struct cpg_info *)c;
	int i = 0;
	int ret = 0;

	VALIDATE(info);
	info->magic = 0;

	cpg_stop();

	for (i = 0 ; i < info->vp_count ; i++) {
		if (virConnectClose(info->vp[i]) < 0)
			ret = -errno;
	}

	free(info->vp);
	free(info);

	return ret;
}


static fence_callbacks_t cpg_callbacks = {
	.null = cpg_virt_null,
	.off = cpg_virt_off,
	.on = cpg_virt_on,
	.reboot = cpg_virt_reboot,
	.status = cpg_virt_status,
	.devstatus = cpg_virt_devstatus,
	.hostlist = cpg_virt_hostlist
};

static backend_plugin_t cpg_virt_plugin = {
	.name = NAME,
	.version = CPG_VERSION,
	.callbacks = &cpg_callbacks,
	.init = cpg_virt_init,
	.cleanup = cpg_virt_shutdown,
};

double
BACKEND_VER_SYM(void)
{
	return PLUGIN_VERSION_BACKEND;
}

const backend_plugin_t *
BACKEND_INFO_SYM(void)
{
	return &cpg_virt_plugin;
}
