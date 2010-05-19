#!/usr/bin/python

#####
##
## The Following Agent Has Been Tested On:
##
##  Version            Firmware
## +-----------------+---------------------------+
##  WTI RSM-8R4         ?? unable to find out ??
##  WTI MPC-??? 	?? unable to find out ??
##  WTI IPS-800-CE     v1.40h		(no username) ('list' tested)
#####

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New WTI Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

def get_power_status(conn, options):
	try:
		conn.send("/S"+"\r\n")
		conn.log_expect(options, options["-c"], int(options["-Y"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)
	
	plug_section = 0
	outlets = {}
	for line in conn.before.splitlines():
		if (plug_section == 2) and line.find("|") >= 0:
			plug_line = [x.strip().lower() for x in line.split("|")]
			if len(plug_line) < len(plug_header):
				plug_section = -1
				pass
			if ["list", "monitor"].count(options["-o"]) == 0 and options["-n"].lower() == plug_line[plug_index]:
				return plug_line[status_index]
			else:
				## We already believe that first column contains plug number
				outlets[plug_line[0]] = (plug_line[name_index], plug_line[status_index])
		elif (plug_section == 1):
			plug_section = 2
			pass
		elif (line.upper().startswith("PLUG")):
			plug_section = 1
			plug_header = [x.strip().lower() for x in line.split("|")]
			plug_index = plug_header.index("plug")
			name_index = plug_header.index("name")
			status_index = plug_header.index("status")

	if ["list", "monitor"].count(options["-o"]) == 1:
		return outlets
	else:
		return "PROBLEM"

def set_power_status(conn, options):
	action = {
		'on' : "/on",
		'off': "/off"
	}[options["-o"]]

	try:
		conn.send(action + " " + options["-n"] + ",y\r\n")
		conn.log_expect(options, options["-c"], int(options["-g"]))
	except pexpect.EOF:
		fail(EC_CONNECTION_LOST)
	except pexpect.TIMEOUT:
		fail(EC_TIMED_OUT)

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"cmd_prompt", "secure", "identity_file", "port", "no_login", "no_password",
			"test", "separator", "inet4_only", "inet6_only",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	options = check_input(device_opt, process_input(device_opt))

	## 
	## Fence agent specific defaults
	#####
	if 0 == options.has_key("-c"):
		options["-c"] = [ "RSM>", "MPC>", "IPS>", "TPS>", "NBB>", "NPS>", "VMR>" ]

	docs = { }
	docs["shortdesc"] = "Fence agent for WTI"
	docs["longdesc"] = "fence_wti is an I/O Fencing agent \
which can be used with the WTI Network Power Switch (NPS). It logs \
into an NPS via telnet or ssh and boots a specified plug. \
Lengthy telnet connections to the NPS should be avoided while a GFS cluster \
is running because the connection will block any necessary fencing actions."
	docs["vendorurl"] = "http://www.wti.com"
	show_docs(options, docs)
	
	##
	## Operate the fencing device
	##
	## @note: if it possible that this device does not need either login, password or both of them
	#####	
	if 0 == options.has_key("-x"):
		try:
			try:
				conn = fspawn('%s %s' % (TELNET_PATH, options["-a"]))
			except pexpect.ExceptionPexpect, ex:
				sys.stderr.write(str(ex) + "\n")
				sys.stderr.write("Due to limitations, binary dependencies on fence agents "
				"are not in the spec file and must be installed separately." + "\n")
				sys.exit(EC_GENERIC_ERROR)
			
			re_login = re.compile("(login: )|(Login Name:  )|(username: )|(User Name :)", re.IGNORECASE)
			re_prompt = re.compile("|".join(map (lambda x: "(" + x + ")", options["-c"])), re.IGNORECASE)

			result = conn.log_expect(options, [ re_login, "Password: ", re_prompt ], int(options["-Y"]))
			if result == 0:
				if options.has_key("-l"):
					conn.send(options["-l"]+"\r\n")
					result = conn.log_expect(options, [ re_login, "Password: ", re_prompt ], int(options["-Y"]))
				else:
					fail_usage("Failed: You have to set login name")
		
			if result == 1:
				if options.has_key("-p"):
					conn.send(options["-p"]+"\r\n")
					conn.log_expect(options, options["-c"], int(options["-Y"]))	
				else:
					fail_usage("Failed: You have to enter password or password script")
		except pexpect.EOF:
			fail(EC_LOGIN_DENIED) 
		except pexpect.TIMEOUT:
			fail(EC_LOGIN_DENIED)		
	else:
		conn = fence_login(options)

	result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)

	##
	## Logout from system
	######
	try:
		conn.send("/X"+"\r\n")
		conn.close()
	except exceptions.OSError:
		pass
	except pexpect.ExceptionPexpect:
		pass
		
	sys.exit(result)

if __name__ == "__main__":
	main()
