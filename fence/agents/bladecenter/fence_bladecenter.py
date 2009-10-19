#!/usr/bin/python

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

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Bladecenter Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		node_cmd = "system:blade\[" + options["-n"] + "\]>"

		conn.send("env -T system:blade[" + options["-n"] + "]\r\n")
		i = conn.log_expect(options, [ node_cmd, "system>" ] , int(options["-Y"]))
		if i == 1:
			## Given blade number does not exist
			if options.has_key("-M"):
				return "off"
			else:
				fail(EC_STATUS)
		conn.send("power -state\r\n")
		conn.log_expect(options, node_cmd, int(options["-Y"]))
		status = conn.before.splitlines()[-1]
		conn.send("env -T system\r\n")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

	return status.lower().strip()

def set_power_status(conn, options):
	action = {
		'on' : "powerup",
		'off': "powerdown"
	}[options["-o"]]

	try:
		node_cmd = "system:blade\[" + options["-n"] + "\]>"

		conn.send("env -T system:blade[" + options["-n"] + "]\r\n")
		conn.log_expect(options, node_cmd, int(options["-Y"]))
		conn.send("power -"+options["-o"]+"\r\n")
		conn.log_expect(options, node_cmd, int(options["-Y"]))
		conn.send("env -T system\r\n")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def get_blades_list(conn, options):
	outlets = { }
	try:
		node_cmd = "system>"

		conn.send("env -T system\r\n")
		conn.log_expect(options, node_cmd, int(options["-Y"]))
		conn.send("list -l 2\r\n")
		conn.log_expect(options, node_cmd, int(options["-Y"]))

		lines = conn.before.split("\r\n")
		filter_re = re.compile("^\s*blade\[(\d+)\]\s+(.*?)\s*$")
		for x in lines:
			res = filter_re.search(x)
			if res != None:
				outlets[res.group(1)] = (res.group(2), "")

	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

	return outlets

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"cmd_prompt", "secure", "port", "identity_file", "separator",
			"inet4_only", "inet6_only", "ipport",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait", "missing_as_off" ]

	atexit.register(atexit_handler)

	all_opt["power_wait"]["default"] = "10"
	all_opt["cmd_prompt"]["default"] = "system>"

	options = check_input(device_opt, process_input(device_opt))

	docs = { }        
	docs["shortdesc"] = "Fence agent for IBM BladeCenter"
	docs["longdesc"] = "fence_bladecenter is an I/O Fencing agent \
which can be used with IBM Bladecenters with recent enough firmware that \
includes telnet support. It logs into a Brocade chasis via telnet or ssh \
and uses the command line interface to power on and off blades."
	show_docs(options, docs)
	
	##
	## Operate the fencing device
	######
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_blades_list)

	##
	## Logout from system
	######
	try:
		conn.send("exit\r\n")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass
	
	sys.exit(result)

if __name__ == "__main__":
	main()
