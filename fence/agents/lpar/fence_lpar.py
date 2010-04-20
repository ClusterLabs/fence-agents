#!/usr/bin/python

#####
##
## The Following Agent Has Been Tested On:
##
##  Version       
## +---------------------------------------------+
##  Tested on HMC
##
#####

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def get_power_status(conn, options):
	if options["-H"] == "3":
		try:
			conn.send("lssyscfg -r lpar -m " + options["-s"] + " -n " + options["-n"] + " -F name,state\n")
			conn.log_expect(options, options["-c"], int(options["-g"]))
		except pexpect.EOF:
			fail(EC_CONNECTION_LOST)
		except pexpect.TIMEOUT:
			fail(EC_TIMED_OUT)

		try:
			status = re.compile("^" + options["-n"] + ",(.*?),.*$", re.IGNORECASE | re.MULTILINE).search(conn.before).group(1)
		except AttributeError:
			fail(EC_STATUS_HMC)
	elif options["-H"] == "4":
		try:
			conn.send("lssyscfg -r lpar -m "+ options["-s"] +" --filter 'lpar_names=" + options["-n"] + "'\n")
			conn.log_expect(options, options["-c"], int(options["-g"]))
		except pexpect.EOF:
			fail(EC_CONNECTION_LOST)
		except pexpect.TIMEOUT:
			fail(EC_TIMED_OUT)

		try:				
			status = re.compile(",state=(.*?),", re.IGNORECASE).search(conn.before).group(1)
		except AttributeError:
			fail(EC_STATUS_HMC)

	##
	## Transformation to standard ON/OFF status if possible
	if status in ["Running", "Open Firmware", "Shutting Down", "Starting"]:
		status = "on"
	else:
		status = "off"

	return status

def set_power_status(conn, options):
	if options["-H"] == "3":
		try:
			conn.send("chsysstate -o " + options["-o"] + " -r lpar -m " + options["-s"]
				+ " -n " + options["-n"] + "\n")
			conn.log_expect(options, options["-c"], int(options["-g"]))
		except pexpect.EOF:
			fail(EC_CONNECTION_LOST)
		except pexpect.TIMEOUT:
			fail(EC_TIMED_OUT)		
	elif options["-H"] == "4":
		try:
			if options["-o"] == "on":
				conn.send("chsysstate -o on -r lpar -m " + options["-s"] + 
					" -n " + options["-n"] + 
					" -f `lssyscfg -r lpar -F curr_profile " +
					" -m " + options["-s"] +
					" --filter \"lpar_names="+ options["-n"] +"\"`\n" )
			else:
				conn.send("chsysstate -o shutdown -r lpar --immed" +
					" -m " + options["-s"] + " -n " + options["-n"] + "\n")		
			conn.log_expect(options, options["-c"], int(options["-g"]))
		except pexpect.EOF:
			fail(EC_CONNECTION_LOST)
		except pexpect.TIMEOUT:
			fail(EC_TIMED_OUT)

def get_lpar_list(conn, options):
	outlets = { }
	if options["-H"] == "3":
		try:
			conn.send("query_partition_names -m " + options["-s"] + "\n")
			conn.log_expect(options, options["-c"], int(options["-g"]))

			## We have to remove first 3 lines (command + header) and last line (part of new prompt)
			####
			res = re.search("^.+?\n(.+?\n){2}(.*)\n.*$", conn.before, re.S)

			if res == None:
				fail_usage("Unable to parse output of list command")
		
			lines = res.group(2).split("\n")
			for x in lines:
				outlets[x.rstrip()] = ("", "")
		except pexpect.EOF:
			fail(EC_CONNECTION_LOST)
		except pexpect.TIMEOUT:
			fail(EC_TIMED_OUT)		
	elif options["-H"] == "4":
		try:
			conn.send("lssyscfg -r lpar -m " + options["-s"] + 
				" -F name:state\n")
			conn.log_expect(options, options["-c"], int(options["-g"]))

			## We have to remove first line (command) and last line (part of new prompt)
			####
			res = re.search("^.+?\n(.*)\n.*$", conn.before, re.S)

			if res == None:
				fail_usage("Unable to parse output of list command")
		
			lines = res.group(1).split("\n")
			for x in lines:
				s = x.split(":")
				outlets[s[0]] = ("", s[1])
		except pexpect.EOF:
			fail(EC_CONNECTION_LOST)
		except pexpect.TIMEOUT:
			fail(EC_TIMED_OUT)

	return outlets

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"secure", "identity_file", "partition", "managed", "hmc_version", "cmd_prompt",
			"separator", "inet4_only", "inet6_only", "ipport",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	all_opt["login_timeout"]["default"] = "15"
	all_opt["secure"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	## 
	## Fence agent specific settings and default values
	#####
	if 0 == options.has_key("-c"):
		options["-c"] = [ ":~>", "]\$", "\$ " ]

	docs = { }
	docs["shortdesc"] = "Fence agent for IBM LPAR"
	docs["longdesc"] = ""
	show_docs(options, docs)

	if 0 == options.has_key("-s"):
		fail_usage("Failed: You have to enter name of managed system")

        if (0 == ["list", "monitor"].count(options["-o"].lower())) and (0 == options.has_key("-n")):
                fail_usage("Failed: You have to enter name of the partition")

	if 1 == options.has_key("-H") and (options["-H"] != "3" and options["-H"] != "4"):
		fail_usage("Failed: You have to enter valid version number: 3 or 4")

	##
	## Operate the fencing device
	####
	conn = fence_login(options)
	result = fence_action(conn, options, set_power_status, get_power_status, get_lpar_list)

	##
	## Logout from system
	######
	try:
		conn.send("quit\r\n")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass	                                         

	sys.exit(result)
if __name__ == "__main__":
	main()
