#!@PYTHON@ -tt

import sys, re
import pycurl, io
import logging
import atexit
import tempfile
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_FETCH_VM_UUID, run_delay

RE_GET_ID = re.compile(r"<vm( .*)? id=\"(.*?)\"", re.IGNORECASE)
RE_STATUS = re.compile(r"<status>(.*?)</status>", re.IGNORECASE)
RE_STATE = re.compile(r"<state>(.*?)</state>", re.IGNORECASE)
RE_GET_NAME = re.compile(r"<name>(.*?)</name>", re.IGNORECASE)

def get_power_status(conn, options):
	del conn

	### Obtain real ID from name
	res = send_command(options, "vms/?search=name%3D" + options["--plug"])

	result = RE_GET_ID.search(res)
	if result == None:
		# Unable to obtain ID needed to access virtual machine
		fail(EC_FETCH_VM_UUID)

	options["id"] = result.group(2)

	if tuple(map(int, options["--api-version"].split(".")))[0] > 3:
		result = RE_STATUS.search(res)
	else:
		result = RE_STATE.search(res)
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
			if tuple(map(int, options["--api-version"].split(".")))[0] > 3:
				status = RE_STATUS.search(lines[i]).group(1)
			else:
				status = RE_STATE.search(lines[i]).group(1)
			outlets[name] = ("", status)
	except AttributeError:
		return {}
	except IndexError:
		return {}

	return outlets

def send_command(opt, command, method="GET"):
	if opt["--api-version"] == "auto":
		opt["--api-version"] = "4"
		res = send_command(opt, "")
		if re.search(r"<title>Error</title>", res):
			opt["--api-version"] = "3"
		logging.debug("auto-detected API version: " + opt["--api-version"])

	## setup correct URL
	if "--ssl-secure" in opt or "--ssl-insecure" in opt:
		url = "https:"
	else:
		url = "http:"
	if "--api-path" in opt:
		api_path = opt["--api-path"]
	else:
		api_path = "/ovirt-engine/api"
	if "--disable-http-filter" in opt:
		http_filter = 'false'
	else:
		http_filter = 'true'

	url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + api_path + "/" + command

	## send command through pycurl
	conn = pycurl.Curl()
	web_buffer = io.BytesIO()
	conn.setopt(pycurl.URL, url.encode("UTF-8"))
	conn.setopt(pycurl.HTTPHEADER, [
		"Version: {}".format(opt["--api-version"]),
		"Content-type: application/xml",
		"Accept: application/xml",
		"Prefer: persistent-auth",
		"Filter: {}".format(http_filter),
	])

	if "cookie" in opt:
		conn.setopt(pycurl.COOKIE, opt["cookie"])
	else:
		conn.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
		conn.setopt(pycurl.USERPWD, opt["--username"] + ":" + opt["--password"])
		if "--use-cookies" in opt:
			if "--cookie-file" in opt:
				cookie_file = opt["--cookie-file"]
			else:
				cookie_file = tempfile.gettempdir() + "/fence_rhevm_" + opt["--ip"] + "_" + opt["--username"] + "_cookie.dat"
			conn.setopt(pycurl.COOKIEFILE, cookie_file)
			conn.setopt(pycurl.COOKIEJAR, cookie_file)

	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))

	if "--ssl-secure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 1)
		conn.setopt(pycurl.SSL_VERIFYHOST, 2)
	elif "--ssl-insecure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 0)
		conn.setopt(pycurl.SSL_VERIFYHOST, 0)

	if method == "POST":
		conn.setopt(pycurl.POSTFIELDS, "<action />")

	conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)
	conn.perform()

	if "cookie" not in opt and "--use-cookies" in opt:
		cookie = ""
		for c in conn.getinfo(pycurl.INFO_COOKIELIST):
			tokens = c.split("\t",7)
			cookie = cookie + tokens[5] + "=" + tokens[6] + ";"

		opt["cookie"] = cookie

	result = web_buffer.getvalue().decode("UTF-8")

	logging.debug("url: %s\n", url.encode("UTF-8"))
	logging.debug("command: %s\n", command.encode("UTF-8"))
	logging.debug("result: %s\n", result.encode("UTF-8"))

	return result

def define_new_opts():

	all_opt["port"] = {
		"getopt" : "n:",
		"longopt" : "plug",
		"help" : "-n, --plug=[name]              "
			 "VM name in RHV",
		"required" : "1",
		"order" : 1}
	all_opt["use_cookies"] = {
		"getopt" : "",
		"longopt" : "use-cookies",
		"help" : "--use-cookies                  Reuse cookies for authentication",
		"required" : "0",
		"shortdesc" : "Reuse cookies for authentication",
		"order" : 1}
	all_opt["cookie_file"] = {
		"getopt" : ":",
		"longopt" : "cookie-file",
		"help" : "--cookie-file                  Path to cookie file for authentication\n"
                        "\t\t\t\t  (Default: /tmp/fence_rhevm_ip_username_cookie.dat)",
		"required" : "0",
		"shortdesc" : "Path to cookie file for authentication",
		"order" : 2}
	all_opt["api_version"] = {
		"getopt" : ":",
		"longopt" : "api-version",
		"help" : "--api-version                  "
			"Version of RHEV API (default: auto)",
		"required" : "0",
		"order" : 2,
		"default" : "auto",
	}
	all_opt["api_path"] = {
		"getopt" : ":",
		"longopt" : "api-path",
		"help" : "--api-path=[path]              The path part of the API URL",
		"default" : "/ovirt-engine/api",
		"required" : "0",
		"shortdesc" : "The path part of the API URL",
		"order" : 3}
	all_opt["disable_http_filter"] = {
		"getopt" : "",
		"longopt" : "disable-http-filter",
		"help" : "--disable-http-filter          Set HTTP Filter header to false",
		"required" : "0",
		"shortdesc" : "Set HTTP Filter header to false",
		"order" : 4}


def main():
	device_opt = [
		"ipaddr",
		"login",
		"passwd",
		"ssl",
		"notls",
		"web",
		"port",
		"use_cookies",
		"cookie_file",
		"api_version",
		"api_path",
		"disable_http_filter",
	]

	atexit.register(atexit_handler)
	define_new_opts()

	all_opt["power_wait"]["default"] = "1"
	all_opt["shell_timeout"]["default"] = "5"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for RHEV-M REST API"
	docs["longdesc"] = "fence_rhevm is a Power Fencing agent which can be \
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
