#!@PYTHON@ -tt

import atexit
import sys
sys.path.append("@FENCEAGENTSLIBDIR@")
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay


def get_nodes_list(conn, options):
	result = {}
	try:
		instanceList = conn.instances().list(project=options["--project"], zone=options["--zone"]).execute()
		for instance in instanceList["items"]:
			status = "unknown"
			if instance["status"] == "RUNNING":
				status = "on"
			elif instance["status"] == "TERMINATED":
				status = "off"
			result[instance["id"]] = (instance["name"], status)
	# TODO: check which Exceptions it can throw
	except:
		fail_usage("Failed: Unable to connect to GCE. Check your configuration.")

	return result

def get_power_status(conn, options):
	try:
		instance = conn.instances().get(project=options["--project"], zone=options["--zone"],
						instance=options["--plug"]).execute()
		if instance["status"] == "RUNNING":
			return "on"
		elif instance["status"] == "TERMINATED":
			return "off"
		else:
			return "unknown"
	# TODO: check which Exceptions it can throw
	except:
		fail_usage("Failed: Unable to connect to GCE. Check your configuration.")

def set_power_status(conn, options):
	try:
		if (options["--action"]=="off"):
			conn.instances().stop(project=options["--project"], zone=options["--zone"],
							instance=options["--plug"]).execute()
		elif (options["--action"]=="on"):
			conn.instances().start(project=options["--project"], zone=options["--zone"],
							instance=options["--plug"]).execute()
	# TODO: check which Exceptions it can throw
	except :
		fail_usage("Failed: Unable to connect to GCE. Check your configuration.")

def define_new_opts():
	all_opt["zone"] = {
		"getopt" : ":",
		"longopt" : "zone",
		"help" : "--zone=[name]            Zone, e.g. us-central1-b",
		"shortdesc" : "Zone.",
		"required" : "0",
		"order" : 2
	}
	all_opt["project"] = {
		"getopt" : ":",
		"longopt" : "project",
		"help" : "--project=[name]            Project",
		"shortdesc" : "Project.",
		"required" : "0",
		"order" : 3
	}

def main():
	conn = None

	device_opt = ["port", "no_password", "zone", "project"]

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

	try:
		credentials = GoogleCredentials.get_application_default()
		conn = discovery.build('compute', 'v1', credentials=credentials)
	except:
		fail_usage("Failed: Unable to connect to GCE. Check your configuration.")

	# Operate the fencing device
	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
	sys.exit(result)

if __name__ == "__main__":
	main()
