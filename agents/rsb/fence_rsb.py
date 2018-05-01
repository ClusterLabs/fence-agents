#!@PYTHON@ -tt

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

def get_power_status(conn, options):
	conn.send("2")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	status = re.compile(r"Power Status[\s]*: (on|off)", re.IGNORECASE).search(conn.before).group(1)
	conn.send("0")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	return status.lower().strip()

def set_power_status(conn, options):
	action = {
		'on' : "4",
		'off': "1"
	}[options["--action"]]

	conn.send("2")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.send_eol(action)
	conn.log_expect(["want to power " + options["--action"],
			"yes/no", "'yes' or 'no'"], int(options["--shell-timeout"]))
	conn.send_eol("yes")
	conn.log_expect("any key to continue", int(options["--power-timeout"]))
	conn.send_eol("")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	conn.send_eol("0")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "secure", "cmd_prompt", "telnet"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["to quit:"]

	opt = process_input(device_opt)

	if "--ssh" not in opt and "--ipport" not in opt:
		# set default value like it should be set as usually
		all_opt["ipport"]["default"] = "3172"
		opt["--ipport"] = all_opt["ipport"]["default"]

	options = check_input(device_opt, opt)

	docs = {}
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
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, None)
	fence_logout(conn, "0")
	sys.exit(result)

if __name__ == "__main__":
	main()
