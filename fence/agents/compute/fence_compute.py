#!@PYTHON@ -tt

import sys
import time
import atexit
import logging
import inspect
import requests.exceptions

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, is_executable, run_command, run_delay

override_status = ""

EVACUABLE_TAG = "evacuable"
TRUE_TAGS = ['true']

def get_power_status(connection, options):

	if len(override_status):
		logging.debug("Pretending we're " + override_status)
		return override_status

	status = "unknown"
	logging.debug("get action: " + options["--action"])

	if connection:
		try:
			services = connection.services.list(host=options["--plug"], binary="nova-compute")
			for service in services:
				logging.debug("Status of %s on %s is %s, %s" % (service.binary, options["--plug"], service.state, service.status))
				if service.state == "up" and service.status == "enabled":
					# Up and operational
					status = "on"
					
				elif service.state == "down" and service.status == "disabled":
					# Down and fenced
					status = "off"

				elif service.state == "down":
					# Down and requires fencing
					status = "failed"

				elif service.state == "up":
					# Up and requires unfencing
					status = "running"
				else:
					logging.warning("Unknown status detected from nova for %s: %s, %s" % (options["--plug"], service.state, service.status))
					status = "%s %s" % (service.state, service.status)
				break
		except requests.exception.ConnectionError as err:
			logging.warning("Nova connection failed: " + str(err))
	logging.debug("Final status of %s is %s" % (options["--plug"], status))
	return status

def get_power_status_simple(connection, options):
	status = get_power_status(connection, options)
	if status in [ "off" ]:
		return status
	return "on"

def set_attrd_status(host, status, options):
	logging.debug("Setting fencing status for %s to %s" % (host, status))
	run_command(options, "attrd_updater -p -n evacuate -Q -N %s -U %s" % (host, status))

def get_attrd_status(host, options):
	(status, pipe_stdout, pipe_stderr) = run_command(options, "attrd_updater -p -n evacuate -Q -N %s" % (host))
	fields = pipe_stdout.split('"')
	if len(fields) > 6:
		return fields[5]
	logging.debug("Got %s: o:%s e:%s n:%d" % (status, pipe_stdout, pipe_stderr, len(fields)))
	return ""

def set_power_status_on(connection, options):
	# Wait for any evacuations to complete
	while True:
		current = get_attrd_status(options["--plug"], options)
		if current in ["no", ""]:
			logging.info("Evacuation complete for: %s '%s'" % (options["--plug"], current))
			break
		else:
			logging.info("Waiting for %s to complete evacuations: %s" % (options["--plug"], current))
			time.sleep(2)

	status = get_power_status(connection, options)
	# Should we do it for 'failed' too?
	if status in [ "off", "running", "failed" ]:
		try:
			# Forcing the host back up
			logging.info("Forcing nova-compute back up on "+options["--plug"])
			connection.services.force_down(options["--plug"], "nova-compute", force_down=False)
			logging.info("Forced nova-compute back up on "+options["--plug"])
		except Exception as e:
			# In theory, if force_down=False fails, that's for the exact
			# same possible reasons that below with force_down=True
			# eg. either an incompatible version or an old client.
			# Since it's about forcing back to a default value, there is
			# no real worries to just consider it's still okay even if the
			# command failed
			logging.warn("Exception from attempt to force "
				      "host back up via nova API: "
				      "%s: %s" % (e.__class__.__name__, e))

		# Forcing the service back up in case it was disabled
		logging.info("Enabling nova-compute on "+options["--plug"])
		connection.services.enable(options["--plug"], 'nova-compute')

		# Pretend we're 'on' so that the fencing library doesn't loop forever waiting for the node to boot
		override_status = "on"
	elif status not in ["on"]:
		# Not safe to unfence, don't waste time looping to see if the status changes to "on"
		options["--power-timeout"] = "0"

def set_power_status_off(connection, options):
	status = get_power_status(connection, options)
	if status in [ "off" ]:
		return

	connection.services.disable(options["--plug"], 'nova-compute')
	try:
		# Until 2.53
		connection.services.force_down(
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
		while get_power_status(connection, options) not in ["off"]:
			# Loop forever if need be.
			#
			# Some callers (such as Pacemaker) will have a timer
			# running and kill us if necessary
			logging.debug("Waiting for nova to update its internal state for %s" % options["--plug"])
			time.sleep(1)

	set_attrd_status(options["--plug"], "yes", options)

def set_power_status(connection, options):
	global override_status

	override_status = ""
	logging.debug("set action: " + options["--action"])

	if not connection:
		return

	if options["--action"] in ["off", "reboot"]:
		set_power_status_off(connection, options)
	else:
		set_power_status_on(connection, options)
	logging.debug("set action passed: " + options["--action"])
	sys.exit(0)

def fix_domain(connection, options):
	domains = {}
	last_domain = None

	if connection:
		# Find it in nova

		services = connection.services.list(binary="nova-compute")
		for service in services:
			shorthost = service.host.split('.')[0]

			if shorthost == service.host:
				# Nova is not using FQDN 
				calculated = ""
			else:
				# Compute nodes are named as FQDN, strip off the hostname
				calculated = service.host.replace(shorthost+".", "")

			if calculated == last_domain:
				# Avoid complaining for each compute node with the same name
				# One hopes they don't appear interleaved as A.com B.com A.com B.com
				logging.debug("Calculated the same domain from: %s" % service.host)
				continue

			domains[calculated] = service.host
			last_domain = calculated

			if "--domain" in options and options["--domain"] != calculated:
				# Warn in case nova isn't available at some point
				logging.warning("Supplied domain '%s' does not match the one calculated from: %s"
					      % (options["--domain"], service.host))

	if len(domains) == 0 and "--domain" not in options:
		logging.error("Could not calculate the domain names used by compute nodes in nova")

	elif len(domains) == 1 and "--domain" not in options:
		options["--domain"] = last_domain

	elif len(domains) == 1 and options["--domain"] != last_domain:
		logging.error("Overriding supplied domain '%s' as it does not match the one calculated from: %s"
			      % (options["--domain"], domains[last_domain]))
		options["--domain"] = last_domain

	elif len(domains) > 1:
		logging.error("The supplied domain '%s' did not match any used inside nova: %s"
			      % (options["--domain"], repr(domains)))
		sys.exit(1)

	return last_domain

def fix_plug_name(connection, options):
	if options["--action"] == "list":
		return

	if "--plug" not in options:
		return

	calculated = fix_domain(connection, options)
	if calculated is None or "--domain" not in options:
		# Nothing supplied and nova not available... what to do... nothing
		return

	short_plug = options["--plug"].split('.')[0]
	logging.debug("Checking target '%s' against calculated domain '%s'"% (options["--plug"], calculated))

	if options["--domain"] == "":
		# Ensure any domain is stripped off since nova isn't using FQDN
		options["--plug"] = short_plug

	elif options["--plug"].endswith(options["--domain"]):
		# Plug already uses the domain, don't re-add
		return

	else:
		# Add the domain to the plug
		options["--plug"] = short_plug + "." + options["--domain"]

def get_plugs_list(connection, options):
	result = {}

	if connection:
		services = connection.services.list(binary="nova-compute")
		for service in services:
			longhost = service.host
			shorthost = longhost.split('.')[0]
			result[longhost] = ("", None)
			result[shorthost] = ("", None)
	return result

def create_nova_connection(options):
	nova = None

	try:
		from novaclient import client
		from novaclient.exceptions import NotAcceptable
	except ImportError:
		fail_usage("Nova not found or not accessible")

	from keystoneauth1 import loading
	from keystoneauth1 import session
	from keystoneclient import discover

	# Prefer the oldest and strip the leading 'v'
	keystone_versions = discover.available_versions(options["--auth-url"])
	keystone_version = keystone_versions[0]['id'][1:]
	kwargs = dict(
		auth_url=options["--auth-url"],
		username=options["--username"],
		password=options["--password"]
		)

	if discover.version_match("2", keystone_version):
		kwargs["tenant_name"] = options["--tenant-name"]

	elif discover.version_match("3", keystone_version):
		kwargs["project_name"] = options["--tenant-name"]
		kwargs["user_domain_name"] = options["--user-domain"]
		kwargs["project_domain_name"] = options["--project-domain"]

	loader = loading.get_plugin_loader('password')
	keystone_auth = loader.load_from_options(**kwargs)
	keystone_session = session.Session(auth=keystone_auth, verify=(not options["--insecure"]))

	nova_versions = [ "2.11", "2" ]
	for version in nova_versions:
		clientargs = inspect.getargspec(client.Client).varargs
		# Some versions of Openstack prior to Ocata only
		# supported positional arguments for username,
		# password, and tenant.
		#
		# Versions since Ocata only support named arguments.
		#
		# So we need to use introspection to figure out how to
		# create a Nova client.
		#
		# Happy days
		#
		if clientargs:
			# OSP < 11
			# ArgSpec(args=['version', 'username', 'password', 'project_id', 'auth_url'],
			#	 varargs=None,
			#	 keywords='kwargs', defaults=(None, None, None, None))
			nova = client.Client(version,
					     None, # User
					     None, # Password
					     None, # Tenant
					     None, # Auth URL
					     insecure=options["--insecure"],
					     region_name=options["--region-name"],
					     endpoint_type=options["--endpoint-type"],
					     session=keystone_session, auth=keystone_auth,
					     http_log_debug=options.has_key("--verbose"))
		else:
			# OSP >= 11
			# ArgSpec(args=['version'], varargs='args', keywords='kwargs', defaults=None)
			nova = client.Client(version,
					     region_name=options["--region-name"],
					     endpoint_type=options["--endpoint-type"],
					     session=keystone_session, auth=keystone_auth,
					     http_log_debug=options.has_key("--verbose"))

		try:
			nova.hypervisors.list()
			return nova

		except NotAcceptable as e:
			logging.warning(e)

		except Exception as e:
			logging.warning("Nova connection failed. %s: %s" % (e.__class__.__name__, e))

	logging.warning("Couldn't obtain a supported connection to nova, tried: %s\n" % repr(nova_versions))
	return None

def define_new_opts():
	all_opt["endpoint_type"] = {
		"getopt" : "e:",
		"longopt" : "endpoint-type",
		"help" : "-e, --endpoint-type=[endpoint] Nova Endpoint type (publicURL, internalURL, adminURL)",
		"required" : "0",
		"shortdesc" : "Nova Endpoint type",
		"default" : "internalURL",
		"order": 1,
	}
	all_opt["tenant_name"] = {
		"getopt" : "t:",
		"longopt" : "tenant-name",
		"help" : "-t, --tenant-name=[name]       Keystone v2 Tenant or v3 Project Name",
		"required" : "0",
		"shortdesc" : "Keystone Admin Tenant or v3 Project",
		"default" : "",
		"order": 1,
	}
	all_opt["user_domain"] = {
		"getopt" : "u:",
		"longopt" : "user-domain",
		"help" : "-u, --user-domain=[name]       Keystone v3 User Domain",
		"required" : "0",
		"shortdesc" : "Keystone v3 User Domain",
		"default" : "Default",
		"order": 2,
	}
	all_opt["project_domain"] = {
		"getopt" : "P:",
		"longopt" : "project-domain",
		"help" : "-d, --project-domain=[name]    Keystone v3 Project Domain",
		"required" : "0",
		"shortdesc" : "Keystone v3 Project Domain",
		"default" : "Default",
		"order": 2,
	}
	all_opt["auth_url"] = {
		"getopt" : "k:",
		"longopt" : "auth-url",
		"help" : "-k, --auth-url=[url]           Keystone Admin Auth URL",
		"required" : "0",
		"shortdesc" : "Keystone Admin Auth URL",
		"default" : "",
		"order": 1,
	}
	all_opt["region_name"] = {
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
	all_opt["record_only"] = {
		"getopt" : "r:",
		"longopt" : "record-only",
		"help" : "--record-only                  Record the target as needing evacuation but as yet do not intiate it",
		"required" : "0",
		"shortdesc" : "Only record the target as needing evacuation",
		"default" : "False",
		"order": 5,
	}
	all_opt["instance_filtering"] = {
		"getopt" : "",
		"longopt" : "instance-filtering",
		"help" : "--instance-filtering           Allow instances created from images and flavors with evacuable=true to be evacuated (or all if no images/flavors have been tagged)",
		"required" : "0",
		"shortdesc" : "Allow instances to be evacuated",
		"default" : "True",
		"order": 5,
	}
	all_opt["no_shared_storage"] = {
		"getopt" : "",
		"longopt" : "no-shared-storage",
		"help" : "--no-shared-storage            Disable functionality for shared storage",
		"required" : "0",
		"shortdesc" : "Disable functionality for dealing with shared storage",
		"default" : "False",
		"order": 5,
	}

def set_multi_power_fn(connection, options, set_power_fn, get_power_fn, retry_attempts=1):
	for _ in range(retry_attempts):
		set_power_fn(connection, options)
		time.sleep(int(options["--power-wait"]))

		for _ in range(int(options["--power-timeout"])):
			if get_power_fn(connection, options) != options["--action"]:
				time.sleep(1)
			else:
				return True
	return False

def main():
	global override_status
	atexit.register(atexit_handler)

	device_opt = ["login", "passwd", "tenant_name", "auth_url", "fabric_fencing",
		      "no_login", "no_password", "port", "domain", "project_domain", "user_domain",
		      "no_shared_storage", "endpoint_type", "record_only", "instance_filtering", "insecure", "region_name"]
	define_new_opts()
	all_opt["shell_timeout"]["default"] = "180"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for the automatic resurrection of OpenStack compute instances"
	docs["longdesc"] = "Used to tell Nova that compute nodes are down and to reschedule flagged instances"
	docs["vendorurl"] = ""

	show_docs(options, docs)

	if options["--record-only"] in [ "2", "Disabled", "disabled" ]:
		sys.exit(0)

	run_delay(options)

	logging.debug("Running "+options["--action"])
	connection = create_nova_connection(options)

	if options["--action"] in ["off", "on", "reboot", "status"]:
		fix_plug_name(connection, options)


	if options["--action"] in ["reboot"]:
		options["--action"]="off"

	if options["--action"] in ["off", "on"]:
		# No status first, call our own version
		result = not set_multi_power_fn(connection, options, set_power_status, get_power_status_simple,
						1 + int(options["--retry-on"]))
	elif options["--action"] in ["monitor"]:
		result = 0
	else:
		result = fence_action(connection, options, set_power_status, get_power_status_simple, get_plugs_list, None)

	logging.debug("Result for "+options["--action"]+": "+repr(result))
	if result == None:
		result = 0
	sys.exit(result)

if __name__ == "__main__":
	main()
