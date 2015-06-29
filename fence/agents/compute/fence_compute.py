#!/usr/bin/python -tt

import sys
import time
import atexit
import logging
import requests.exceptions

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, is_executable, run_command, run_delay

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="4.0.11"
BUILD_DATE="(built Wed Nov 12 06:33:38 EST 2014)"
REDHAT_COPYRIGHT="Copyright (C) Red Hat, Inc. 2004-2010 All rights reserved."
#END_VERSION_GENERATION

override_status = ""
nova = None

def get_power_status(_, options):
	global override_status

	status = "unknown"
	logging.debug("get action: " + options["--action"])

	if len(override_status):
		logging.debug("Pretending we're " + override_status)
		return override_status

	if nova:
		try:
			services = nova.services.list(host=options["--plug"])

			for service in services:
				if service.binary == "nova-compute":
					if service.state == "up":
						status = "on"
					elif service.state == "down":
						status = "off"
					else:
						logging.debug("Unknown status detected from nova: " + service.state)
					break
		except ConnectionError as (err):
			logging.warning("Nova connection failed: " + str(err))
	return status

# NOTE(sbauza); We mimic the host-evacuate module since it's only a contrib
# module which is not stable
def _server_evacuate(server, on_shared_storage):
	success = True
	error_message = ""
	try:
		nova.servers.evacuate(server=server['uuid'], on_shared_storage=on_shared_storage)
	except Exception as e:
		success = False
		error_message = "Error while evacuating instance: %s" % e

	return {
		"server_uuid": server['uuid'],
		"evacuate_accepted": success,
		"error_message": error_message,
		}

def _host_evacuate(host, on_shared_storage):
	hypervisors = nova.hypervisors.search(host, servers=True)
	response = []
	for hyper in hypervisors:
		if hasattr(hyper, 'servers'):
			for server in hyper.servers:
				response.append(_server_evacuate(server, on_shared_storage))

def set_attrd_status(host, status, options):
	logging.debug("Setting fencing status for %s to %s" % (host, status))
	run_command(options, "attrd_updater -p -n evacute -Q -N %s -v %s" % (host, status))

def set_power_status(_, options):
	global override_status

	override_status = ""
	logging.debug("set action: " + options["--action"])

	if not nova:
		return

	if options["--action"] == "on":
		if get_power_status(_, options) == "on":
			nova.services.enable(options["--plug"], 'nova-compute')
		else:
			# Pretend we're 'on' so that the fencing library doesn't loop forever waiting for the node to boot
			override_status = "on"
		return

	# need to wait for nova to update its internal status or we
	# cannot call host-evacuate
	while get_power_status(_, options) != "off":
		# Loop forever if need be.
		#
		# Some callers (such as Pacemaker) will have a timer
		# running and kill us if necessary
		logging.debug("Waiting for nova to update it's internal state")
		time.sleep(1)

	if options["--no-shared-storage"] != "False":
		on_shared_storage = False
	else:
		on_shared_storage = True

	_host_evacuate(options["--plug"], on_shared_storage)
	return

def get_plugs_list(_, options):
	result = {}

	if nova:
		hypervisors = nova.hypervisors.list()
		for hypervisor in hypervisors:
			longhost = hypervisor.hypervisor_hostname
			if options["--action"] == "list" and options["--domain"] != "":
				shorthost = longhost.replace("." + options["--domain"],
                                                 "")
				result[shorthost] = ("", None)
			else:
				result[longhost] = ("", None)
	return result


def define_new_opts():
	all_opt["endpoint-type"] = {
		"getopt" : "e:",
		"longopt" : "endpoint-type",
		"help" : "-e, --endpoint-type=[endpoint] Nova Endpoint type (publicURL, internalURL, adminURL)",
		"required" : "0",
		"shortdesc" : "Nova Endpoint type",
		"default" : "internalURL",
		"order": 1,
	}
	all_opt["tenant-name"] = {
		"getopt" : "t:",
		"longopt" : "tenant-name",
		"help" : "-t, --tenant-name=[tenant]     Keystone Admin Tenant",
		"required" : "0",
		"shortdesc" : "Keystone Admin Tenant",
		"default" : "",
		"order": 1,
	}
	all_opt["auth-url"] = {
		"getopt" : "k:",
		"longopt" : "auth-url",
		"help" : "-k, --auth-url=[tenant]        Keystone Admin Auth URL",
		"required" : "0",
		"shortdesc" : "Keystone Admin Auth URL",
		"default" : "",
		"order": 1,
	}
	all_opt["domain"] = {
		"getopt" : "d:",
		"longopt" : "domain",
		"help" : "-d, --domain=[string]          DNS domain in which hosts live, useful when the cluster uses short names and nova uses FQDN",
		"required" : "0",
		"shortdesc" : "DNS domain in which hosts live",
		"default" : "",
		"order": 5,
	}
	all_opt["record-only"] = {
		"getopt" : "",
		"longopt" : "record-only",
		"help" : "--record-only                  Record the target as needing evacuation but as yet do not intiate it",
		"required" : "0",
		"shortdesc" : "Only record the target as needing evacuation",
		"default" : "False",
		"order": 5,
	}
	all_opt["no-shared-storage"] = {
		"getopt" : "",
		"longopt" : "no-shared-storage",
		"help" : "--no-shared-storage            Disable functionality for shared storage",
		"required" : "0",
		"shortdesc" : "Disable functionality for dealing with shared storage",
		"default" : "False",
		"order": 5,
	}

def main():
	global override_status
	global nova
	atexit.register(atexit_handler)

	device_opt = ["login", "passwd", "tenant-name", "auth-url",
		"no_login", "no_password", "port", "domain", "no-shared-storage", "endpoint-type",
		"record-only"]
	define_new_opts()
	all_opt["shell_timeout"]["default"] = "180"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for nova compute nodes"
	docs["longdesc"] = "fence_nova_host is a Nova fencing notification agent"
	docs["vendorurl"] = ""

	show_docs(options, docs)

	run_delay(options)

	try:
		from novaclient import client as nova_client
	except ImportError:
		fail_usage("nova not found or not accessible")

	# Potentially we should make this a pacemaker feature
	if options["--action"] != "list" and options["--domain"] != "" and options.has_key("--plug"):
		options["--plug"] = options["--plug"] + "." + options["--domain"]

	if options["--record-only"] != "False":
		if options["--action"] == "on":
			set_attrd_status(options["--plug"], "no", options)
			sys.exit(0)

		elif options["--action"] in ["off", "reboot"]:
			set_attrd_status(options["--plug"], "yes", options)
			sys.exit(0)

		elif options["--action"] in ["status", "monitor"]:
			sys.exit(0)

	# The first argument is the Nova client version
	nova = nova_client.Client('2',
		options["--username"],
		options["--password"],
		options["--tenant-name"],
		options["--auth-url"],
		endpoint_type=options["--endpoint-type"])

	if options["--action"] in ["off", "reboot"]:
		# Pretend we're 'on' so that the fencing library will always call set_power_status(off)
		override_status = "on"

	if options["--action"] == "on":
		# Pretend we're 'off' so that the fencing library will always call set_power_status(on)
		override_status = "off"

	result = fence_action(None, options, set_power_status, get_power_status, get_plugs_list, None)
	sys.exit(result)

if __name__ == "__main__":
	main()
