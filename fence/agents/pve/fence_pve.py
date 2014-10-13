#!/usr/bin/python -tt

# This agent uses Proxmox VE API
# Thanks to Frank Brendel (author of original perl fence_pve)
# for help with writing and testing this agent.

import sys
import json
import pycurl
import StringIO
import urllib
import atexit
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail, EC_LOGIN_DENIED, atexit_handler, all_opt, check_input, process_input, show_docs, fence_action, run_delay

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
BUILD_DATE=""
REDHAT_COPYRIGHT=""
#END_VERSION_GENERATION


def get_power_status(conn, options):
	del conn
	state = {"running" : "on", "stopped" : "off"}
	if options["--nodename"] is None:
		nodes = send_cmd(options, "nodes")
		if type(nodes) is not dict or "data" not in nodes or type(nodes["data"]) is not list:
			return None
		for node in nodes["data"]: # lookup the node holding the vm
			if type(node) is not dict or "node" not in node:
				return None
			options["--nodename"] = node["node"]
			status = get_power_status(None, options)
			if status is not None:
				logging.info("vm found on node: " + options["--nodename"])
				break
			else:
				options["--nodename"] = None
		return status
	else:
		cmd = "nodes/" + options["--nodename"] + "/qemu/" + options["--plug"] + "/status/current"
		result = send_cmd(options, cmd)
		if type(result) is dict and "data" in result:
			if type(result["data"]) is dict and "status" in result["data"]:
				if result["data"]["status"] in state:
					return state[result["data"]["status"]]
		return None


def set_power_status(conn, options):
	del conn
	action = {
		'on' : "start",
		'off': "stop"
	}[options["--action"]]
	cmd = "nodes/" + options["--nodename"] + "/qemu/" + options["--plug"] + "/status/" + action
	send_cmd(options, cmd, post={"skiplock":1})


def get_outlet_list(conn, options):
	del conn
	nodes = send_cmd(options, "nodes")
	outlets = dict()
	if type(nodes) is not dict or "data" not in nodes or type(nodes["data"]) is not list:
		return None
	for node in nodes["data"]:
		if type(node) is not dict or "node" not in node:
			return None
		vms = send_cmd(options, "nodes/" + node["node"] + "/qemu")
		if type(vms) is not dict or "data" not in vms or type(vms["data"]) is not list:
			return None
		for vm in vms["data"]:
			outlets[vm["vmid"]] = [vm["name"], vm["status"]]
	return outlets


def get_ticket(options):
	post = {'username': options["--username"], 'password': options["--password"]}
	result = send_cmd(options, "access/ticket", post=post)
	if type(result) is dict and "data" in result:
		if type(result["data"]) is dict and "ticket" in result["data"] and "CSRFPreventionToken" in result["data"]:
			return {
				"ticket" : str("PVEAuthCookie=" + result["data"]["ticket"] + "; " + \
					"version=0; path=/; domain=" + options["--ip"] + \
					"; port=" + str(options["--ipport"]) + "; path_spec=0; secure=1; " + \
					"expires=7200; discard=0"),
				"CSRF_token" : str("CSRFPreventionToken: " + result["data"]["CSRFPreventionToken"])
				}
	return None


def send_cmd(options, cmd, post=None):
	url = options["url"] + cmd
	conn = pycurl.Curl()
	output_buffer = StringIO.StringIO()
	if logging.getLogger().getEffectiveLevel() < logging.WARNING:
		conn.setopt(pycurl.VERBOSE, True)
	conn.setopt(pycurl.HTTPGET, 1)
	conn.setopt(pycurl.URL, str(url))
	if "auth" in options and options["auth"] is not None:
		conn.setopt(pycurl.COOKIE, options["auth"]["ticket"])
		conn.setopt(pycurl.HTTPHEADER, [options["auth"]["CSRF_token"]])
	if post is not None:
		conn.setopt(pycurl.POSTFIELDS, urllib.urlencode(post))
	conn.setopt(pycurl.WRITEFUNCTION, output_buffer.write)
	conn.setopt(pycurl.TIMEOUT, int(options["--shell-timeout"]))
	if opt.has_key("--ssl") or opt.has_key("--ssl-secure"):
		conn.setopt(pycurl.SSL_VERIFYPEER, 1)
		conn.setopt(pycurl.SSL_VERIFYHOST, 2)

	if opt.has_key("--ssl-insecure"):
		conn.setopt(pycurl.SSL_VERIFYPEER, 0)
		conn.setopt(pycurl.SSL_VERIFYHOST, 0)

	logging.debug("URL: " + url)

	try:
		conn.perform()
		result = output_buffer.getvalue()

		logging.debug("RESULT [" + str(conn.getinfo(pycurl.RESPONSE_CODE)) + \
			"]: " + result)
		conn.close()

		return json.loads(result)
	except pycurl.error:
		logging.error("Connection failed")
	except:
		logging.error("Cannot parse json")
	return None


def main():
	atexit.register(atexit_handler)

	all_opt["node_name"] = {
		"getopt" : "N:",
		"longopt" : "nodename",
		"help" : "-N, --nodename                 "
			"Node on which machine is located",
		"required" : "0",
		"shortdesc" : "Node on which machine is located. "
			"(Optional, will be automatically determined)",
		"order": 2
	}

	device_opt = ["ipaddr", "login", "passwd", "web", "port", "node_name"]

	all_opt["login"]["required"] = "0"
	all_opt["login"]["default"] = "root@pam"
	all_opt["ipport"]["default"] = "8006"
	all_opt["port"]["shortdesc"] = "Id of the virtual machine."
	all_opt["ipaddr"]["shortdesc"] = "IP Address or Hostname of a node " +\
		"within the Proxmox cluster."

	options = check_input(device_opt, process_input(device_opt))
	docs = {}
	docs["shortdesc"] = "Fencing agent for the Proxmox Virtual Environment"
	docs["longdesc"] = "The fence_pve agent can be used to fence virtual \
machines acting as nodes in a virtualized cluster."
	docs["vendorurl"] = "http://www.proxmox.com/"

	show_docs(options, docs)

	run_delay(options)

	if "--nodename" not in options or not options["--nodename"]:
		options["--nodename"] = None

	options["url"] = "https://" + options["--ip"] + ":" + str(options["--ipport"]) + "/api2/json/"

	options["auth"] = get_ticket(options)
	if options["auth"] is None:
		fail(EC_LOGIN_DENIED)

	result = fence_action(None, options, set_power_status, get_power_status, get_outlet_list)

	sys.exit(result)

if __name__ == "__main__":
	main()
