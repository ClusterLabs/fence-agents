#!@PYTHON@ -tt

import sys, re
import pycurl, io
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS, EC_LOGIN_DENIED, run_delay

RE_COOKIE = re.compile("<aaaLogin .* outCookie=\"(.*?)\"", re.IGNORECASE)
RE_STATUS = re.compile("<lsPower .*? state=\"(.*?)\"", re.IGNORECASE)
RE_GET_DN = re.compile(" dn=\"(.*?)\"", re.IGNORECASE)
RE_GET_PNDN = re.compile(" pndn=\"(.*?)\"", re.IGNORECASE)
RE_GET_DESC = re.compile(" descr=\"(.*?)\"", re.IGNORECASE)
RE_GET_OPERPOWER = re.compile(" operPower=\"(.*?)\"", re.IGNORECASE)
RE_GET_PRESENCE = re.compile(" presence=\"(.*?)\"", re.IGNORECASE)

options_global = None

def get_power_status(conn, options):
	del conn

	res = send_command(options, "<configResolveDn cookie=\"" + options["cookie"] +
			"\" inHierarchical=\"false\" dn=\"org-root" + options["--suborg"] + "/ls-" +
			options["--plug"] + "\"/>", int(options["--shell-timeout"]))

	result = RE_GET_PNDN.search(res)
	if result == None:
		pndn = ""
	else:
		pndn = result.group(1)

	if pndn.strip() == "":
		if "--missing-as-off" in options:
			return "off"
		else:
			fail(EC_STATUS)

	res = send_command(options, "<configResolveDn cookie=\"" + options["cookie"] +
			"\" inHierarchical=\"false\" dn=\"" + pndn +
			"\"/>", int(options["--shell-timeout"]))

	result = RE_GET_PRESENCE.search(res)
	if result == None:
		fail(EC_STATUS)
	else:
		presence_status = result.group(1)

	if presence_status in ["missing", "mismatch"]:
		return "off"
	else:
		result = RE_GET_OPERPOWER.search(res)
		if result == None:
			fail(EC_STATUS)
		else:
			power_status = result.group(1)

		if power_status == "on":
			return "on"
		else:
			return "off"

def set_power_status(conn, options):
	del conn

	action = {
		'on' : "admin-up",
		'off' : "admin-down"
	}[options["--action"]]

	send_command(options, "<configConfMos cookie=\"" + options["cookie"] + "\" inHierarchical=\"no\">" +
			"<inConfigs><pair key=\"org-root" + options["--suborg"] + "/ls-" + options["--plug"] +
			"/power\">" + "<lsPower dn=\"org-root/ls-" + options["--plug"] + "/power\" state=\"" +
			action + "\" status=\"modified\" />" + "</pair></inConfigs></configConfMos>",
			int(options["--shell-timeout"]))

	return

def get_list(conn, options):
	del conn
	outlets = {}

	try:
		res = send_command(options, "<configResolveClass cookie=\"" + options["cookie"] +
				"\" inHierarchical=\"false\" classId=\"lsServer\"/>", int(options["--shell-timeout"]))

		lines = res.split("<lsServer ")
		for i in range(1, len(lines)):
			node_name = RE_GET_DN.search(lines[i]).group(1)
			desc = RE_GET_DESC.search(lines[i]).group(1)
			outlets[node_name] = (desc, None)
	except AttributeError:
		return {}
	except IndexError:
		return {}

	return outlets

def send_command(opt, command, timeout):
	## setup correct URL
	if "--ssl" in opt or "--ssl-secure" in opt or "--ssl-insecure" in opt:
		url = "https:"
	else:
		url = "http:"

	url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + "/nuova"

	## send command through pycurl
	conn = pycurl.Curl()
	web_buffer = io.BytesIO()
	conn.setopt(pycurl.URL, url.encode("ascii"))
	conn.setopt(pycurl.HTTPHEADER, ["Content-type: text/xml"])
	conn.setopt(pycurl.POSTFIELDS, command)
	conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)
	conn.setopt(pycurl.TIMEOUT, timeout)
	if "--ssl" in opt or "--ssl-secure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 1)
		conn.setopt(pycurl.SSL_VERIFYHOST, 2)

	if "--ssl-insecure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 0)
		conn.setopt(pycurl.SSL_VERIFYHOST, 0)
	conn.perform()
	result = web_buffer.getvalue().decode()

	logging.debug("%s\n", command)
	logging.debug("%s\n", result)

	return result

def define_new_opts():
	all_opt["suborg"] = {
		"getopt" : ":",
		"longopt" : "suborg",
		"help" : "--suborg=[path]                Additional path needed to access suborganization",
		"required" : "0",
		"shortdesc" : "Additional path needed to access suborganization",
		"default" : "",
		"order" : 1}

def logout():
	### Logout; we do not care about result as we will end in any case
	try:
		send_command(options_global, "<aaaLogout inCookie=\"" + options_global["cookie"] + "\" />",
				int(options_global["--shell-timeout"]))
	except Exception:
		pass

def main():
	global options_global
	device_opt = ["ipaddr", "login", "passwd", "ssl", "notls", "port", "web", "suborg", "missing_as_off"]

	atexit.register(atexit_handler)
	atexit.register(logout)

	define_new_opts()

	options_global = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Cisco UCS"
	docs["longdesc"] = "fence_cisco_ucs is an I/O Fencing agent which can be \
used with Cisco UCS to fence machines."
	docs["vendorurl"] = "http://www.cisco.com"
	show_docs(options_global, docs)

	run_delay(options_global)
	### Login
	try:
		res = send_command(options_global, "<aaaLogin inName=\"" + options_global["--username"] +
				"\" inPassword=\"" + options_global["--password"] + "\" />", int(options_global["--login-timeout"]))
		result = RE_COOKIE.search(res)
		if result == None:
			## Cookie is absenting in response
			fail(EC_LOGIN_DENIED)
	except Exception:
		fail(EC_LOGIN_DENIED)

	options_global["cookie"] = result.group(1)

	##
	## Modify suborg to format /suborg
	if options_global["--suborg"] != "":
		options_global["--suborg"] = "/" + options_global["--suborg"].lstrip("/").rstrip("/")

	##
	## Fence operations
	####
	result = fence_action(None, options_global, set_power_status, get_power_status, get_list)

	## Logout is done every time at atexit phase
	sys.exit(result)

if __name__ == "__main__":
	main()
