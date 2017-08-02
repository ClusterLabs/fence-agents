#!@PYTHON@ -tt

import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS

def get_power_status(conn, options):
	conn.send_eol("show node list")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

	nodes = {}
	for line in conn.before.splitlines():
		if len(line.split()) == 10:
			nodes[line.split()[1]] = ("", line.split()[8].lower().strip())

	if ["list", "monitor"].count(options["--action"]) == 1:
		return nodes
	else:
		try:
			(_, status) = nodes[options["--plug"]]
			return status.lower()
		except KeyError:
			fail(EC_STATUS)

def set_power_status(conn, options):
	if options["--action"] == "on":
		conn.send_eol("set node power on %s" % (options["--plug"]))
	else:
		conn.send_eol("set node power off force %s" % (options["--plug"]))

	conn.log_expect(options["--command-prompt"], int(options["--power-timeout"]))

	return

def main():
	device_opt = ["ipaddr", "login", "passwd", "secure", "cmd_prompt", "port"]

	atexit.register(atexit_handler)

	all_opt["secure"]["default"] = "1"
	all_opt["cmd_prompt"]["default"] = ["MP>", "hpiLO->"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for HP Moonshot iLO"
	docs["longdesc"] = ""
	docs["vendorurl"] = "http://www.hp.com"
	show_docs(options, docs)

	conn = fence_login(options)

	##
	## Fence operations
	####
	result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
