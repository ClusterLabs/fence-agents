#!/usr/bin/python

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Dummy Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		status_file = open(options["--status-file"], 'r')
	except:
		return "off"

	status = status_file.read()
	status_file.close()

	return status.lower()

def set_power_status(conn, options):
	if not (options["--action"] in [ "on", "off" ]):
		return

	status_file = open(options["--status-file"], 'w')
	status_file.write(options["--action"])
	status_file.close()

def main():
	device_opt = [ "no_password", "status_file" ]

	atexit.register(atexit_handler)

	all_opt["status_file"] = {
		"getopt" : "s:",
		"longopt" : "status-file",
		"help":"--status-file=<file>           Name of file that holds current status",
		"required" : "0",
		"shortdesc" : "File with status",
		"default" : "/tmp/fence_dummy.status",
		"order": 1
		}

	options = check_input(device_opt, process_input(device_opt))

	docs = { }
	docs["shortdesc"] = "Dummy fence agent"
	docs["longdesc"] = "fence_dummy"
	docs["vendorurl"] = "http://www.example.com"
	show_docs(options, docs)
	
	result = fence_action(None, options, set_power_status, get_power_status, None)
	sys.exit(result)

if __name__ == "__main__":
	main()
