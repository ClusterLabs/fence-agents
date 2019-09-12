#!/usr/libexec/platform-python -tt

import io
import re
import subprocess
import shlex
import sys, stat
import logging
import os
import atexit
import time
sys.path.append("/usr/share/fence")
from fencing import fail_usage, run_command, fence_action, all_opt
from fencing import atexit_handler, check_input, process_input, show_docs
from fencing import run_delay

def heuristics_resource(con, options):

	if options["--action"] == "on":
		return True

	if not "--resource" in options or options["--resource"] == "":
		logging.error("resource parameter required")
		return False

	crm_resource_path = options["--crm-resource-path"]
	resource = options["--resource"]
	standby_wait = int(options["--standby-wait"])
	p = None
	cmd = "%s -r %s -W" % (crm_resource_path, resource)
	search_str = re.compile(r"\s%s$" % os.uname()[1])

	logging.info("Running command: %s", cmd)
	try:
		p = subprocess.Popen(shlex.split(cmd),
			stdout=subprocess.PIPE);
	except OSError:
		logging.error("Command failed on OS level");
		return False

	if p != None: 
		p.wait()
		if p.returncode == 0:
			for line in p.stdout:
				searchres = search_str.search(line.decode().strip())
				if searchres:
					# This node is ACT! Continue fencing.
					return True
			logging.info("Resource %s NOT found on this node" % resource);
		else:
			logging.error("Command failed. rc=%s" % p.returncode);

	if standby_wait > 0:
		# The SBY node waits for fencing from the ACT node, and
		# tries to fencing to the ACT node when waking up from sleep.
		logging.info("Standby wait %s sec" % standby_wait);
		time.sleep(standby_wait)
		return True
		
	return False


def define_new_opts():
	all_opt["resource"] = {
		"getopt" : ":",
		"longopt" : "resource",
		"required" : "1",
		"help" : "--resource=[resource-id] ID of the resource that should be running in the ACT node",
		"shortdesc" : "Resource ID",
		"default" : "",
		"order" : 1
		}
	all_opt["standby_wait"] = {
		"getopt" : ":",
		"longopt" : "standby-wait",
		"required" : "0",
		"help" : "--standby-wait=[seconds] Wait X seconds on SBY node. If a positive number is specified, fencing action of this agent will always succeed after waits.",
		"shortdesc" : "Wait X seconds on SBY node. If a positive number is specified, fencing action of this agent will always succeed after waits.",
		"default" : "0",
		"order" : 1
		}
	all_opt["crm_resource_path"] = {
		"getopt" : ":",
		"longopt" : "crm-resource-path",
		"required" : "0",
		"help" : "--crm-resource-path=[path] Path to crm_resource",
		"shortdesc" : "Path to crm_resource",
		"default" : "@CRM_RESOURCE_PATH@",
		"order" : 1
		}


def main():
	device_opt = ["no_status", "no_password", "resource", "standby_wait", "crm_resource_path", "method"]
	define_new_opts()
	atexit.register(atexit_handler)

	all_opt["method"]["default"] = "cycle"
	all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (cycle|onoff) (Default: cycle)"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for resource-heuristic based fencing"
	docs["longdesc"] = "fence_heuristics_resource uses resource-heuristics to control execution of another fence agent on the same fencing level.\
\n.P\n\
This is not a fence agent by itself! \
Its only purpose is to enable/disable another fence agent that lives on the same fencing level but after fence_heuristic_resource."
	docs["vendorurl"] = ""
	show_docs(options, docs)

	run_delay(options)

	result = fence_action(\
				None, \
				options, \
				None, \
				None, \
				reboot_cycle_fn = heuristics_resource,
				sync_set_power_fn = heuristics_resource)

	sys.exit(result)

if __name__ == "__main__":
	main()
