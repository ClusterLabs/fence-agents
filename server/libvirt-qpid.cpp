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
#include <static_map.h>
#include <sys/types.h>
#include <stdint.h>
#include <time.h>
#include <server_plugin.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>
#include "uuid-test.h"
#include <xvm.h>

#include <qpid/console/SessionManager.h>

using namespace qpid::console; 
using namespace qpid::client; 



#define NAME "libvirt-qpid"
#define VERSION "0.1"

#define MAGIC 0x1e01017a

struct lq_info {
	int magic;
	int port;
	char *host;
	char *username;
	char *service;
	int use_gssapi;
};
	


#define VALIDATE(arg) \
do {\
	if (!arg || ((struct lq_info *)arg)->magic != MAGIC) { \
		errno = EINVAL;\
		return -1; \
	} \
} while(0)


int
do_lq_request(struct lq_info *info, const char *vm_name,
	      const char *action)
{
	Broker *b = NULL;
	SessionManager::NameVector names;
	Object::Vector domains;
	Object *domain = NULL;
	const char *property = "name";
	unsigned i, tries = 0, found = 0;
	const char *vm_state = NULL;

	if (is_uuid(vm_name) == 1) {
		property = "uuid";
	}
	
	SessionManager::Settings s;

	s.rcvObjects = true;
	s.rcvEvents = false;
	s.rcvHeartbeats = false;
	s.userBindings = false;
	s.methodTimeout = 10;
	s.getTimeout = 10;

	SessionManager sm(NULL, s);

	ConnectionSettings cs;
	if (info->host)
		cs.host = info->host;
	if (info->port)
		cs.port = info->port;
	if (info->username)
		cs.username = info->username;
	if (info->service)
		cs.service = info->service;
	if (info->use_gssapi)
		cs.mechanism = "GSSAPI";

	try {
		b = sm.addBroker(cs);
	}
	catch (...) {
		std::cout << "Error connecting.\n";
		return 1;
	}

	while (++tries < 10 && !found) {
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

	Object::AttributeMap attrs;
	MethodResponse result;

	if (!found) {
		result.code = 1;
		goto out;
	}

	vm_state = domain->attrString("state").c_str();

	std::cout << domain->attrString(property) << " "
		  << vm_state << std::endl;
	
	if (!strcmp( vm_state, "running" ) ||
	    !strcmp( vm_state, "idle" ) ||
	    !strcmp( vm_state, "paused" ) ||
	    !strcmp( vm_state, "no state" ) ) {
		i = RESP_OFF;
	} else {
		i = 0;
	}

	if (!strcasecmp(action, "state")) {
		result.code = i;
		goto out;
	}

	result.code = 1;
	if (!strcasecmp(action, "destroy") && !i) {
		std::cout << "Domain is inactive; nothing to do" << std::endl;
		result.code = 0;
		goto out;
	}
	if (!strcasecmp(action, "create") && i) {
		std::cout << "Domain is active; nothing to do" << std::endl;
		result.code = 0;
		goto out;
	}

	domain->invokeMethod(action, attrs, result);

	std::cout << "Response: " << result.code << " (" << result.text << ")" << std::endl;

out:
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
lq_off(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] OFF operation on %s\n", vm_name);

	return do_lq_request((lq_info *)priv, vm_name, "destroy");

	return 1;
}


static int
lq_on(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] ON operation on %s\n", vm_name);

	return do_lq_request((lq_info *)priv, vm_name, "create");
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

	return do_lq_request((lq_info *)priv, vm_name, "state");
}


static int
lq_reboot(const char *vm_name, const char *src, uint32_t seqno, void *priv)
{
	VALIDATE(priv);
	printf("[libvirt-qpid] REBOOT operation on %s\n", vm_name);
	
	if (lq_off(vm_name, src, seqno, priv) != 0)
		return 1;
	sleep(1);
	lq_on(vm_name, src, seqno, priv);

	return 0;
}


static int
lq_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	VALIDATE(priv);

	struct lq_info *info = (struct lq_info *)priv;

	Broker *b = NULL;
	SessionManager::NameVector names;
	Object::Vector domains;
	unsigned i, tries = 0;
	const char *vm_name, *vm_uuid, *vm_state_str;
	int vm_state = 0, ret = 1;

	printf("[libvirt-qpid] HOSTLIST operation\n");
	
	SessionManager::Settings s;

	s.rcvObjects = true;
	s.rcvEvents = false;
	s.rcvHeartbeats = false;
	s.userBindings = false;
	s.methodTimeout = 10;
	s.getTimeout = 10;

	SessionManager sm(NULL, s);

	ConnectionSettings cs;
	if (info->host)
		cs.host = info->host;
	if (info->port)
		cs.port = info->port;
	if (info->username)
		cs.username = info->username;
	if (info->service)
		cs.service = info->service;
	if (info->use_gssapi)
		cs.mechanism = "GSSAPI";

	try {
		b = sm.addBroker(cs);
	}
	catch (...) {
		std::cout << "Error connecting.\n";
		return 1;
	}

	while (++tries < 10) {
		sleep(1);

		sm.getObjects(domains, "domain", NULL, NULL);

		if (domains.size() >= 1) {
			break;
		}
	}

	if (domains.size() < 1)
		goto out;

	for (i = 0; i < domains.size(); i++) {

		vm_name = domains[i].attrString("name").c_str();
		vm_uuid = domains[i].attrString("uuid").c_str();
		vm_state_str = domains[i].attrString("state").c_str();

		if (!strcasecmp(vm_state_str, "shutoff"))
			vm_state = 0;
		else 
			vm_state = 1;

		callback(vm_name, vm_uuid, vm_state, arg);
	}
	ret = 0;

out:
	sm.delBroker(b);

	return 0;
}


static int
lq_init(backend_context_t *c, config_object_t *config)
{
	char value[256];
	struct lq_info *info = NULL;

	info = (lq_info *)malloc(sizeof(*info));
	if (!info)
		return -1;

	memset(info, 0, sizeof(*info));
	info->port = 5672;

	if(sc_get(config, "backends/libvirt-qpid/@host",
		   value, sizeof(value))==0){
		printf("\n\nHOST = %s\n\n",value);	
		info->host = strdup(value);
		if (!info->host) {
			goto out_fail;
		}
	} else {
		info->host = strdup("127.0.0.1");
	}

	if(sc_get(config, "backends/libvirt-qpid/@port",
		   value, sizeof(value)-1)==0){
		printf("\n\nPORT = %d\n\n",atoi(value));	
		info->port = atoi(value);
	}

	if(sc_get(config, "backends/libvirt-qpid/@username",
		   value, sizeof(value))==0){
		printf("\n\nUSERNAME = %s\n\n",value);	
		info->username = strdup(value);
		if (!info->username) {
			goto out_fail;
		}
	}

	if(sc_get(config, "backends/libvirt-qpid/@service",
		   value, sizeof(value))==0){
		printf("\n\nSERVICE = %s\n\n",value);	
		info->service = strdup(value);
		if (!info->service) {
			goto out_fail;
		}
	}

	if(sc_get(config, "backends/libvirt-qpid/@gssapi",
		   value, sizeof(value)-1)==0){
		printf("\n\nGSSAPI = %d\n\n",atoi(value));	
		if (atoi(value) > 0) {
			info->use_gssapi = 1;
		}
	}

	info->magic = MAGIC;

	*c = (void *)info;
	return 0;

out_fail:
	free(info->service);
	free(info->username);
	free(info->host);

	free(info);

	return -1;
}


static int
lq_shutdown(backend_context_t c)
{
	struct lq_info *info = (struct lq_info *)c;

	VALIDATE(info);
	info->magic = 0;

	free(info->service);
	free(info->username);
	free(info->host);

	free(info);

	return 0;
}


static fence_callbacks_t lq_callbacks = {
	lq_null, lq_off, lq_on, lq_reboot, lq_status, lq_devstatus,
	lq_hostlist
};

static backend_plugin_t lq_plugin = {
	NAME, VERSION, &lq_callbacks, lq_init, lq_shutdown
};


#ifdef _MODULE
extern "C" double
BACKEND_VER_SYM(void)
{
	return PLUGIN_VERSION_BACKEND;
}

extern "C" const backend_plugin_t *
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
