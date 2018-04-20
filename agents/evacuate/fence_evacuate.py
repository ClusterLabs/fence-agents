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

EVACUABLE_TAG = "evacuable"
TRUE_TAGS = ['true']

def get_power_status(connection, options):

	status = "unknown"
	logging.debug("get action: " + options["--action"])

	if connection:
		try:
			services = connection.services.list(host=options["--plug"], binary="nova-compute")
			for service in services:
				logging.debug("Status of %s is %s, %s" % (service.binary, service.state, service.status))
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
	return status

# NOTE(sbauza); We mimic the host-evacuate module since it's only a contrib
# module which is not stable
def _server_evacuate(connection, server, on_shared_storage):
	success = False
	error_message = ""
	try:
		logging.debug("Resurrecting instance: %s" % server)
		(response, dictionary) = connection.servers.evacuate(server=server, on_shared_storage=on_shared_storage)

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
	if hasattr(server.image, 'get'):
		if server.image.get('id') in evac_images:
			return True
	logging.debug("Instance %s is not evacuable" % server.image.get('id'))
	return False

def _get_evacuable_flavors(connection):
	result = []
	flavors = connection.flavors.list()
	# Since the detailed view for all flavors doesn't provide the extra specs,
	# we need to call each of the flavor to get them.
	for flavor in flavors:
		tag = flavor.get_keys().get(EVACUABLE_TAG)
		if tag and tag.strip().lower() in TRUE_TAGS:
			result.append(flavor.id)
	return result

def _get_evacuable_images(connection):
	result = []
	images = []
	if hasattr(connection, "images"):
		images = connection.images.list(detailed=True)
	elif hasattr(connection, "glance"):
		# OSP12+
		images = connection.glance.list()

	for image in images:
		if hasattr(image, 'metadata'):
			tag = image.metadata.get(EVACUABLE_TAG)
			if tag and tag.strip().lower() in TRUE_TAGS:
				result.append(image.id)
		elif hasattr(image, 'tags'):
			# OSP12+
			if EVACUABLE_TAG in image.tags:
				result.append(image.id)
	return result

def _host_evacuate(connection, options):
	result = True
	images = _get_evacuable_images(connection)
	flavors = _get_evacuable_flavors(connection)
	servers = connection.servers.list(search_opts={'host': options["--plug"], 'all_tenants': 1 })

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
			response = _server_evacuate(connection, server.id, on_shared_storage)
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

def set_power_status(connection, options):
	logging.debug("set action: " + options["--action"])

	if not connection:
		return

	if options["--action"] == "off" and not _host_evacuate(options):
		sys.exit(1)

	sys.exit(0)

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

	versions = [ "2.11", "2" ]
	for version in versions:
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

	logging.warning("Couldn't obtain a supported connection to nova, tried: %s\n" % repr(versions))
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
		"help" : "-k, --auth-url=[url]                   Keystone Admin Auth URL",
		"required" : "0",
		"shortdesc" : "Keystone Admin Auth URL",
		"default" : "",
		"order": 1,
	}
	all_opt["region_name"] = {
		"getopt" : "",
		"longopt" : "region-name",
		"help" : "--region-name=[region]                 Region Name",
		"required" : "0",
		"shortdesc" : "Region Name",
		"default" : "",
		"order": 1,
	}
	all_opt["insecure"] = {
		"getopt" : "",
		"longopt" : "insecure",
		"help" : "--insecure                                     Explicitly allow agent to perform \"insecure\" TLS (https) requests",
		"required" : "0",
		"shortdesc" : "Allow Insecure TLS Requests",
		"default" : "False",
		"order": 2,
	}
	all_opt["domain"] = {
		"getopt" : "d:",
		"longopt" : "domain",
		"help" : "-d, --domain=[string]                  DNS domain in which hosts live, useful when the cluster uses short names and nova uses FQDN",
		"required" : "0",
		"shortdesc" : "DNS domain in which hosts live",
		"order": 5,
	}
	all_opt["instance_filtering"] = {
		"getopt" : "",
		"longopt" : "instance-filtering",
		"help" : "--instance-filtering                   Allow instances created from images and flavors with evacuable=true to be evacuated (or all if no images/flavors have been tagged)",
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

def main():
	atexit.register(atexit_handler)

	device_opt = ["login", "passwd", "tenant_name", "auth_url",
		      "no_login", "no_password", "port", "domain", "project_domain",
		      "user_domain", "no_shared_storage", "endpoint_type",
		      "instance_filtering", "insecure", "region_name"]
	define_new_opts()
	all_opt["shell_timeout"]["default"] = "180"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for the automatic resurrection of OpenStack compute instances"
	docs["longdesc"] = "Used to reschedule flagged instances"
	docs["vendorurl"] = ""

	show_docs(options, docs)

	run_delay(options)

	connection = create_nova_connection(options)

	# Un-evacuating a server doesn't make sense
	if options["--action"] in ["on"]:
		logging.error("Action %s is not supported by this agent" % (options["--action"]))
		sys.exit(1)

	if options["--action"] in ["off", "reboot"]:
		status = get_power_status(connection, options)
		if status != "off":
			logging.error("Cannot resurrect instances from %s in state '%s'" % (options["--plug"], status))
			sys.exit(1)

		elif not _host_evacuate(connection, options):
			logging.error("Resurrection of instances from %s failed" % (options["--plug"]))
			sys.exit(1)

		logging.info("Resurrection of instances from %s complete" % (options["--plug"]))
		sys.exit(0)

	result = fence_action(connection, options, set_power_status, get_power_status, get_plugs_list, None)
	sys.exit(result)

if __name__ == "__main__":
	main()
