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

#include "config.h"

#include <stdio.h>
#include <sys/types.h>
#include <stdint.h>
#include <time.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>

#include "simpleconfig.h"
#include "static_map.h"
#include "server_plugin.h"

#define NAME "null"
#define NULL_VERSION "0.8"

#define MAGIC 0x1e00017a

struct null_info {
	int magic;
	int pad;
	char *message;
};

#define VALIDATE(arg) \
do {\
	if (!arg || ((struct null_info *)arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)


static int
null_null(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[Null] Null operation on %s\n", vm_name);

	return 1;
}


static int
null_off(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[Null] OFF operation on %s\n", vm_name);

	return 1;
}


static int
null_on(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[Null] ON operation on %s\n", vm_name);

	return 1;
}


static int
null_devstatus(void *priv)
{
	printf("[Null] Device status\n");
	VALIDATE(priv);
	printf("[Null] Message for you: %s\n",
	       ((struct null_info *)priv)->message);

	return 0;
}


static int
null_status(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[Null] STATUS operation on %s\n", vm_name);

	return 1;
}


static int
null_reboot(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[Null] REBOOT operation on %s\n", vm_name);

	return 1;
}


static int
null_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	VALIDATE(priv);
	printf("[Null] HOSTLIST operation\n");

	return 1;
}


static int
null_init(backend_context_t *c, config_object_t *config)
{
	char value[256];
	struct null_info *info = NULL;
	char *null_message = NULL;

	info = malloc(sizeof(*info));
	if (!info)
		return -1;

	memset(info, 0, sizeof(*info));

	if (sc_get(config, "backends/null/@message",
		   value, sizeof(value)) != 0) {
		snprintf(value, sizeof(value), "Hi!");
	}

	null_message = strdup(value);
	if (!null_message) {
		free(info);
		return -1;
	}

	info->magic = MAGIC;
	info->message = null_message;

	*c = (void *)info;
	return 0;
}


static int
null_shutdown(backend_context_t c)
{
	struct null_info *info = (struct null_info *)c;

	VALIDATE(info);
	info->magic = 0;
	free(info->message);
	free(info);

	return 0;
}


static fence_callbacks_t null_callbacks = {
	.null = null_null,
	.off = null_off,
	.on = null_on,
	.reboot = null_reboot,
	.status = null_status,
	.devstatus = null_devstatus,
	.hostlist = null_hostlist
};

static backend_plugin_t null_plugin = {
	.name = NAME,
	.version = NULL_VERSION,
	.callbacks = &null_callbacks,
	.init = null_init,
	.cleanup = null_shutdown,
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
	return &null_plugin;
}
#else
static void __attribute__((constructor))
null_register_plugin(void)
{
	plugin_reg_backend(&null_plugin);
}
#endif
