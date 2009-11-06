//
//  Copyright Red Hat, Inc. 2009
//
//  This program is free software; you can redistribute it and/or modify it
//  under the terms of the GNU General Public License as published by the
//  Free Software Foundation; either version 2, or (at your option) any
//  later version.
//
//  This program is distributed in the hope that it will be useful, but
//  WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
//  General Public License for more details.
//
//  You should have received a copy of the GNU General Public License
//  along with this program; see the file COPYING.  If not, write to the
//  Free Software Foundation, Inc.,  675 Mass Ave, Cambridge, 
//  MA 02139, USA.
//
//  Author: Lon Hohberger <lhh at redhat.com>
//
#include <stdio.h>
#include <simpleconfig.h>
#include <sys/types.h>
#include <stdint.h>
#include <time.h>
#include <server_plugin.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>
#include "uuid-test.h"

#include <qpid/console/SessionManager.h>

using namespace qpid::console; 
using namespace qpid::client; 



#define NAME "libvirt-qpid"
#define VERSION "0.1"

#define MAGIC 0x1e01017a

struct lq_info {
	int magic;
	int pad;
	char *host;
	uint16_t port;
};

#define VALIDATE(arg) \
do {\
	if (!arg || ((struct lq_info *)arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)


int
do_lq_request(const char *vm_name, const char *action)
{
	Broker *b = NULL;
	ConnectionSettings cs;
	SessionManager::NameVector names;
	Object::Vector domains;
	Object *domain = NULL;
	const char *property = "name";
	unsigned i, tries = 0, found = 0;

	if (is_uuid(vm_name) == 1) {
		property = "uuid";
	}

	cs.host = "127.0.0.1";
	cs.port = 5672;
	
	SessionManager::Settings s;

	s.rcvObjects = true;
	s.rcvEvents = false;
	s.rcvHeartbeats = false;
	s.userBindings = false;
	s.methodTimeout = 10;
	s.getTimeout = 10;

	SessionManager sm(NULL, s);

	try {
		b = sm.addBroker(cs);
	}
	catch (...) {
		std::cout << "Error connecting.\n";
		return 1;
	}

	while (tries < 10 && !found) {
		sleep(1);

		// why not com.redhat.libvirt:domain or having
		// a way to specify that I want the domain objects from
		// the com.redhat.libvirt namespace?!

		sm.getObjects(domains, "domain", NULL, NULL);

		for (i = 0; i < domains.size(); i++) {
#if 0
			SchemaClass *c;

			c = domains[i].getSchema();
#endif

			if (strcmp(domains[i].attrString(property).c_str(),
				   vm_name)) {
				continue;
			}

			found = 1;
			domain = &domains[i];

			break;

#if 0
			for (j = 0; j < c->properties.size(); j++) {
				if (!strcmp(c->properties[j]->name.c_str(), "name") &&
				    !strcmp(domains[i].attrString(c->properties[j]->name).c_str(), argv[1])) {
					std::cout << c->properties[j]->name << " " << domains[i].attrString(c->properties[j]->name) << std::endl;
				}
			}
#endif

		}
	}

	if (!found) {
		return 1;
	}

	Object::AttributeMap attrs;
	MethodResponse result;

	std::cout << domain->attrString(property) << " "
		  << domain->attrString("state") << std::endl;

	domain->invokeMethod(action, attrs, result);

	std::cout << "Response: " << result.code << " (" << result.text << ")" << std::endl;

	sm.delBroker(b);

	return result.code;
}


static int
lq_null(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] libvirt-qpid operation on %s\n", vm_name);

	return 1;
}


static int
lq_off(const char *vm_name, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] OFF operation on %s\n", vm_name);

	return do_lq_request(vm_name, "destroy");

	return 1;
}


static int
lq_on(const char *vm_name, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] ON operation on %s\n", vm_name);

	return do_lq_request(vm_name, "create");
}


static int
lq_devstatus(void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] Device status\n");

	return 0;
}


static int
lq_status(const char *vm_name, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] STATUS operation on %s\n", vm_name);

	return 1;
}


static int
lq_reboot(const char *vm_name, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] REBOOT operation on %s\n", vm_name);
	
	if (lq_off(vm_name, seqno, priv) != 0)
		return 1;
	sleep(1);
	lq_on(vm_name, seqno, priv);

	return 1;
}


static int
lq_init(backend_context_t *c, config_object_t *config)
{
	char value[256];
	struct lq_info *info = NULL;
	char *null_message = NULL;

	info = (lq_info *)malloc(sizeof(*info));
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

	*c = (void *)info;
	return 0;
}


static int
lq_shutdown(backend_context_t c)
{
	struct lq_info *info = (struct lq_info *)c;

	VALIDATE(info);
	info->magic = 0;
	free(info);

	return 0;
}


static fence_callbacks_t lq_callbacks = {
	lq_null, lq_off, lq_on, lq_reboot, lq_status, lq_devstatus
};

static backend_plugin_t lq_plugin = {
	NAME, VERSION, &lq_callbacks, lq_init, lq_shutdown
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
	return &lq_plugin;
}
#else
static void __attribute__((constructor))
lq_register_plugin(void)
{
	plugin_reg_backend(&lq_plugin);
}
#endif
