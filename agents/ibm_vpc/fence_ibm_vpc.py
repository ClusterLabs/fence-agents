#!@PYTHON@ -tt

import sys
import pycurl, io, json
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, run_delay, EC_LOGIN_DENIED, EC_STATUS

state = {
	 "running": "on",
	 "stopped": "off",
	 "starting": "unknown",
	 "stopping": "unknown",
	 "restarting": "unknown",
	 "pending": "unknown",
}

def get_list(conn, options):
	outlets = {}

	try:
		command = "instances?version=2021-05-25&generation=2&limit={}".format(options["--limit"])
		res = send_command(conn, command)
	except Exception as e:
		logging.debug("Failed: Unable to get list: {}".format(e))
		return outlets

	for r in res["instances"]:
		if options["--verbose-level"] > 1:
			logging.debug("Node:\n{}".format(json.dumps(r, indent=2)))
			logging.debug("Status: " + state[r["status"]])
		outlets[r["id"]] = (r["name"], state[r["status"]])

	return outlets

def get_power_status(conn, options):
	try:
		command = "instances/{}?version=2021-05-25&generation=2".format(options["--plug"])
		res = send_command(conn, command)
		result = state[res["status"]]
		if options["--verbose-level"] > 1:
			logging.debug("Result:\n{}".format(json.dumps(res, indent=2)))
			logging.debug("Status: " + result)
	except Exception as e:
		logging.debug("Failed: Unable to get status for {}: {}".format(options["--plug"], e))
		fail(EC_STATUS)

	return result

def set_power_status(conn, options):
	action = {
		"on" :  '{"type" : "start"}',
		"off" : '{"type" : "stop"}',
	}[options["--action"]]

	try:
		command = "instances/{}/actions?version=2021-05-25&generation=2".format(options["--plug"])
		send_command(conn, command, "POST", action, 201)
	except Exception as e:
		logging.debug("Failed: Unable to set power to {} for {}".format(options["--action"], e))
		fail(EC_STATUS)

def get_bearer_token(conn, options):
	token = None
	try:
		conn.setopt(pycurl.HTTPHEADER, [
			"Content-Type: application/x-www-form-urlencoded",
			"User-Agent: curl",
		])
		token = send_command(conn, "https://iam.cloud.ibm.com/identity/token", "POST", "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={}".format(options["--apikey"]))["access_token"]
	except Exception:
		logging.error("Failed: Unable to authenticate")
		fail(EC_LOGIN_DENIED)

	return token

def connect(opt):
	conn = pycurl.Curl()

	## setup correct URL
	conn.base_url = "https://" + opt["--region"] + ".iaas.cloud.ibm.com/v1/"

	if opt["--verbose-level"] > 1:
		conn.setopt(pycurl.VERBOSE, 1)

	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	conn.setopt(pycurl.SSL_VERIFYPEER, 1)
	conn.setopt(pycurl.SSL_VERIFYHOST, 2)

	# get bearer token
	bearer_token = get_bearer_token(conn, opt)

	# set auth token for later requests
	conn.setopt(pycurl.HTTPHEADER, [
		"Content-Type: application/json",
		"Authorization: Bearer {}".format(bearer_token),
		"User-Agent: curl",
	])

	return conn

def disconnect(conn):
	conn.close()

def send_command(conn, command, method="GET", action=None, expected_rc=200):
	if not command.startswith("https"):
		url = conn.base_url + command
	else:
		url = command

	conn.setopt(pycurl.URL, url.encode("ascii"))

	web_buffer = io.BytesIO()

	if method == "GET":
		conn.setopt(pycurl.POST, 0)
	if method == "POST":
		conn.setopt(pycurl.POSTFIELDS, action)
	if method == "DELETE":
		conn.setopt(pycurl.CUSTOMREQUEST, "DELETE")

	conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)

	try:
		conn.perform()
	except Exception as e:
		raise(e)

	rc = conn.getinfo(pycurl.HTTP_CODE)
	result = web_buffer.getvalue().decode("UTF-8")

	web_buffer.close()

	# actions (start/stop/reboot) report 201 when they've been created
	if rc != expected_rc:
		logging.debug("rc: {}, result: {}".format(rc, result))
		if len(result) > 0:
			raise Exception("{}: {}".format(rc, 
					result["value"]["messages"][0]["default_message"]))
		else:
			raise Exception("Remote returned {} for request to {}".format(rc, url))

	if len(result) > 0:
		result = json.loads(result)

	logging.debug("url: {}".format(url))
	logging.debug("method: {}".format(method))
	logging.debug("response code: {}".format(rc))
	logging.debug("result: {}\n".format(result))

	return result

def define_new_opts():
	all_opt["apikey"] = {
		"getopt" : ":",
		"longopt" : "apikey",
		"help" : "--apikey=[key]                 API Key",
		"required" : "1",
		"shortdesc" : "API Key",
		"order" : 0
	}
	all_opt["instance"] = {
		"getopt" : ":",
		"longopt" : "instance",
		"help" : "--instance=[instance]          Cloud Instance",
		"required" : "1",
		"shortdesc" : "Cloud Instance",
		"order" : 0
	}
	all_opt["region"] = {
		"getopt" : ":",
		"longopt" : "region",
		"help" : "--region=[region]              Region",
		"required" : "1",
		"shortdesc" : "Region",
		"order" : 0
	}
	all_opt["limit"] = {
		"getopt" : ":",
		"longopt" : "limit",
		"help" : "--limit=[number]               Limit number of nodes returned by API",
		"required" : "1",
		"default": 50,
		"shortdesc" : "Number of nodes returned by API",
		"order" : 0
	}


def main():
	device_opt = [
		"apikey",
		"instance",
		"region",
		"limit",
		"port",
		"no_password",
	]

	atexit.register(atexit_handler)
	define_new_opts()

	all_opt["shell_timeout"]["default"] = "15"
	all_opt["power_timeout"]["default"] = "30"
	all_opt["power_wait"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for IBM Cloud VPC"
	docs["longdesc"] = """fence_ibm_vpc is an I/O Fencing agent which can be \
used with IBM Cloud VPC to fence virtual machines."""
	docs["vendorurl"] = "https://www.ibm.com"
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
