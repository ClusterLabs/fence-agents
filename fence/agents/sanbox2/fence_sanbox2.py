#!/usr/bin/python

#####
##
## The Following Agent Has Been Tested On:
##
##  Version            Firmware
## +-----------------+---------------------------+
#####

import sys, re, pexpect
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Sanbox2 Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	status_trans = {
		'online' : "on",
		'offline' : "off"
	}
	try:
		conn.send("show port " + options["-n"] + "\n")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		try:
			conn.send("admin end\n")
			conn.send("exit\n")
			conn.close()
		except:
			pass
		fail(EC_TIMED_OUT)
	
	status = re.compile(".*AdminState\s+(online|offline)\s+", re.IGNORECASE | re.MULTILINE).search(conn.before).group(1)

	try:
		return status_trans[status.lower().strip()]
	except KeyError:
		return "PROBLEM"

def set_power_status(conn, options):
	action = {
		'on' : "online",
		'off' : "offline"
	}[options["-o"]]

        try:
        	conn.send("set port " + options["-n"] + " state " + action + "\n")
		conn.log_expect(options, options["-c"], int(options["-g"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		try:
			conn.send("admin end\n")
			conn.send("exit\n")
			conn.close()
		except:
			pass
		fail(EC_TIMED_OUT)                                                                         	

	try:
		conn.send("set port " + options["-n"] + " state " + action + "\n")
		conn.log_expect(options, options["-c"], int(options["-g"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		try:
			conn.send("admin end\n")
			conn.send("exit\n")
			conn.close()
		except:
			pass
		fail(EC_TIMED_OUT)

def get_list_devices(conn, options):
	outlets = { }

	try:
		conn.send("show port" + "\n")
		conn.log_expect(options, options["-c"], int(options["-Y"]))

		list_re = re.compile("^\s+(\d+?)\s+(Online|Offline)\s+", re.IGNORECASE)
		for line in conn.before.splitlines():
			if (list_re.search(line)):
				status = {
					'online' : "ON",
					'offline' : "OFF"
				}[list_re.search(line).group(2).lower()]
				outlets[list_re.search(line).group(1)] = ("", status)

	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		try:
			conn.send("admin end\n")
			conn.send("exit\n")
			conn.close()
		except:
			pass
		fail(EC_TIMED_OUT)
		
	return outlets

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"io_fencing", "ipaddr", "login", "passwd", "passwd_script",
			"cmd_prompt", "port", "ipport", "login_eol_lf", "separator",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	options = check_input(device_opt, process_input(device_opt))

	## 
	## Fence agent specific defaults
	#####
	if 0 == options.has_key("-c"):
		options["-c"] = [ " #> " ]

	docs = { }
	docs["shortdesc"] = "Fence agent for QLogic SANBox2 FC switches"
	docs["longdesc"] = "fence_sanbox2 is an I/O Fencing agent which can be used with \
QLogic SANBox2 FC switches.  It logs into a SANBox2 switch via telnet and disables a specified \
port. Disabling  the port which a machine is connected to effectively fences that machine. \
Lengthy telnet connections to the switch should be avoided while a GFS cluster is running \
because the connection will block any necessary fencing actions."
	docs["vendorurl"] = "http://www.qlogic.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	##
	conn = fence_login(options)

	conn.send("admin start\n")
	conn.log_expect(options, options["-c"], int(options["-Y"]))

	if (re.search("\(admin\)", conn.before, re.MULTILINE) == None):
		## Someone else is in admin section, we can't enable/disable
		## ports so we will rather exit
		sys.stderr.write("Failed: Unable to switch to admin section\n")
		sys.exit(EC_GENERIC_ERROR)

	result = fence_action(conn, options, set_power_status, get_power_status, get_list_devices)

	##
	## Logout from system
	######
	try:
		conn.send("admin end\n")
		conn.send("exit\n")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass

	sys.exit(result)

if __name__ == "__main__":
	main()
