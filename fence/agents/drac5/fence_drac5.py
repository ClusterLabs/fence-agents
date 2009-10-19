#!/usr/bin/python

#####
##
## The Following Agent Has Been Tested On:
##
##  DRAC Version       Firmware
## +-----------------+---------------------------+
##  DRAC 5             1.0  (Build 06.05.12)
##  DRAC 5             1.21 (Build 07.05.04)
##
## @note: drac_version was removed
#####

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Drac5 Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		if options["model"] == "DRAC CMC":
			conn.sendline("racadm serveraction powerstatus -m " + options["-m"])
		elif options["model"] == "DRAC 5":
			conn.sendline("racadm serveraction powerstatus")
		
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)
				
	status = re.compile("(^|: )(ON|OFF|Powering ON|Powering OFF)\s*$", re.IGNORECASE | re.MULTILINE).search(conn.before).group(2)
	if status.lower().strip() in ["on", "powering on", "powering off"]:
		return "on"
	else:
		return "off"

def set_power_status(conn, options):
	action = {
		'on' : "powerup",
		'off': "powerdown"
	}[options["-o"]]

	try:
		if options["model"] == "DRAC CMC":
			conn.sendline("racadm serveraction " + action + " -m " + options["-m"])
		elif options["model"] == "DRAC 5":
			conn.sendline("racadm serveraction " + action)
		conn.log_expect(options, options["-c"], int(options["-g"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def get_list_devices(conn, options):
	outlets = { }

	try:
		if options["model"] == "DRAC CMC":
			conn.sendline("getmodinfo")

			list_re = re.compile("^([^\s]*?)\s+Present\s*(ON|OFF)\s*.*$")
			for line in conn.before.splitlines():
				if (list_re.search(line)):
					outlets[list_re.search(line).group(1)] = ("", list_re.search(line).group(2))
			conn.log_expect(options, options["-c"], int(options["-g"]))
		elif options["model"] == "DRAC 5":
			## DRAC 5 can be used only for one computer
			pass
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

	return outlets
	
def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"cmd_prompt", "secure", "drac_version", "module_name",
			"separator", "inet4_only", "inet6_only", "ipport",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	options = check_input(device_opt, process_input(device_opt))

	## 
	## Fence agent specific defaults
	#####
	if 0 == options.has_key("-c"):
		options["-c"] = "\$"

	show_docs(options)

	##
	## Operate the fencing device
	######
	conn = fence_login(options)

	if conn.before.find("CMC") >= 0:
		if 0 == options.has_key("-m") and 0 == ["monitor", "list"].count(option["-o"].lower()):
			fail_usage("Failed: You have to enter module name (-m)")
			
		options["model"]="DRAC CMC"		
	elif conn.before.find("DRAC 5") >= 0:
		options["model"]="DRAC 5"
	else:
		## Assume this is DRAC 5 by default as we don't want to break anything
		options["model"]="DRAC 5"

	result = fence_action(conn, options, set_power_status, get_power_status, get_list_devices)

	##
	## Logout from system
	######
	try:
		conn.sendline("exit")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass
	
	sys.exit(result)

if __name__ == "__main__":
	main()
