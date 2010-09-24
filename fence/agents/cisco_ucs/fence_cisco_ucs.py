#!/usr/bin/python

import sys, re, pexpect, socket
import pycurl, StringIO
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New Cisco UCS Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION

re_cookie = re.compile("<aaaLogin .* outCookie=\"(.*?)\"", re.IGNORECASE);
re_status = re.compile("<lsPower .*? state=\"(.*?)\"", re.IGNORECASE);
re_get_dn = re.compile(" dn=\"(.*?)\"", re.IGNORECASE)
re_get_desc = re.compile(" descr=\"(.*?)\"", re.IGNORECASE)

def get_power_status(conn, options):
	try:
		res = send_command(options, "<configResolveDn cookie=\"" + options["cookie"] + "\" inHierarchical=\"false\" dn=\"org-root/ls-" + options["-n"] + "/power\"/>")
	except pycurl.error, e:
		sys.stderr.write(e[1] + "\n")
		fail(EC_TIMED_OUT)

	result = re_status.search(res)
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
	}[options["-o"]]
	
	try:
		res = send_command(options, "<configConfMos cookie=\"" + options["cookie"] + "\" inHierarchical=\"no\"><inConfigs><pair key=\"org-root/ls-" + options["-n"] + "/power\"><lsPower dn=\"org-root/ls-" + options["-n"] + "/power\" state=\"" + action + "\" status=\"modified\" /></pair></inConfigs></configConfMos>")
	except pycurl.error, e:
		sys.stderr.write(e[1] + "\n")
		fail(EC_TIMED_OUT)
	
	return

def get_list(conn, options):
	outlets = { }

	try:
		try:
			res = send_command(options, "<configResolveClass cookie=\"" + options["cookie"] + "\" inHierarchical=\"false\" classId=\"lsServer\"/>")
		except pycurl.error, e:
			sys.stderr.write(e[1] + "\n")
			fail(EC_TIMED_OUT)

		lines = res.split("<lsServer ")
		for i in range(1, len(lines)):
			dn = re_get_dn.search(lines[i]).group(1)
			desc = re_get_desc.search(lines[i]).group(1)
			outlets[dn] = (desc, None)
	except AttributeError:
		return { }
	except IndexError:
		return { }

	return outlets

def send_command(opt, command):
	## setup correct URL
	if opt.has_key("-z"):
		url = "https:"
	else:
		url = "http:"

	url += "//" + opt["-a"] + ":" + str(opt["-u"]) + "/nuova"

	## send command through pycurl
	c = pycurl.Curl()
	b = StringIO.StringIO()
	c.setopt(pycurl.URL, url)
	c.setopt(pycurl.HTTPHEADER, [ "Content-type: text/xml" ])
	c.setopt(pycurl.POSTFIELDS, command)
	c.setopt(pycurl.WRITEFUNCTION, b.write)
	c.setopt(pycurl.TIMEOUT, int(opt["-Y"]))
	c.setopt(pycurl.SSL_VERIFYPEER, 0)
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
	
	options = check_input(device_opt, process_input(device_opt))

	docs = { }
	docs["shortdesc"] = "Fence agent for Cisco UCS"
	docs["longdesc"] = "fence_cisco_ucs is an I/O Fencing agent which can be \
used with Cisco UCS to fence machines."
	docs["vendorurl"] = "http://www.cisco.com"
	show_docs(options, docs)

	### Login
	res = send_command(options, "<aaaLogin inName=\"" + options["-l"] + "\" inPassword=\"" + options["-p"] + "\" />")
	result = re_cookie.search(res)
	if (result == None):	
		## Cookie is absenting in response
		fail(EC_LOGIN_DENIED)

	options["cookie"] = result.group(1);

	##
	## Fence operations
	####
	result = fence_action(None, options, set_power_status, get_power_status, get_list)

	### Logout; we do not care about result as we will end in any case
	send_command(options, "<aaaLogout inCookie=\"" + options["cookie"] + "\" />")
	
	sys.exit(result)

if __name__ == "__main__":
	main()
