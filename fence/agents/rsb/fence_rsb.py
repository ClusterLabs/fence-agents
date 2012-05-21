#!/usr/bin/python

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		conn.send("2")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
		status = re.compile("Power Status : (on|off)", re.IGNORECASE).search(conn.before).group(1)
		conn.send("0")
		conn.log_expect(options, options["-c"], int(options["-Y"]))

		return (status.lower().strip())
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def set_power_status(conn, options):
	action = {
		'on' : "4",
		'off': "1"
	}[options["-o"]]

	try:
		conn.send("2")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
		conn.send_eol(action)
		conn.log_expect(options, ["want to power off", "'yes' or 'no'"], int(options["-Y"]))
		conn.send_eol("yes")
		conn.log_expect(options, "any key to continue", int(options["-g"]))
		conn.send_eol("")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
		conn.send_eol("0")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"secure", "identity_file", "separator", "cmd_prompt",
			"inet4_only", "inet6_only", "ipport", "telnet_port",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)
	all_opt["telnet_port"] = {
		"getopt" : "n:",
                "longopt" : "telnet_port",
                "help" : "-n                             TCP port to use (deprecated, use -u)",
                "required" : "0",
                "shortdesc" : "TCP port to use for connection with device (default is 3172 for telnet)",
                "order" : 1
	}
	all_opt["cmd_prompt"]["default"] = "to quit:"

	opt = process_input(device_opt)
	# option -n for backward compatibility (-n is normally port no)
	if 1 == opt.has_key("-n"):
		opt["-u"] = opt["-n"]

	# set default port for telnet only
	if 0 == opt.has_key("-x") and 0 == opt.has_key("-u"):
		opt["-u"] = 3172
	options = check_input(device_opt, opt)

	docs = { }
	docs["shortdesc"] = "I/O Fencing agent for Fujitsu-Siemens RSB"
	docs["longdesc"] = "fence_rsb is an I/O Fencing agent \
which can be used with the Fujitsu-Siemens RSB management interface. It logs \
into device via telnet/ssh  and reboots a specified outlet. Lengthy telnet/ssh \
connections should be avoided while a GFS cluster is running because the connection \
will block any necessary fencing actions."
	docs["vendorurl"] = "http://www.fujitsu.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	####
	print options["-u"]

	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, None)

	##
	## Logout from system
	##
	## In some special unspecified cases it is possible that 
	## connection will be closed before we run close(). This is not 
	## a problem because everything is checked before.
	######
	try:
		conn.send_eol("0")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass
	
	sys.exit(result)

if __name__ == "__main__":
	main()
