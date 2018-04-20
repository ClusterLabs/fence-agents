#!@PYTHON@ -tt

#####
##
## The Following Agent Has Been Tested On:
##  Main GFEP25A & Boot GFBP25A
##
#####

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

def get_power_status(conn, options):
	conn.send_eol("power state")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	match = re.compile("Power: (.*)", re.IGNORECASE).search(conn.before)
	if match != None:
		status = match.group(1)
	else:
		status = "undefined"

	return status.lower().strip()

def set_power_status(conn, options):
	conn.send_eol("power " + options["--action"])
	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", "telnet"]

	atexit.register(atexit_handler)

	all_opt["login_timeout"]["default"] = 10
	all_opt["cmd_prompt"]["default"] = [">"]
	# This device will not allow us to login even with LANG=C
	all_opt["ssh_options"]["default"] = "-F /dev/null"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
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
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
