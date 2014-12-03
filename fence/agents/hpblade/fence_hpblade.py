#!/usr/bin/python -tt

#####
##
## The Following Agent Has Been Tested On:
##  * BladeSystem c7000 Enclosure
#####

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Bladecenter Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	conn.send_eol("show server status " + options["--plug"])
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	power_re = re.compile(r"^\s*Power: (.*?)\s*$")
	status = "unknown"
	for line in conn.before.splitlines():
		res = power_re.search(line)
		if res != None:
			status = res.group(1)

	if status == "unknown":
		if options.has_key("--missing-as-off"):
			return "off"
		else:
			fail(EC_STATUS)

	return status.lower().strip()

def set_power_status(conn, options):
	if options["--action"] == "on":
		conn.send_eol("poweron server " + options["--plug"])
	elif options["--action"] == "off":
		conn.send_eol("poweroff server " + options["--plug"] + " force")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def get_blades_list(conn, options):
	outlets = {}

	conn.send_eol("show server list")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	list_re = re.compile(r"^\s*(.*?)\s+(.*?)\s+(.*?)\s+OK\s+(.*?)\s+(.*?)\s*$")
	for line in conn.before.splitlines():
		res = list_re.search(line)
		if res != None:
			outlets[res.group(1)] = (res.group(2), res.group(4).lower())

	return outlets

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
		"port", "missing_as_off", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["c7000oa>"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for HP BladeSystem"
	docs["longdesc"] = "fence_hpblade is an I/O Fencing agent \
which can be used with HP BladeSystem. It logs into an enclosure via telnet or ssh \
and uses the command line interface to power on and off blades."
	docs["vendorurl"] = "http://www.hp.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	######
	options["eol"] = "\n"
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_blades_list)
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
