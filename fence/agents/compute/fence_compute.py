#!@PYTHON@ -tt

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

EVACUABLE_TAG = "evacuable"
TRUE_TAGS = ['true']

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
				logging.debug("Status of %s is %s" % (service.binary, service.state))
				if service.binary == "nova-compute":
					if service.state == "up":
						status = "on"
					elif service.state == "down":
						status = "off"
					else:
						logging.debug("Unknown status detected from nova: " + service.state)
					break
		except ConnectionError as err:
			logging.warning("Nova connection failed: " + str(err))
	return status

# NOTE(sbauza); We mimic the host-evacuate module since it's only a contrib
# module which is not stable
def _server_evacuate(server, on_shared_storage):
	success = False
	error_message = ""
	try:
		logging.debug("Resurrecting instance: %s" % server)
		(response, dictionary) = nova.servers.evacuate(server=server, on_shared_storage=on_shared_storage)

		if response == None:
			error_message = "No response while evacuating instance"
		elif response.status_code == 200:
			success = True
			error_message = response.reason
		else:
			error_message = response.reason

	except Exception as e:
		error_message = "Error while evacuating instance: %s" % e

	return {
		"uuid": server,
		"accepted": success,
		"reason": error_message,
		}

def _is_server_evacuable(server, evac_flavors, evac_images):
	if server.flavor.get('id') in evac_flavors:
		return True
	if server.image.get('id') in evac_images:
		return True
	logging.debug("Instance %s is not evacuable" % server.image.get('id'))
	return False

def _get_evacuable_flavors():
	result = []
	flavors = nova.flavors.list()
	# Since the detailed view for all flavors doesn't provide the extra specs,
	# we need to call each of the flavor to get them.
	for flavor in flavors:
		tag = flavor.get_keys().get(EVACUABLE_TAG)
		if tag and tag.strip().lower() in TRUE_TAGS:
			result.append(flavor.id)
	return result

def _get_evacuable_images():
	result = []
	images = nova.images.list(detailed=True)
	for image in images:
		if hasattr(image, 'metadata'):
			tag = image.metadata.get(EVACUABLE_TAG)
			if tag and tag.strip().lower() in TRUE_TAGS:
				result.append(image.id)
	return result

def _host_evacuate(options):
	result = True
	images = _get_evacuable_images()
	flavors = _get_evacuable_flavors()
	servers = nova.servers.list(search_opts={'host': options["--plug"], 'all_tenants': 1 })

	if options["--instance-filtering"] == "False":
		logging.debug("Not evacuating anything")
		evacuables = []
	elif len(flavors) or len(images):
		logging.debug("Filtering images and flavors: %s %s" % (repr(flavors), repr(images)))
		# Identify all evacuable servers
		logging.debug("Checking %s" % repr(servers))
		evacuables = [server for server in servers
				if _is_server_evacuable(server, flavors, images)]
		logging.debug("Evacuating %s" % repr(evacuables))
	else:
		logging.debug("Evacuating all images and flavors")
		evacuables = servers

	if options["--no-shared-storage"] != "False":
		on_shared_storage = False
	else:
		on_shared_storage = True

	for server in evacuables:
		logging.debug("Processing %s" % server)
		if hasattr(server, 'id'):
			response = _server_evacuate(server.id, on_shared_storage)
			if response["accepted"]:
				logging.debug("Evacuated %s from %s: %s" %
					      (response["uuid"], options["--plug"], response["reason"]))
			else:
				logging.error("Evacuation of %s on %s failed: %s" %
					      (response["uuid"], options["--plug"], response["reason"]))
				result = False
		else:
			logging.error("Could not evacuate instance: %s" % server.to_dict())
			# Should a malformed instance result in a failed evacuation?
			# result = False
	return result

def set_attrd_status(host, status, options):
	logging.debug("Setting fencing status for %s to %s" % (host, status))
	run_command(options, "attrd_updater -p -n evacuate -Q -N %s -U %s" % (host, status))

def set_power_status(_, options):
	global override_status

	override_status = ""
	logging.debug("set action: " + options["--action"])

	if not nova:
		return

	if options["--action"] == "on":
		if get_power_status(_, options) == "on":
			# Forcing the service back up in case it was disabled
			nova.services.enable(options["--plug"], 'nova-compute')
			try:
				# Forcing the host back up
				nova.services.force_down(
					options["--plug"], "nova-compute", force_down=False)
			except Exception as e:
				# In theory, if force_down=False fails, that's for the exact
				# same possible reasons that below with force_down=True
				# eg. either an incompatible version or an old client.
				# Since it's about forcing back to a default value, there is
				# no real worries to just consider it's still okay even if the
				# command failed
				logging.info("Exception from attempt to force "
					      "host back up via nova API: "
					      "%s: %s" % (e.__class__.__name__, e))
		else:
			# Pretend we're 'on' so that the fencing library doesn't loop forever waiting for the node to boot
			override_status = "on"
		return

	try:
		nova.services.force_down(
			options["--plug"], "nova-compute", force_down=True)
	except Exception as e:
		# Something went wrong when we tried to force the host down.
		# That could come from either an incompatible API version
		# eg. UnsupportedVersion or VersionNotFoundForAPIMethod
		# or because novaclient is old and doesn't include force_down yet
		# eg. AttributeError
		# In that case, fallbacking to wait for Nova to catch the right state.

		logging.error("Exception from attempt to force host down via nova API: "
			      "%s: %s" % (e.__class__.__name__, e))
		# need to wait for nova to update its internal status or we
		# cannot call host-evacuate
		while get_power_status(_, options) != "off":
			# Loop forever if need be.
			#
			# Some callers (such as Pacemaker) will have a timer
			# running and kill us if necessary
			logging.debug("Waiting for nova to update its internal state for %s" % options["--plug"])
			time.sleep(1)

	if not _host_evacuate(options):
		sys.exit(1)

	return


def fix_domain(options):
	domains = {}
	last_domain = None

	if nova:
		# Find it in nova

		hypervisors = nova.hypervisors.list()
		for hypervisor in hypervisors:
			shorthost = hypervisor.hypervisor_hostname.split('.')[0]

			if shorthost == hypervisor.hypervisor_hostname:
				# Nova is not using FQDN 
				calculated = ""
			else:
				# Compute nodes are named as FQDN, strip off the hostname
				calculated = hypervisor.hypervisor_hostname.replace(shorthost+".", "")

			domains[calculated] = shorthost

			if calculated == last_domain:
				# Avoid complaining for each compute node with the same name
				# One hopes they don't appear interleaved as A.com B.com A.com B.com
				logging.debug("Calculated the same domain from: %s" % hypervisor.hypervisor_hostname)

			elif "--domain" in options and options["--domain"] == calculated:
				# Supplied domain name is valid 
				return

			elif "--domain" in options:
				# Warn in case nova isn't available at some point
				logging.warning("Supplied domain '%s' does not match the one calculated from: %s"
					      % (options["--domain"], hypervisor.hypervisor_hostname))

			last_domain = calculated

	if len(domains) == 0 and "--domain" not in options:
		logging.error("Could not calculate the domain names used by compute nodes in nova")

	elif len(domains) == 1 and "--domain" not in options:
		options["--domain"] = last_domain
		return options["--domain"]

	elif len(domains) == 1:
		logging.error("Overriding supplied domain '%s' does not match the one calculated from: %s"
			      % (options["--domain"], hypervisor.hypervisor_hostname))
		options["--domain"] = last_domain
		return options["--domain"]

	elif len(domains) > 1:
		logging.error("The supplied domain '%s' did not match any used inside nova: %s"
			      % (options["--domain"], repr(domains)))
		sys.exit(1)

	return None

def fix_plug_name(options):
	if options["--action"] == "list":
		return

	if "--plug" not in options:
		return

	calculated = fix_domain(options)
	short_plug = options["--plug"].split('.')[0]
	logging.debug("Checking target '%s' against calculated domain '%s'"% (options["--plug"], calculated))

	if "--domain" not in options:
		# Nothing supplied and nova not available... what to do... nothing
		return

	elif options["--domain"] == "":
		# Ensure any domain is stripped off since nova isn't using FQDN
		options["--plug"] = short_plug

	elif options["--plug"].find(options["--domain"]):
		# Plug already contains the domain, don't re-add 
		return

	else:
		# Add the domain to the plug
		options["--plug"] = short_plug + "." + options["--domain"]

def get_plugs_list(_, options):
	result = {}

	if nova:
		hypervisors = nova.hypervisors.list()
		for hypervisor in hypervisors:
			longhost = hypervisor.hypervisor_hostname
			shorthost = longhost.split('.')[0]
			result[longhost] = ("", None)
			result[shorthost] = ("", None)
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
	all_opt["region-name"] = {
		"getopt" : "",
		"longopt" : "region-name",
		"help" : "--region-name=[region]         Region Name",
		"required" : "0",
		"shortdesc" : "Region Name",
		"default" : "",
		"order": 1,
	}
	all_opt["insecure"] = {
		"getopt" : "",
		"longopt" : "insecure",
		"help" : "--insecure                     Explicitly allow agent to perform \"insecure\" TLS (https) requests",
		"required" : "0",
		"shortdesc" : "Allow Insecure TLS Requests",
		"default" : "False",
		"order": 2,
	}
	all_opt["domain"] = {
		"getopt" : "d:",
		"longopt" : "domain",
		"help" : "-d, --domain=[string]          DNS domain in which hosts live, useful when the cluster uses short names and nova uses FQDN",
		"required" : "0",
		"shortdesc" : "DNS domain in which hosts live",
		"order": 5,
	}
	all_opt["record-only"] = {
		"getopt" : "r:",
		"longopt" : "record-only",
		"help" : "--record-only                  Record the target as needing evacuation but as yet do not intiate it",
		"required" : "0",
		"shortdesc" : "Only record the target as needing evacuation",
		"default" : "False",
		"order": 5,
	}
	all_opt["instance-filtering"] = {
		"getopt" : "",
		"longopt" : "instance-filtering",
		"help" : "--instance-filtering           Allow instances created from images and flavors with evacuable=true to be evacuated (or all if no images/flavors have been tagged)",
		"required" : "0",
		"shortdesc" : "Allow instances to be evacuated",
		"default" : "True",
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

	device_opt = ["login", "passwd", "tenant-name", "auth-url", "fabric_fencing", "on_target",
		"no_login", "no_password", "port", "domain", "no-shared-storage", "endpoint-type",
		"record-only", "instance-filtering", "insecure", "region-name"]
	define_new_opts()
	all_opt["shell_timeout"]["default"] = "180"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for the automatic resurrection of OpenStack compute instances"
	docs["longdesc"] = "Used to tell Nova that compute nodes are down and to reschedule flagged instances"
	docs["vendorurl"] = ""

	show_docs(options, docs)

	run_delay(options)

	try:
		from novaclient import client as nova_client
	except ImportError:
		fail_usage("nova not found or not accessible")

	fix_plug_name(options)

	if options["--record-only"] in [ "2", "Disabled", "disabled" ]:
		sys.exit(0)

	elif options["--record-only"] in [ "1", "True", "true", "Yes", "yes"]:
		if options["--action"] == "on":
			set_attrd_status(options["--plug"], "no", options)
			sys.exit(0)

		elif options["--action"] in ["off", "reboot"]:
			set_attrd_status(options["--plug"], "yes", options)
			sys.exit(0)

		elif options["--action"] in ["monitor", "status"]:
			sys.exit(0)

	# The first argument is the Nova client version
	nova = nova_client.Client('2',
		options["--username"],
		options["--password"],
		options["--tenant-name"],
		options["--auth-url"],
		insecure=options["--insecure"],
		region_name=options["--region-name"],
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
