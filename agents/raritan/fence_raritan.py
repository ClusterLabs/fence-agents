#!@PYTHON@ -tt

import sys, re, pexpect
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fspawn, fail, EC_LOGIN_DENIED, run_delay

# --plug should include path to the outlet # such as port 1:
# /system1/outlet1

def get_power_status(conn, options):
	conn.send_eol("show -d properties=powerState %s" % options["--plug"])
	re_status = re.compile(".*powerState is [12].*")
	conn.log_expect(re_status, int(options["--shell-timeout"]))
	status = {
		#"0" : "off",
		"1" : "on",
		"2" : "off",
	}[conn.after.split()[2]]

	return status

def set_power_status(conn, options):
	action = {
		"on" : "on",
		"off" : "off",
	}[options["--action"]]

	conn.send_eol("set %s powerState=%s" % (options["--plug"], action))

def main():
	device_opt = ["ipaddr", "login", "passwd", "port", "telnet"]

	atexit.register(atexit_handler)

	opt = process_input(device_opt)

	all_opt["ipport"]["default"] = "23"

	opt["eol"] = "\r\n"
	options = check_input(device_opt, opt)

	docs = {}
	docs["shortdesc"] = "I/O Fencing agent for Raritan Dominion PX"
	docs["longdesc"] = "fence_raritan is an I/O Fencing agent which can be \
used with the Raritan DPXS12-20 Power Distribution Unit. It logs into \
device via telnet and reboots a specified outlet. Lengthy telnet connections \
should be avoided while a GFS cluster is running because the connection will \
block any necessary fencing actions."
	docs["vendorurl"] = "http://www.raritan.com/"
	show_docs(options, docs)

	#  add support also for delay before login which is very useful for 2-node clusters
	run_delay(options)

	##
	## Operate the fencing device
	## We can not use fence_login(), username and passwd are sent on one line
	####
	try:
		conn = fspawn(options, options["--telnet-path"])
		conn.send("set binary\n")
		conn.send("open %s -%s\n"%(options["--ip"], options["--ipport"]))
		conn.read_nonblocking(size=100, timeout=int(options["--shell-timeout"]))
		conn.log_expect("Login.*", int(options["--shell-timeout"]))
		conn.send_eol("%s" % (options["--username"]))
		conn.log_expect("Password.*", int(options["--shell-timeout"]))
		conn.send_eol("%s" % (options["--password"]))
		conn.log_expect("clp.*", int(options["--shell-timeout"]))
	except pexpect.EOF:
		fail(EC_LOGIN_DENIED)
	except pexpect.TIMEOUT:
		fail(EC_LOGIN_DENIED)

	result = 0
	if options["--action"] != "monitor":
		result = fence_action(conn, options, set_power_status, get_power_status)

	fence_logout(conn, "exit\n")
	sys.exit(result)

if __name__ == "__main__":
	main()
