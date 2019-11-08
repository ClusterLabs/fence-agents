#!/usr/libexec/platform-python -tt

import io
import re
import subprocess
import shlex
import sys, stat
import logging
import atexit
import time
sys.path.append("/usr/share/fence")
from fencing import fail_usage, run_command, fence_action, all_opt
from fencing import atexit_handler, check_input, process_input, show_docs
from fencing import run_delay

def heuristics_resource(con, options):
	# Search the node where the resource is running and determine
	# the ACT node or not. For SBY node, a delay is generated.
	# Note that this method always returns FALSE.

	if not "--nodename" in options or options["--nodename"] == "":
		logging.error("nodename parameter required")
		return False

	if not "--resource" in options or options["--resource"] == "":
		logging.error("resource parameter required")
		return False

	target = options["--nodename"]
	resource = options["--resource"]
	promotable = options["--promotable"] in ["", "1"]
	standby_wait = int(options["--standby-wait"])
	crm_resource_path = options["--crm-resource-path"]
	crm_node_path = options["--crm-node-path"]

	(rc, out, err) = run_command(options, "%s --name" % crm_node_path)
	if rc != 0 or out == None:
		logging.error("Can not get my nodename. rc=%s, stderr=%s" % (rc, err))
		return False

	mynodename = out.strip()

	if mynodename == target:
		logging.info("Skip standby wait due to self-fencing.")
		return False

	(rc, out, err) = run_command(options, "%s -r %s -W" % (crm_resource_path, resource))
	if rc != 0 or out == None:
		logging.error("Command failed. rc=%s, stderr=%s" % (rc, err))
		return False

	search_str = re.compile(r"\s%s%s$" % (mynodename, '\sMaster' if promotable else ''))
	for line in out.splitlines():
		searchres = search_str.search(line.strip())
		if searchres:
			logging.info("This node is ACT! Skip standby wait.")
			return False

	logging.info("Resource %s NOT found on this node" % resource)

	if standby_wait > 0:
		# The SBY node waits for fencing from the ACT node, and tries to fence
		# the ACT node on next fencing level waking up from sleep.
		logging.info("Standby wait %s sec" % standby_wait)
		time.sleep(standby_wait)
		
	return False


def define_new_opts():
	all_opt["nodename"] = {
		"getopt" : "n:",
		"longopt" : "nodename",
		"required" : "1",
		"help" : "-n, --nodename=[nodename]      Name of node to be fenced",
		"shortdesc" : "Name of node to be fenced",
		"default" : "",
		"order" : 1
		}
	all_opt["resource"] = {
		"getopt" : "r:",
		"longopt" : "resource",
		"required" : "1",
		"help" : "-r, --resource=[resource-id]   ID of the resource that should be running in the ACT node",
		"shortdesc" : "Resource ID",
		"default" : "",
		"order" : 1
		}
	all_opt["promotable"] = {
		"getopt" : "p",
		"longopt" : "promotable",
		"required" : "0",
		"help" : "-p, --promotable               Specify if resource parameter is promotable (master/slave) resource",
		"shortdesc" : "Handle the promotable resource. The node on which the master resource is running is considered as ACT.",
		"default" : "False",
		"order" : 1
		}
	all_opt["standby_wait"] = {
		"getopt" : "w:",
		"longopt" : "standby-wait",
		"required" : "0",
		"help" : "-w, --standby-wait=[seconds]   Wait X seconds on SBY node. If a positive number is specified, fencing action of this agent will always succeed after waits.",
		"shortdesc" : "Wait X seconds on SBY node. If a positive number is specified, fencing action of this agent will always succeed after waits.",
		"default" : "0",
		"order" : 1
		}
	all_opt["crm_resource_path"] = {
		"getopt" : ":",
		"longopt" : "crm-resource-path",
		"required" : "0",
		"help" : "--crm-resource-path=[path]     Path to crm_resource",
		"shortdesc" : "Path to crm_resource command",
		"default" : "@CRM_RESOURCE_PATH@",
		"order" : 1
		}
	all_opt["crm_node_path"] = {
		"getopt" : ":",
		"longopt" : "crm-node-path",
		"required" : "0",
		"help" : "--crm-node-path=[path]         Path to crm_node",
		"shortdesc" : "Path to crm_node command",
		"default" : "@CRM_NODE_PATH@",
		"order" : 1
		}


def main():
	device_opt = ["no_status", "no_password", "nodename", "resource", "promotable", "standby_wait", "crm_resource_path", "crm_node_path", "method"]
	define_new_opts()
	atexit.register(atexit_handler)

	all_opt["method"]["default"] = "cycle"
	all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (cycle|onoff) (Default: cycle)"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for resource-heuristic based fencing delay"
	docs["longdesc"] = "fence_heuristics_resource uses resource-heuristics to delay execution of fence agent running on next level.\
\n.P\n\
This is not a fence agent by itself! \
Its only purpose is to delay execution of another fence agent that lives on next fencing level. \
Note that this agent always returns FALSE. Therefore, subsequent agents on the same fencing level will not run"
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
