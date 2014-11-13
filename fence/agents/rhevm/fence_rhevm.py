#!/usr/bin/python -tt

import sys, re
import pycurl, StringIO
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS, run_delay

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New RHEV-M Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION


RE_GET_ID = re.compile("<vm( .*)? id=\"(.*?)\"", re.IGNORECASE)
RE_STATUS = re.compile("<state>(.*?)</state>", re.IGNORECASE)
RE_GET_NAME = re.compile("<name>(.*?)</name>", re.IGNORECASE)

def get_power_status(conn, options):
	del conn

	### Obtain real ID from name
	res = send_command(options, "vms/?search=name%3D" + options["--plug"])

	result = RE_GET_ID.search(res)
	if result == None:
		# Unable to obtain ID needed to access virtual machine
		fail(EC_STATUS)

	options["id"] = result.group(2)

	result = RE_STATUS.search(res)
	if result == None:
		# We were able to parse ID so output is correct
		# in some cases it is possible that RHEV-M output does not
		# contain <status> line. We can assume machine is OFF then
		return "off"
	else:
		status = result.group(1)

	if status.lower() == "down":
		return "off"
	else:
		return "on"

def set_power_status(conn, options):
	del conn
	action = {
		'on' : "start",
		'off' : "stop"
	}[options["--action"]]

	url = "vms/" + options["id"] + "/" + action
	send_command(options, url, "POST")

def get_list(conn, options):
	del conn
	outlets = {}

	try:
		res = send_command(options, "vms")

		lines = res.split("<vm ")
		for i in range(1, len(lines)):
			name = RE_GET_NAME.search(lines[i]).group(1)
			outlets[name] = ("", None)
	except AttributeError:
		return {}
	except IndexError:
		return {}

	return outlets

def send_command(opt, command, method="GET"):
	## setup correct URL
	if opt.has_key("--ssl") or opt.has_key("--ssl-secure") or opt.has_key("--ssl-insecure"):
		url = "https:"
	else:
		url = "http:"

	url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + "/api/" + command

	## send command through pycurl
	conn = pycurl.Curl()
	web_buffer = StringIO.StringIO()
	conn.setopt(pycurl.URL, url)
	conn.setopt(pycurl.HTTPHEADER, ["Content-type: application/xml", "Accept: application/xml", "Prefer: persistent-auth"])

	if opt.has_key("cookie"):
		conn.setopt(pycurl.COOKIE, opt["cookie"])
	else:
		conn.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
		conn.setopt(pycurl.USERPWD, opt["--username"] + ":" + opt["--password"])
		if opt.has_key("--use-cookies"):
			conn.setopt(pycurl.COOKIEFILE, "")

	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	if opt.has_key("--ssl") or opt.has_key("--ssl-secure"):
		conn.setopt(pycurl.SSL_VERIFYPEER, 1)
		conn.setopt(pycurl.SSL_VERIFYHOST, 2)

	if opt.has_key("--ssl-insecure"):
		conn.setopt(pycurl.SSL_VERIFYPEER, 0)
		conn.setopt(pycurl.SSL_VERIFYHOST, 0)

	if method == "POST":
		conn.setopt(pycurl.POSTFIELDS, "<action />")

	conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)
	conn.perform()

	if not opt.has_key("cookie") and opt.has_key("--use-cookies"):
		cookie = ""
		for c in conn.getinfo(pycurl.INFO_COOKIELIST):
			tokens = c.split("\t",7)
			cookie = cookie + tokens[5] + "=" + tokens[6] + ";"

		opt["cookie"] = cookie

	result = web_buffer.getvalue()

	logging.debug("%s\n", command)
	logging.debug("%s\n", result)

	return result

def define_new_opts():
	all_opt["use_cookies"] = {
		"getopt" : "",
		"longopt" : "use-cookies",
		"help" : "--use-cookies                  Reuse cookies for authentication",
		"required" : "0",
		"shortdesc" : "Reuse cookies for authentication",
		"order" : 1}

def main():
	device_opt = ["ipaddr", "login", "passwd", "ssl", "notls", "web", "port", "use_cookies" ]

	atexit.register(atexit_handler)
	define_new_opts()

	all_opt["power_wait"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for RHEV-M REST API"
	docs["longdesc"] = "fence_rhevm is an I/O Fencing agent which can be \
used with RHEV-M REST API to fence virtual machines."
	docs["vendorurl"] = "http://www.redhat.com"
	show_docs(options, docs)

	##
	## Fence operations
	####
	run_delay(options)
	result = fence_action(None, options, set_power_status, get_power_status, get_list)

	sys.exit(result)

if __name__ == "__main__":
	main()
