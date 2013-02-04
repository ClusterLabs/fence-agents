#!/usr/bin/python

import sys, re
import pycurl, StringIO
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Cisco UCS Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

RE_COOKIE = re.compile("<aaaLogin .* outCookie=\"(.*?)\"", re.IGNORECASE)
RE_STATUS = re.compile("<lsPower .*? state=\"(.*?)\"", re.IGNORECASE)
RE_GET_DN = re.compile(" dn=\"(.*?)\"", re.IGNORECASE)
RE_GET_DESC = re.compile(" descr=\"(.*?)\"", re.IGNORECASE)

def get_power_status(conn, options):
	res = send_command(options, \
		"<configResolveDn cookie=\"" + options["cookie"] + "\" inHierarchical=\"false\" dn=\"org-root" + options["--suborg"] + \
		"/ls-" + options["--plug"] + "/power\"/>", \
		 int(options["--shell-timeout"]))

	result = RE_STATUS.search(res)
	if (result == None):
		fail(EC_STATUS)
	else:
		status = result.group(1)

	if (status == "up"):
		return "on"
	else:
		return "off"

def set_power_status(conn, options):
	action = {
		'on' : "up",
		'off' : "down"
	}[options["--action"]]
	
	res = send_command(options, \
		"<configConfMos cookie=\"" + options["cookie"] + "\" inHierarchical=\"no\">" + \
		"<inConfigs><pair key=\"org-root" + options["--suborg"] + "/ls-" + options["--plug"] + "/power\">" + \
		"<lsPower dn=\"org-root/ls-" + options["--plug"] + "/power\" state=\"" + action + "\" status=\"modified\" />" + \
		"</pair></inConfigs></configConfMos>", \
		int(options["--shell-timeout"]))
	
	return

def get_list(conn, options):
	outlets = { }

	try:
		res = send_command(options, \
			"<configResolveClass cookie=\"" + options["cookie"] + "\" inHierarchical=\"false\" classId=\"lsServer\"/>", \
			int(options["--shell-timeout"]))

		lines = res.split("<lsServer ")
		for i in range(1, len(lines)):
			dn = RE_GET_DN.search(lines[i]).group(1)
			desc = RE_GET_DESC.search(lines[i]).group(1)
			outlets[dn] = (desc, None)
	except AttributeError:
		return { }
	except IndexError:
		return { }

	return outlets

def send_command(opt, command, timeout):
	## setup correct URL
	if opt.has_key("--ssl"):
		url = "https:"
	else:
		url = "http:"

	url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + "/nuova"

	## send command through pycurl
	c = pycurl.Curl()
	b = StringIO.StringIO()
	c.setopt(pycurl.URL, url)
	c.setopt(pycurl.HTTPHEADER, [ "Content-type: text/xml" ])
	c.setopt(pycurl.POSTFIELDS, command)
	c.setopt(pycurl.WRITEFUNCTION, b.write)
	c.setopt(pycurl.TIMEOUT, timeout)
	c.setopt(pycurl.SSL_VERIFYPEER, 0)
	c.setopt(pycurl.SSL_VERIFYHOST, 0)
	c.perform()
	result = b.getvalue()

	if opt["log"] >= LOG_MODE_VERBOSE:
		opt["debug_fh"].write(command + "\n")
		opt["debug_fh"].write(result + "\n")

	return result

def define_new_opts():
	all_opt["suborg"] = {
		"getopt" : "s:",
		"longopt" : "suborg",
		"help" : "--suborg=[path]                Additional path needed to access suborganization",
		"required" : "0",
		"shortdesc" : "Additional path needed to access suborganization",
		"default" : "",
		"order" : 1 }

def main():
	device_opt = [ "ipaddr", "login", "passwd", "ssl", "port", "web", "suborg" ]

	atexit.register(atexit_handler)

	define_new_opts()
	
	options = check_input(device_opt, process_input(device_opt))

	docs = { }
	docs["shortdesc"] = "Fence agent for Cisco UCS"
	docs["longdesc"] = "fence_cisco_ucs is an I/O Fencing agent which can be \
used with Cisco UCS to fence machines."
	docs["vendorurl"] = "http://www.cisco.com"
	show_docs(options, docs)

	### Login
	res = send_command(options, "<aaaLogin inName=\"" + options["--username"] + "\" inPassword=\"" + options["--password"] + "\" />", int(options["--login-timeout"]))
	result = RE_COOKIE.search(res)
	if (result == None):	
		## Cookie is absenting in response
		fail(EC_LOGIN_DENIED)

	options["cookie"] = result.group(1)

	##
	## Modify suborg to format /suborg
	if options["--suborg"] != "":
		options["--suborg"] = "/" + options["--suborg"].lstrip("/").rstrip("/")

	##
	## Fence operations
	####
	result = fence_action(None, options, set_power_status, get_power_status, get_list)

	### Logout; we do not care about result as we will end in any case
	send_command(options, "<aaaLogout inCookie=\"" + options["cookie"] + "\" />", int(options["--shell-timeout"]))
	
	sys.exit(result)

if __name__ == "__main__":
	main()
