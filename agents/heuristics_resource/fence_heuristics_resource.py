#!@PYTHON@ -tt

import io
import re
import subprocess
import shlex
import sys, stat
import logging
import atexit
import time
import xml.etree.ElementTree as ET
import distutils.util as dist
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
	resource_id = options["--resource"]
	wait_time = int(options["--standby-wait"])
	crm_node_path = options["--crm-node-path"]
	crm_mon_path = options["--crm-mon-path"]

	(rc, out, err) = run_command(options, "%s --name" % crm_node_path)
	if not rc == 0 or out is None:
		logging.error("Can not get my nodename. rc=%s, stderr=%s" % (rc, err))
		return False

	node = out.strip()

	if node == target:
		logging.info("Skip standby wait due to self-fencing.")
		return False

	(rc, out, err) = run_command(options, "%s --as-xml" % crm_mon_path)
	if not rc == 0 or out is None:
		logging.error("crm_mon command failed. rc=%s, stderr=%s" % (rc, err))
		return False

	tree = ET.fromstring(out)
	resources = tree.findall('./resources//*[@id="%s"]' % resource_id)
	if len(resources) == 0:
		logging.error("Resource '%s' not found." % resource_id)
	elif len(resources) == 1:
		resource = resources[0]
		type = resource.tag
		if type == "resource":
			# primitive resource
			standby_node = check_standby_node(resource, node)
			failed = check_failed_attrib(resource)
			if standby_node and not failed:
				return standby_wait(wait_time)
		elif type == "group":
			# resource group
			standby_node = True
			failed = False
			for child in resource:
				failed |= check_failed_attrib(child)
				standby_node &= check_standby_node(child, node)
			if standby_node and not failed:
				return standby_wait(wait_time)
		elif type == "clone" and dist.strtobool(resource.get("multi_state")):
			# promotable resource
			master_nodes = 0
			standby_node = True
			failed = False
			for native in resource:
				failed |= check_failed_attrib(native)
				if native.get("role") in ["Master"]:
					master_nodes += 1
					standby_node &= check_standby_node(native, node)
			if master_nodes == 1 and standby_node and not failed:
				return standby_wait(wait_time)
		else:
			# clone or bundle resource
			logging.error("Unsupported resource type: '%s'" % type)
	else:
		logging.error("Multiple active resources found.")

	logging.info("Skip standby wait.")
	return False

def standby_wait(wait_time):
	logging.info("Standby wait %s sec" % wait_time)
	time.sleep(wait_time)
	return False

def check_failed_attrib(resource):
	failed = dist.strtobool(resource.get("failed"))
	ignored = dist.strtobool(resource.get("failure_ignored"))
	return failed and not ignored

def check_standby_node(resource, nodename):
	running_nodes = []
	for node in resource:
		running_nodes.append(node.get("name"))
	return len(set(running_nodes)) == 1 and not running_nodes[0] == nodename

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
		"help" : "-r, --resource=[resource-id]   ID of the resource that should be running on the ACT node. It does not make sense to specify a cloned or bundled resource unless it is promotable and has only a single master instance.",
		"shortdesc" : "Resource ID. It does not make sense to specify a cloned or bundled resource unless it is promotable and has only a single master instance.",
		"default" : "",
		"order" : 1
		}
	all_opt["standby_wait"] = {
		"getopt" : "w:",
		"longopt" : "standby-wait",
		"required" : "0",
		"help" : "-w, --standby-wait=[seconds]   Wait X seconds on SBY node. The agent will delay but not succeed.",
		"shortdesc" : "Wait X seconds on SBY node. The agent will delay but not succeed.",
		"default" : "5",
		"order" : 1
		}
	all_opt["crm_mon_path"] = {
		"getopt" : ":",
		"longopt" : "crm-mon-path",
		"required" : "0",
		"help" : "--crm-mon-path=[path]          Path to crm_mon",
		"shortdesc" : "Path to crm_mon command",
		"default" : "@CRM_MON_PATH@",
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
	device_opt = ["no_status", "no_password", "nodename", "resource", "standby_wait", "crm_mon_path", "crm_node_path", "method"]
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
