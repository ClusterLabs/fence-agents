#!/usr/bin/python -tt

##
## The Following Agent Has Been Tested On - LDOM 1.0.3
## The interface is backward compatible so it will work
## with 1.0, 1.0.1 and .2 too.
##
#####

import sys, re, pexpect, exceptions
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="Logical Domains (LDoms) fence Agent"
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

COMMAND_PROMPT_REG = r"\[PEXPECT\]$"
COMMAND_PROMPT_NEW = "[PEXPECT]"

# Start comunicating after login. Prepare good environment.
def start_communication(conn, options):
	conn.send_eol("PS1='" + COMMAND_PROMPT_NEW + "'")
	res = conn.expect([pexpect.TIMEOUT, COMMAND_PROMPT_REG], int(options["--shell-timeout"]))
	if res == 0:
		#CSH stuff
		conn.send_eol("set prompt='" + COMMAND_PROMPT_NEW + "'")
		conn.log_expect(COMMAND_PROMPT_REG, int(options["--shell-timeout"]))

def get_power_status(conn, options):
	start_communication(conn, options)

	conn.send_eol("ldm ls")

	conn.log_expect(COMMAND_PROMPT_REG, int(options["--shell-timeout"]))

	result = {}

	#This is status of mini finite automata. 0 = we didn't found NAME and STATE, 1 = we did
	fa_status = 0

	for line in conn.before.splitlines():
		domain = re.search(r"^(\S+)\s+(\S+)\s+.*$", line)

		if domain != None:
			if fa_status == 0 and domain.group(1) == "NAME" and domain.group(2) == "STATE":
				fa_status = 1
			elif fa_status == 1:
				result[domain.group(1)] = ("", (domain.group(2).lower() == "bound" and "off" or "on"))

	if not options["--action"] in ['monitor', 'list']:
		if not options["--plug"] in result:
			fail_usage("Failed: You have to enter existing logical domain!")
		else:
			return result[options["--plug"]][1]
	else:
		return result

def set_power_status(conn, options):
	start_communication(conn, options)

	cmd_line = "ldm "+ (options["--action"] == "on" and "start" or "stop -f") + " \"" + options["--plug"] + "\""

	conn.send_eol(cmd_line)

	conn.log_expect(COMMAND_PROMPT_REG, int(options["--power-timeout"]))

def main():
	device_opt = ["ipaddr", "login", "passwd", "cmd_prompt", "secure", "port"]

	atexit.register(atexit_handler)

	all_opt["secure"]["default"] = "1"
	all_opt["cmd_prompt"]["default"] = [r"\ $"]

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Sun LDOM"
	docs["longdesc"] = "fence_ldom is an I/O Fencing agent \
which can be used with LDoms virtual machines. This agent works \
so, that run ldm command on host machine. So ldm must be directly \
runnable.\
\n.P\n\
Very useful parameter is -c (or cmd_prompt in stdin mode). This \
must be set to something, what is displayed after successful login \
to host machine. Default string is space on end of string (default \
for root in bash). But (for example) csh use ], so in that case you \
must use parameter -c with argument ]. Very similar situation is, \
if you use bash and login to host machine with other user than \
root. Than prompt is $, so again, you must use parameter -c."
	docs["vendorurl"] = "http://www.sun.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	####
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)
	fence_logout(conn, "logout")
	sys.exit(result)

if __name__ == "__main__":
	main()
