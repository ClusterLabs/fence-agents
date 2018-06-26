#!@PYTHON@ -tt

import atexit
import logging
import platform
import sys
import time
sys.path.append("@FENCEAGENTSLIBDIR@")

import googleapiclient.discovery
from fencing import fail_usage, run_delay, all_opt, atexit_handler, check_input, process_input, show_docs, fence_action


LOGGER = logging


def translate_status(instance_status):
	"Returns on | off | unknown."
	if instance_status == "RUNNING":
		return "on"
	elif instance_status == "TERMINATED":
		return "off"
	return "unknown"


def get_nodes_list(conn, options):
	result = {}
	try:
		instanceList = conn.instances().list(project=options["--project"], zone=options["--zone"]).execute()
		for instance in instanceList["items"]:
			result[instance["id"]] = (instance["name"], translate_status(instance["status"]))
	except Exception as err:
		fail_usage("Failed: get_nodes_list: {}".format(str(err)))

	return result


def get_power_status(conn, options):
	try:
		instance = conn.instances().get(
				project=options["--project"],
				zone=options["--zone"],
				instance=options["--plug"]).execute()
		return translate_status(instance["status"])
	except Exception as err:
		fail_usage("Failed: get_power_status: {}".format(str(err)))


def wait_for_operation(conn, project, zone, operation):
	while True:
		result = conn.zoneOperations().get(
			project=project,
			zone=zone,
			operation=operation['name']).execute()
		if result['status'] == 'DONE':
			if 'error' in result:
				raise Exception(result['error'])
			return
		time.sleep(1)


def set_power_status(conn, options):
	try:
		if options["--action"] == "off":
			LOGGER.info("Issuing poweroff of %s in zone %s" % (options["--plug"], options["--zone"]))
			operation = conn.instances().stop(
					project=options["--project"],
					zone=options["--zone"],
					instance=options["--plug"]).execute()
			wait_for_operation(conn, options["--project"], options["--zone"], operation)
			LOGGER.info("Poweroff of %s in zone %s complete" % (options["--plug"], options["--zone"]))
		elif options["--action"] == "on":
			LOGGER.info("Issuing poweron of %s in zone %s" % (options["--plug"], options["--zone"]))
			operation = conn.instances().start(
					project=options["--project"],
					zone=options["--zone"],
					instance=options["--plug"]).execute()
			wait_for_operation(conn, options["--project"], options["--zone"], operation)
			LOGGER.info("Poweron of %s in zone %s complete" % (options["--plug"], options["--zone"]))
	except Exception as err:
		fail_usage("Failed: set_power_status: {}".format(str(err)))


def define_new_opts():
	all_opt["zone"] = {
		"getopt" : ":",
		"longopt" : "zone",
		"help" : "--zone=[name]                  Zone, e.g. us-central1-b",
		"shortdesc" : "Zone.",
		"required" : "1",
		"order" : 2
	}
	all_opt["project"] = {
		"getopt" : ":",
		"longopt" : "project",
		"help" : "--project=[name]               Project ID",
		"shortdesc" : "Project ID.",
		"required" : "1",
		"order" : 3
	}
	all_opt["logging"] = {
		"getopt" : ":",
		"longopt" : "logging",
		"help" : "--logging=[bool]               Logging, true/false",
		"shortdesc" : "Stackdriver-logging support.",
		"longdesc" : "If enabled (set to true), IP failover logs will be posted to stackdriver logging.",
		"required" : "0",
		"default" : "false",
		"order" : 4
	}

def main():
	conn = None
	global LOGGER

	hostname = platform.node()

	device_opt = ["port", "no_password", "zone", "project", "logging"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["power_timeout"]["default"] = "60"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for GCE (Google Cloud Engine)"
	docs["longdesc"] = "fence_gce is an I/O Fencing agent for GCE (Google Cloud " \
			   "Engine). It uses the googleapiclient library to connect to GCE.\n" \
			   "googleapiclient can be configured with Google SDK CLI or by " \
			   "executing 'gcloud auth application-default login'.\n" \
			   "For instructions see: https://cloud.google.com/compute/docs/tutorials/python-guide"
	docs["vendorurl"] = "http://cloud.google.com"
	show_docs(options, docs)

	run_delay(options)

	# Prepare logging
	logging_env = options.get('--logging')
	if logging_env:
		logging_env = logging_env.lower()
		if any(x in logging_env for x in ['yes', 'true', 'enabled']):
			try:
				import google.cloud.logging.handlers
				client = google.cloud.logging.Client()
				handler = google.cloud.logging.handlers.CloudLoggingHandler(client, name=hostname)
				formatter = logging.Formatter('gcp:stonish "%(message)s"')
				LOGGER = logging.getLogger(hostname)
				handler.setFormatter(formatter)
				LOGGER.addHandler(handler)
				LOGGER.setLevel(logging.INFO)
			except ImportError:
				LOGGER.error('Couldn\'t import google.cloud.logging, '
					'disabling Stackdriver-logging support')

	# Prepare cli
	try:
		credentials = None
		if tuple(googleapiclient.__version__) < tuple("1.6.0"):
			import oauth2client.client
			credentials = oauth2client.client.GoogleCredentials.get_application_default()
		conn = googleapiclient.discovery.build('compute', 'v1', credentials=credentials)
	except Exception as err:
		fail_usage("Failed: Create GCE compute v1 connection: {}".format(str(err)))

	# Operate the fencing device
	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
	sys.exit(result)

if __name__ == "__main__":
	main()
