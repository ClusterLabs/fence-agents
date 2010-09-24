#!/usr/bin/python

import sys, re, pexpect, socket
import pycurl, StringIO
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New RHEV-M Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION


re_get_id = re.compile("<vm id=\"(.*?)\"", re.IGNORECASE);
re_status = re.compile("<status>(.*?)</status>", re.IGNORECASE);
re_get_name = re.compile("<name>(.*?)</name>", re.IGNORECASE); 

def get_power_status(conn, options):
	### Obtain real ID from name
	try:
		res = send_command(options, "vms/?search=name%3D" + options["-n"])
	except pycurl.error, e:
		sys.stderr.write(e[1] + "\n")
		fail(EC_TIMED_OUT)

	result = re_get_id.search(res)
	if (result == None):
		# Unable to obtain ID needed to access virtual machine
		fail(EC_STATUS)

	options["id"] = result.group(1);
	
	re_status.search(res)
	result = re_status.search(res)
	if (result == None):
		# We were able to parse ID so output is correct
		# in some cases it is possible that RHEV-M output does not
		# contain <status> line. We can assume machine is OFF then
		return "off"
	else:
		status = result.group(1)

	if (status == "RUNNING"):
		return "on"
	else:
		return "off"

def set_power_status(conn, options):
	action = {
		'on' : "start",
		'off' : "stop"
	}[options["-o"]]

	url = "vms/" + options["id"] + "/" + action
	try:
		res = send_command(options, url, "POST")
	except pycurl.error, e:
		sys.stderr.write(e[1] + "\n")
		fail(EC_TIMED_OUT)
	
	return

def get_list(conn, options):
	outlets = { }

	try:
		try:
			res = send_command(options, "vms")
		except pycurl.error, e:
			sys.stderr.write(e[1] + "\n")
			fail(EC_TIMED_OUT)	

		lines = res.split("<vm ")
		for i in range(1, len(lines)):
			name = re_get_name.search(lines[i]).group(1)
			outlets[name] = ("", None)
	except AttributeError:
		return { }
	except IndexError:
		return { }

	return outlets

def send_command(opt, command, method = "GET"):
	## setup correct URL
	if opt.has_key("-z"):
		url = "https:"
	else:
		url = "http:"

	url += "//" + opt["-a"] + ":" + str(opt["-u"]) + "/rhevm-api-powershell/" + command

	## send command through pycurl
	c = pycurl.Curl()
	b = StringIO.StringIO()
	c.setopt(pycurl.URL, url)
	c.setopt(pycurl.HTTPHEADER, [ "Content-type: application/xml", "Accept: application/xml" ])
	c.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
	c.setopt(pycurl.USERPWD, opt["-l"] + ":" + opt["-p"])
	c.setopt(pycurl.TIMEOUT, int(opt["-Y"]))
	c.setopt(pycurl.SSL_VERIFYPEER, 0)

	if (method == "POST"):
		c.setopt(pycurl.POSTFIELDS, "<action />")

	c.setopt(pycurl.WRITEFUNCTION, b.write)
	c.perform()
	result = b.getvalue()

	if opt["log"] >= LOG_MODE_VERBOSE:
		opt["debug_fh"].write(command + "\n")
		opt["debug_fh"].write(result + "\n")

	return result

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"ssl", "inet4_only", "inet6_only", "ipport", "port", 
			"web", "separator", "power_wait", "power_timeout", 
			"shell_timeout" ]

	atexit.register(atexit_handler)

	all_opt["power_wait"]["default"] = "1"
	
	options = check_input(device_opt, process_input(device_opt))

	docs = { }
	docs["shortdesc"] = "Fence agent for RHEV-M REST API"
	docs["longdesc"] = "fence_rhevm is an I/O Fencing agent which can be \
used with RHEV-M REST API to fence virtual machines."
	docs["vendorurl"] = "http://www.redhat.com"
	show_docs(options, docs)

	##
	## Fence operations
	####
	result = fence_action(None, options, set_power_status, get_power_status, get_list)

	sys.exit(result)

if __name__ == "__main__":
	main()
