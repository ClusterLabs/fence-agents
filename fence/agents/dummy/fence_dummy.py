#!/usr/bin/python -tt

import sys, random
import logging
import time
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Dummy Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

plug_status = "on"

def get_power_status_file(conn, options):
	del conn

	try:
		status_file = open(options["--status-file"], 'r')
	except Exception:
		return "off"

	status = status_file.read()
	status_file.close()

	return status.lower()

def set_power_status_file(conn, options):
	del conn

	if not (options["--action"] in ["on", "off"]):
		return

	status_file = open(options["--status-file"], 'w')
	status_file.write(options["--action"])
	status_file.close()

def get_power_status_fail(conn, options):
	outlets = get_outlets_fail(conn, options)

	if len(outlets) == 0 or not options.has_key("--plug"):
		fail_usage("Failed: You have to enter existing machine!")
	else:
		return outlets[options["--plug"]][0]

def set_power_status_fail(conn, options):
	global plug_status
	del conn

	plug_status = "unknown"
	if options["--action"] == "on":
		plug_status = "off"

def get_outlets_fail(conn, options):
	del conn

	result = {}
	global plug_status

	if options["--action"] == "on":
		plug_status = "off"

	# This fake agent has no port data to list, so we have to make
	# something up for the list action.
	if options.get("--action", None) == "list":
		result["fake_port_1"] = [plug_status, "fake"]
		result["fake_port_2"] = [plug_status, "fake"]
	elif not options.has_key("--plug"):
		fail_usage("Failed: You have to enter existing machine!")
	else:
		port = options["--plug"]
		result[port] = [plug_status, "fake"]

	return result

def main():
	device_opt = ["no_password", "status_file", "random_sleep_range", "type", "port"]

	atexit.register(atexit_handler)

	all_opt["status_file"] = {
		"getopt" : ":",
		"longopt" : "status-file",
		"help":"--status-file=[file]           Name of file that holds current status",
		"required" : "0",
		"shortdesc" : "File with status",
		"default" : "/tmp/fence_dummy.status",
		"order": 1
		}

	all_opt["random_sleep_range"] = {
		"getopt" : ":",
		"longopt" : "random_sleep_range",
		"help":"--random_sleep_range=[seconds] Issue a sleep between 1 and [seconds]",
		"required" : "0",
		"shortdesc" : "Issue a sleep between 1 and X seconds. Used for testing.",
		"order": 1
		}

	all_opt["type"] = {
		"getopt" : ":",
		"longopt" : "type",
		"help":"--type=[type]                  Possible types are: file and fail",
		"required" : "0",
		"shortdesc" : "Type of the dummy fence agent",
		"default" : "file",
		"order": 1
		}

	pinput = process_input(device_opt)
	if (pinput.has_key("--type") and pinput["--type"] == "file") or (pinput.has_key("--type") == False):
		# hack to have fence agents that require ports 'fail' and one that do not 'file'
		device_opt.remove("port")

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Dummy fence agent"
	docs["longdesc"] = "fence_dummy"
	docs["vendorurl"] = "http://www.example.com"
	show_docs(options, docs)

	# random sleep for testing
	if options.has_key("--random_sleep_range"):
		val = int(options["--random_sleep_range"])
		ran = random.randint(1, val)
		logging.info("Random sleep for %d seconds\n", ran)
		time.sleep(ran)

	if options["--type"] == "fail":
		result = fence_action(None, options, set_power_status_fail, get_power_status_fail, get_outlets_fail)
	else:
		result = fence_action(None, options, set_power_status_file, get_power_status_file, None)

	sys.exit(result)

if __name__ == "__main__":
	main()
