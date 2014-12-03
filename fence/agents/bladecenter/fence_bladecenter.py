#!/usr/bin/python -tt

#####
##
## The Following Agent Has Been Tested On:
##
##  Model                 Firmware
## +--------------------+---------------------------+
## (1) Main application	  BRET85K, rev 16
##     Boot ROM           BRBR67D, rev 16
##     Remote Control     BRRG67D, rev 16
##
#####

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS, EC_GENERIC_ERROR

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Bladecenter Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	node_cmd = r"system:blade\[" + options["--plug"] + r"\]>"

	conn.send_eol("env -T system:blade[" + options["--plug"] + "]")
	i = conn.log_expect([node_cmd, "system>"], int(options["--shell-timeout"]))
	if i == 1:
		## Given blade number does not exist
		if options.has_key("--missing-as-off"):
			return "off"
		else:
			fail(EC_STATUS)
	conn.send_eol("power -state")
	conn.log_expect(node_cmd, int(options["--shell-timeout"]))
	status = conn.before.splitlines()[-1]
	conn.send_eol("env -T system")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	return status.lower().strip()

def set_power_status(conn, options):
	node_cmd = r"system:blade\[" + options["--plug"] + r"\]>"

	conn.send_eol("env -T system:blade[" + options["--plug"] + "]")
	i = conn.log_expect([node_cmd, "system>"], int(options["--shell-timeout"]))
	if i == 1:
		## Given blade number does not exist
		if options.has_key("--missing-as-off"):
			return
		else:
			fail(EC_GENERIC_ERROR)

	conn.send_eol("power -"+options["--action"])
	conn.log_expect(node_cmd, int(options["--shell-timeout"]))
	conn.send_eol("env -T system")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def get_blades_list(conn, options):
	outlets = {}

	node_cmd = "system>"

	conn.send_eol("env -T system")
	conn.log_expect(node_cmd, int(options["--shell-timeout"]))
	conn.send_eol("list -l 2")
	conn.log_expect(node_cmd, int(options["--shell-timeout"]))

	lines = conn.before.split("\r\n")
	filter_re = re.compile(r"^\s*blade\[(\d+)\]\s+(.*?)\s*$")
	for blade_line in lines:
		res = filter_re.search(blade_line)
		if res != None:
			outlets[res.group(1)] = (res.group(2), "")

	return outlets

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
			"port", "missing_as_off", "telnet"]

	atexit.register(atexit_handler)

	all_opt["power_wait"]["default"] = "10"
	all_opt["cmd_prompt"]["default"] = ["system>"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for IBM BladeCenter"
	docs["longdesc"] = "fence_bladecenter is an I/O Fencing agent \
which can be used with IBM Bladecenters with recent enough firmware that \
includes telnet support. It logs into a Brocade chasis via telnet or ssh \
and uses the command line interface to power on and off blades."
	docs["vendorurl"] = "http://www.ibm.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	######
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_blades_list)
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
