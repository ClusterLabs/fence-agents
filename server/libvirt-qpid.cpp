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
#include <string>
#include <sstream>
#include <iostream>
#include "uuid-test.h"
#include <xvm.h>

#include <qpid/types/Variant.h>
#include <qpid/messaging/Connection.h>
#include <qpid/console/Object.h>
#include <qmf/ConsoleSession.h>
#include <qmf/ConsoleEvent.h>


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


static qmf::ConsoleSession
lq_open_session(struct lq_info *info)
{
	std::stringstream url;
	url << info->host << ":" << info->port;

	qpid::types::Variant::Map options;
	if (info->username) {
		options["username"] = info->username;
	}
        if (info->service) {
		options["sasl-service"] = info->service;
	}
	if (info->use_gssapi) {
		options["sasl-mechanism"] = "GSSAPI";
	}

	qpid::messaging::Connection connection(url.str(), options);
	connection.open();

	qmf::ConsoleSession session;
	if (!connection.isOpen()) {
		std::cout << "Error connecting." << std::endl;
	} else {
		session = qmf::ConsoleSession(connection);

		std::stringstream filter;
		filter << "[or, "
			   "[eq, _product, [quote, 'libvirt-qmf']], "
			   "[eq, _product, [quote, 'libvirt-qpid']]"
			  "]";
		session.setAgentFilter(filter.str());
		session.open();
	}

	return session;
}

static qmf::ConsoleEvent
queryDomain(qmf::Agent& agent)
{
	std::string query;
	if (agent.getProduct() == "libvirt-qmf") {
		query = "{class: Domain, package: 'org.libvirt'}";
	} else {
		query = "{class: domain, package: 'com.redhat.libvirt'}";
	}

	return agent.query(query);
}

int
do_lq_request(struct lq_info *info, const char *vm_name,
	      const char *action)
{
	std::string vm_state;
	const char *property = "name";
	if (is_uuid(vm_name) == 1) {
		property = "uuid";
	}
	
	qmf::ConsoleSession session(lq_open_session(info));
	if (!session.isValid()) {
		std::cout << "Invalid session." << std::endl;
		return 1;
	}

	qmf::Agent agent;
	qmf::Data domain;
	int result;

	unsigned tries = 0;
	bool found = false;
	while (++tries < 10 && !found) {
		sleep(1);

		uint32_t numAgents = session.getAgentCount();
		for (unsigned a = 0; !found && a < numAgents; a++) {
			agent = session.getAgent(a);

			qmf::ConsoleEvent event(queryDomain(agent));
			uint32_t numDomains = event.getDataCount();
			for (unsigned d = 0; !found && d < numDomains; d++) {
				domain = event.getData(d);
				qpid::types::Variant prop;
				try {
					prop = domain.getProperty(property);
				} catch (qmf::KeyNotFound e) {
					std::cout << e.what() << " - skipping" << std::endl;
					continue;
				}

				if (prop.asString() != vm_name) {
					continue;
				}

				found = true;
			}
		}
	}

	if (!found) {
		result = 1;
		goto out;
	}

	vm_state = domain.getProperty("state").asString();

	std::cout << vm_name << " " << vm_state << std::endl;

	int r;
	if (vm_state == "running" ||
	    vm_state == "idle" ||
	    vm_state == "paused" ||
	    vm_state == "no state") {
		r = RESP_OFF;
	} else {
		r = 0;
	}

	if (strcasecmp(action, "state") == 0) {
		result = r;
		goto out;
	}

	result = 1;
	if (!r && strcasecmp(action, "destroy") == 0) {
		std::cout << "Domain is inactive; nothing to do" << std::endl;
		result = 0;
		goto out;
	}
	if (r && strcasecmp(action, "create") == 0) {
		std::cout << "Domain is active; nothing to do" << std::endl;
		result = 0;
		goto out;
	}

	{
		qmf::ConsoleEvent response;
		response = agent.callMethod(action,
				qpid::types::Variant::Map(),
				domain.getAddr());

		if (response.getType() == qmf::CONSOLE_EXCEPTION) {
			std::string errorText;
			if (response.getDataCount()) {
				qmf::Data responseData(response.getData(0));

				qpid::types::Variant code(responseData.getProperty("error_code"));
				if (code.getType() == qpid::types::VAR_INT32) {
					result = responseData.getProperty("error_code").asInt32();
				} else {
					result = 7; // Exception
				}
				qpid::types::Variant text(responseData.getProperty("error_text"));
				if (text.getType() != qpid::types::VAR_VOID) {
					errorText = text.asString();
				}
			} else {
				result = 7; // Exception
			}

			std::cout << "Response: " << result;
			if (errorText.length()) {
				std::cout << " (" << errorText << ")";
			}
			std::cout << std::endl;
		} else { // Success
			result = 0;
		}
	}

out:
	session.close();

	return result;
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

	printf("[libvirt-qpid] HOSTLIST operation\n");
	
	qmf::ConsoleSession session(lq_open_session((struct lq_info *)priv));
	if (!session.isValid()) {
		return 1;
	}

	unsigned tries = 0;
	qmf::ConsoleEvent event;
	uint32_t numDomains = 0;
	while (++tries < 10 && !numDomains) {
		sleep(1);
		uint32_t numAgents = session.getAgentCount();
		for (unsigned a = 0; a < numAgents; a++) {
			qmf::Agent agent(session.getAgent(a));
			event = queryDomain(agent);

			numDomains = event.getDataCount();
			if (numDomains >= 1) {
				break;
			}
		}
	}

	for (unsigned d = 0; d < numDomains; d++) {
		qmf::Data domain = event.getData(d);

		std::string vm_name, vm_uuid, vm_state_str;
		try {
			vm_name = domain.getProperty("name").asString();
			vm_uuid = domain.getProperty("uuid").asString();
			vm_state_str = domain.getProperty("state").asString();
		} catch (qmf::KeyNotFound e) {
			std::cout << e.what() << " - skipping" << std::endl;
			continue;
		}

		int vm_state;
		if (!strcasecmp(vm_state_str.c_str(), "shutoff")) {
			vm_state = 0;
		} else {
			vm_state = 1;
		}

		callback(vm_name.c_str(), vm_uuid.c_str(), vm_state, arg);
	}

	session.close();
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
	info->port = 49000;

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
