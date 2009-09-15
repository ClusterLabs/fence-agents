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
#include <sys/types.h>
#include <stdint.h>
#include <time.h>
#include <server_plugin.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>
#include <libvirt/libvirt.h>
#ifdef HAVE_OPENAIS_CPG_H
#include <openais/cpg.h>
#else
#ifdef HAVE_COROSYNC_CPG_H
#include <corosync/cpg.h>
#endif
#endif


#define NAME "checkpoint"
#define VERSION "0.8"

#define MAGIC 0x1e017afe

struct check_info {
	int magic;
	int pad;
	cpg_handle_t h;
	virConnectPtr vp;
};

#define VALIDATE(arg) \
do {\
	if (!arg || ((struct check_info *)arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)


static int
ckpt_null(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] Null operation on %s\n", vm_name);

	return 1;
}


static int
ckpt_off(const char *vm_name, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] OFF operation on %s seq %d\n", vm_name, seqno);

	return 1;
}


static int
ckpt_on(const char *vm_name, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] ON operation on %s seq %d\n", vm_name, seqno);

	return 1;
}


static int
ckpt_devstatus(void *priv)
{
	printf("[CKPT] Device status\n");
	VALIDATE(priv);

	return 0;
}


static int
ckpt_status(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] STATUS operation on %s\n", vm_name);

	return 1;
}


static int
ckpt_reboot(const char *vm_name, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[CKPT] REBOOT operation on %s seq %d\n", vm_name, seqno);

	return 1;
}


static int
ckpt_init(backend_context_t *c, config_object_t *config)
{
	//char value[256];
	struct check_info *info = NULL;

	info = malloc(sizeof(*info));
	if (!info)
		return -1;

	memset(info, 0, sizeof(*info));

	info->magic = MAGIC;

	*c = (void *)info;
	return 0;
}


static int
ckpt_shutdown(backend_context_t c)
{
	struct check_info *info = (struct check_info *)c;

	VALIDATE(info);
	info->magic = 0;
	free(info);

	return 0;
}


static fence_callbacks_t ckpt_callbacks = {
	.null = ckpt_null,
	.off = ckpt_off,
	.on = ckpt_on,
	.reboot = ckpt_reboot,
	.status = ckpt_status,
	.devstatus = ckpt_devstatus
};

static backend_plugin_t ckpt_plugin = {
	.name = NAME,
	.version = VERSION,
	.callbacks = &ckpt_callbacks,
	.init = ckpt_init,
	.cleanup = ckpt_shutdown,
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
	return &ckpt_plugin;
}
#else
static void __attribute__((constructor))
ckpt_register_plugin(void)
{
	plugin_reg_backend(&ckpt_plugin);
}
#endif
