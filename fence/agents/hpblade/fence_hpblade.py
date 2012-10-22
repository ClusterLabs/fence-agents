#!/usr/bin/python

#####
##
## The Following Agent Has Been Tested On:
##  * BladeSystem c7000 Enclosure
#####

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Bladecenter Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		conn.send_eol("show server status " + options["-n"])
		conn.log_expect(options, options["-c"] , int(options["-Y"]))
		
		power_re = re.compile("^\s*Power: (.*?)\s*$")
		status = "unknown"
		for line in conn.before.splitlines():
		        res = power_re.search(line)
		        if res != None:
		                status = res.group(1)

                if status == "unknown":
			if options.has_key("-M"):
				return "off"
			else:
				fail(EC_STATUS)
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

	return status.lower().strip()

def set_power_status(conn, options):
	try:
	        if options["-o"] == "on":
	                conn.send_eol("poweron server " + options["-n"])
                elif options["-o"] == "off":
                        conn.send_eol("poweroff server " + options["-n"] + " force")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def get_blades_list(conn, options):
	outlets = { }
	try:
		conn.send_eol("show server list" )
		conn.log_expect(options, options["-c"], int(options["-Y"]))

		list_re = re.compile("^\s*(.*?)\s+(.*?)\s+(.*?)\s+OK\s+(.*?)\s+(.*?)\s*$")
		for line in conn.before.splitlines():
		        res = list_re.search(line)
		        if res != None:
		                outlets[res.group(1)] = (res.group(2), res.group(4).lower())
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

	return outlets

def main():
	device_opt = [  "ipaddr", "login", "passwd", "passwd_script",
			"cmd_prompt", "secure", "port", "identity_file", "separator",
			"inet4_only", "inet6_only", "ipport", "missing_as_off" ]

	atexit.register(atexit_handler)

	all_opt["cmd_prompt"]["default"] = "c7000oa>"

	options = check_input(device_opt, process_input(device_opt))

 	docs = { }        
	docs["shortdesc"] = "Fence agent for HP BladeSystem"
	docs["longdesc"] = "fence_hpblade is an I/O Fencing agent \
which can be used with HP BladeSystem. It logs into an enclosure via telnet or ssh \
and uses the command line interface to power on and off blades."
	docs["vendorurl"] = "http://www.hp.com"
	show_docs(options, docs)
	
	##
	## Operate the fencing device
	######
	options["eol"] = "\n"
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_blades_list)

	##
	## Logout from system
	######
	try:
		conn.send_eol("exit")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass
	
	sys.exit(result)

if __name__ == "__main__":
	main()
