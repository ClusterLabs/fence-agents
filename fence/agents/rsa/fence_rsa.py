#!/usr/bin/python

#####
##
## The Following Agent Has Been Tested On:
##  Main GFEP25A & Boot GFBP25A
##
#####

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New RSA2 Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		conn.send("power state\r\n")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)
				
	match = re.compile("Power: (.*)", re.IGNORECASE).search(conn.before)
	if (match != None):
		status = match.group(1)
	else:
		status = "undefined"

	return status.lower().strip()

def set_power_status(conn, options):
	try:
		conn.send("power " + options["-o"] + "\r\n")
		conn.log_expect(options, options["-c"], int(options["-g"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"cmd_prompt", "secure", "identity_file", "ipport",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	all_opt["login_timeout"]["default"] = 10
	options = check_input(device_opt, process_input(device_opt))

	## 
	## Fence agent specific defaults
	#####
	if 0 == options.has_key("-c"):
		options["-c"] = ">"
		
	# This device will not allow us to login even with LANG=C
	options["ssh_options"] = "-F /dev/null"

	docs = { }
	docs["shortdesc"] = "Fence agent for IBM RSA"
	docs["longdesc"] = "fence_rsa is an I/O Fencing agent \
which can be used with the IBM RSA II management interface. It \
logs into an RSA II device via telnet and reboots the associated \
machine. Lengthy telnet connections to the RSA II device should \
be avoided while a GFS cluster is running because the connection \
will block any necessary fencing actions."
	docs["vendorurl"] = "http://www.ibm.com"
	show_docs(options, docs)
	
	##
	## Operate the fencing device
	######
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, None)

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
