#!@PYTHON@ -tt

#####
##
## Fence agent for CyberPower based SSH-capable power strip
## Tested with CyberPower model PDU41001, ePDU Firmware version 1.2.0
##
#####

import sys, re, time
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS

def set_power_status(conn, options):
	conn.send_eol("oltctrl index " + options["--plug"] + " act delay" + options["--action"])
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def get_power_status(conn, options):
	outlets = {}
	conn.send_eol("oltsta show")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	lines = conn.before.split("\n")
	show_re = re.compile(r'(\s*)(\d)\s*(.*)\s*(On|Off)\s*')
	for line in lines:
		res = show_re.search(line)
		if res != None:
			outlets[res.group(2)] = (res.group(3), res.group(4))
	if ["list", "monitor"].count(options["--action"]) == 1:
		return outlets
	else:
		try:
			(_,status) = outlets[options["--plug"]]
			return status.lower().strip()
		except KeyError:
			fail(EC_STATUS)

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", \
			"port"]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = ["\n>", "\nCyberPower >"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for CyberPower over ssh"
	docs["longdesc"] = "fence_cyberpower_ssh is a Power Fencing agent \
which can be used with the CyberPower network power switch. It logs into \
device via ssh and reboots a specified outlet. Lengthy ssh connections \
should be avoided while a GFS cluster is running because the connection \
will block any necessary fencing actions."
	docs["vendorurl"] = "http://www.cyberpower.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	####
	conn = fence_login(options)

	result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)

	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
