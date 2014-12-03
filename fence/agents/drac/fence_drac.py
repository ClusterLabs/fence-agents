#!/usr/bin/python -tt

import sys, re
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	conn.send_eol("getmodinfo")
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
	status = re.compile(r"\s+(on|off)\s+", re.IGNORECASE).search(conn.before).group(1)
	return status.lower().strip()

def set_power_status(conn, options):
	action = {
		'on' : "powerup",
		'off': "powerdown"
	}[options["--action"]]

	conn.send_eol("serveraction -d 0 " + action)
	conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "telnet"]

	atexit.register(atexit_handler)

	opt = process_input(device_opt)
	if "--username" in opt:
		all_opt["cmd_prompt"]["default"] = ["\\[" + opt["--username"] + "\\]# "]
	else:
		all_opt["cmd_prompt"]["default"] = ["\\[" "username" + "\\]# "]

	options = check_input(device_opt, opt)

	docs = {}
	docs["shortdesc"] = "I/O Fencing agent for Dell DRAC IV"
	docs["longdesc"] = "fence_drac is an I/O Fencing agent which can be used with \
the Dell Remote Access Card (DRAC). This card provides remote access to controlling \
power to a server. It logs into the DRAC through the telnet interface of the card. By \
default, the telnet interface is not enabled. To enable the interface, you will need \
to use the racadm command in the racser-devel rpm available from Dell.  \
\
To enable telnet on the DRAC: \
\
[root]# racadm config -g cfgSerial -o cfgSerialTelnetEnable 1 \
\
[root]# racadm racreset \
"
	docs["vendorurl"] = "http://www.dell.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	####
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, None)
	fence_logout(conn, "exit")
	sys.exit(result)

if __name__ == "__main__":
	main()
