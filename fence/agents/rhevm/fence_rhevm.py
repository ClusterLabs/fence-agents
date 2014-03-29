#!/usr/bin/python

import sys, re
import pycurl, StringIO
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New RHEV-M Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="March, 2008"
#END_VERSION_GENERATION


RE_GET_ID = re.compile("<vm( .*)? id=\"(.*?)\"", re.IGNORECASE)
RE_STATUS = re.compile("<state>(.*?)</state>", re.IGNORECASE)
RE_GET_NAME = re.compile("<name>(.*?)</name>", re.IGNORECASE)

def get_power_status(conn, options):
	### Obtain real ID from name
	res = send_command(options, "vms/?search=name%3D" + options["--plug"])

	result = RE_GET_ID.search(res)
	if (result == None):
		# Unable to obtain ID needed to access virtual machine
		fail(EC_STATUS)

	options["id"] = result.group(2)

	result = RE_STATUS.search(res)
	if (result == None):
		# We were able to parse ID so output is correct
		# in some cases it is possible that RHEV-M output does not
		# contain <status> line. We can assume machine is OFF then
		return "off"
	else:
		status = result.group(1)

	if (status.lower() == "down"):
		return "off"
	else:
		return "on"

def set_power_status(conn, options):
	action = {
		'on' : "start",
		'off' : "stop"
	}[options["--action"]]

	url = "vms/" + options["id"] + "/" + action
	res = send_command(options, url, "POST")

def get_list(conn, options):
	outlets = { }

	try:
		res = send_command(options, "vms")

		lines = res.split("<vm ")
		for i in range(1, len(lines)):
			name = RE_GET_NAME.search(lines[i]).group(1)
			outlets[name] = ("", None)
	except AttributeError:
		return { }
	except IndexError:
		return { }

	return outlets

def send_command(opt, command, method = "GET"):
	## setup correct URL
	if opt.has_key("--ssl"):
		url = "https:"
	else:
		url = "http:"

	url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + "/api/" + command

	## send command through pycurl
	c = pycurl.Curl()
	b = StringIO.StringIO()
	c.setopt(pycurl.URL, url)
	c.setopt(pycurl.HTTPHEADER, [ "Content-type: application/xml", "Accept: application/xml" ])
	c.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
	c.setopt(pycurl.USERPWD, opt["--username"] + ":" + opt["--password"])
	c.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	c.setopt(pycurl.SSL_VERIFYPEER, 0)
	c.setopt(pycurl.SSL_VERIFYHOST, 0)

	if (method == "POST"):
		c.setopt(pycurl.POSTFIELDS, "<action />")

	c.setopt(pycurl.WRITEFUNCTION, b.write)
	c.perform()
	result = b.getvalue()

	logging.debug("%s\n" % command)
	logging.debug("%s\n" % result)

	return result

def main():
	device_opt = [ "ipaddr", "login", "passwd", "ssl", "notls", "web", "port" ]

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
