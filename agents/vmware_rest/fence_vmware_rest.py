#!@PYTHON@ -tt

import sys
import pycurl, io, json
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, run_delay, EC_LOGIN_DENIED, EC_STATUS

state = {"POWERED_ON": "on", 'POWERED_OFF': "off"}

def get_power_status(conn, options):
	res = send_command(conn, "vcenter/vm?filter.names={}".format(options["--plug"]))["value"]

	if len(res) == 0:
		fail(EC_STATUS)

	options["id"] = res[0]["vm"]

	result = res[0]["power_state"]

	return state[result]

def set_power_status(conn, options):
	action = {
		"on" : "start",
		"off" : "stop"
	}[options["--action"]]

	send_command(conn, "vcenter/vm/{}/power/{}".format(options["id"], action), "POST")

def get_list(conn, options):
	outlets = {}

	res = send_command(conn, "vcenter/vm")

	for r in res["value"]:
		outlets[r["name"]] = ("", state[r["power_state"]])

	return outlets

def connect(opt):
	conn = pycurl.Curl()

	## setup correct URL
	if "--ssl" in opt or "--ssl-secure" in opt or "--ssl-insecure" in opt:
		conn.base_url = "https:"
	else:
		conn.base_url = "http:"
	if "--api-path" in opt:
		api_path = opt["--api-path"]
	else:
		api_path = "/rest"

	conn.base_url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + api_path + "/"

	## send command through pycurl
	conn.setopt(pycurl.HTTPHEADER, [
		"Accept: application/json",
	])

	conn.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
	conn.setopt(pycurl.USERPWD, opt["--username"] + ":" + opt["--password"])

	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	if "--ssl" in opt or "--ssl-secure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 1)
		conn.setopt(pycurl.SSL_VERIFYHOST, 2)

	if "--ssl-insecure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 0)
		conn.setopt(pycurl.SSL_VERIFYHOST, 0)

	try:
		result = send_command(conn, "com/vmware/cis/session", "POST")
	except Exception as e:
		logging.debug("Failed: {}".format(e))
		fail(EC_LOGIN_DENIED)

	# set session id for later requests
	conn.setopt(pycurl.HTTPHEADER, [
		"Accept: application/json",
		"vmware-api-session-id: {}".format(result["value"]),
	])

	return conn

def disconnect(conn):
	send_command(conn, "com/vmware/cis/session", "DELETE")
	conn.close()

def send_command(conn, command, method="GET"):
	url = conn.base_url + command

	conn.setopt(pycurl.URL, url.encode("ascii"))

	web_buffer = io.BytesIO()

	if method == "GET":
		conn.setopt(pycurl.POST, 0)
	if method == "POST":
		conn.setopt(pycurl.POSTFIELDS, "")
	if method == "DELETE":
		conn.setopt(pycurl.CUSTOMREQUEST, "DELETE")

	conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)

	try:
		conn.perform()
	except Exception as e:
		raise Exception(e[1])

	rc = conn.getinfo(pycurl.HTTP_CODE)
	result = web_buffer.getvalue().decode()

	web_buffer.close()

	if len(result) > 0:
		result = json.loads(result)

	if rc != 200:
		raise Exception("{}: {}".format(rc, result["value"]["messages"][0]["default_message"]))

	logging.debug("url: {}".format(url))
	logging.debug("method: {}".format(method))
	logging.debug("response code: {}".format(rc))
	logging.debug("result: {}\n".format(result))

	return result

def define_new_opts():
	all_opt["api_path"] = {
		"getopt" : ":",
		"longopt" : "api-path",
		"help" : "--api-path=[path]              The path part of the API URL",
		"default" : "/rest",
		"required" : "0",
		"shortdesc" : "The path part of the API URL",
		"order" : 2}


def main():
	device_opt = [
		"ipaddr",
		"api_path",
		"login",
		"passwd",
		"ssl",
		"notls",
		"web",
		"port",
	]

	atexit.register(atexit_handler)
	define_new_opts()

	all_opt["shell_timeout"]["default"] = "5"
	all_opt["power_wait"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for VMware REST API"
	docs["longdesc"] = "fence_vmware_rest is an I/O Fencing agent which can be \
used with VMware API to fence virtual machines."
	docs["vendorurl"] = "https://www.vmware.com"
	show_docs(options, docs)

	####
	## Fence operations
	####
	run_delay(options)

	conn = connect(options)
	atexit.register(disconnect, conn)

	result = fence_action(conn, options, set_power_status, get_power_status, get_list)

	sys.exit(result)

if __name__ == "__main__":
	main()
