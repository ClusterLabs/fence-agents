#!@PYTHON@ -tt

import sys
import pycurl
import io
import json
import logging
import atexit

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import all_opt, atexit_handler, check_input, process_input, show_docs, fence_action, fail, run_delay, EC_STATUS

state = {
	 "ACTIVE": "on",
	 "SHUTOFF": "off",
	 "HARD_REBOOT": "on",
	 "SOFT_REBOOT": "on",
	 "ERROR": "unknown"
}

def get_token(conn, options):
	try:
		if options["--token"][0] == '@':
			key_file = options["--token"][1:]
			try:
				# read the API key from a file
				with open(key_file, "r") as f:
					try:
						keys = json.loads(f.read())
						# data seems to be in json format
						# return the value of the item with the key 'Apikey'
						api_key = keys.get("Apikey", "")
						if not api_key:
							# backward compatibility: former key name was 'apikey'
							api_key = keys.get("apikey", "")
					# data is text, return as is
					except ValueError:
						f.seek(0)
						api_key = f.read().strip()
			except FileNotFoundError:
				logging.debug("Failed: Cannot open file {}".format(key_file))
				return "TOKEN_IS_MISSING_OR_WRONG"
		else:
			api_key = options["--token"]
		command = "identity/token"
		action = "grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey&apikey={}".format(api_key)
		res = send_command(conn, command, "POST", action, printResult=False)
	except Exception as e:
		logging.debug("Failed: {}".format(e))
		return "TOKEN_IS_MISSING_OR_WRONG"
	return res["access_token"]

def get_list(conn, options):
	outlets = {}

	try:
		command = "cloud-instances/{}/pvm-instances".format(options["--instance"])
		res = send_command(conn, command)
	except Exception as e:
		logging.debug("Failed: {}".format(e))
		return outlets

	for r in res["pvmInstances"]:
		if options["--verbose-level"] > 1:
			logging.debug(json.dumps(r, indent=2))
		outlets[r["pvmInstanceID"]] = (r["serverName"], state.get(r["status"], "unknown"))

	return outlets

def get_power_status(conn, options):
	outlets = {}
	logging.debug("Info: getting power status for LPAR " + options["--plug"] + " instance " + options["--instance"])
	try:
		command = "cloud-instances/{}/pvm-instances/{}".format(
				options["--instance"], options["--plug"])
		res = send_command(conn, command)
		outlets[res["pvmInstanceID"]] = (res["serverName"], state[res["status"]])
		if options["--verbose-level"] > 1:
			logging.debug(json.dumps(res, indent=2))
		result = outlets[options["--plug"]][1]
		logging.debug("Info: Status: {}".format(result))
	except KeyError as e:
		try:
			result = get_list(conn, options)[options["--plug"]][1]
		except KeyError as ex:
			logging.debug("Failed: Unable to get status for {}".format(ex))
			fail(EC_STATUS)

	return result

def set_power_status(conn, options):
	action = {
		"on" :  '{"action" : "start"}',
		"off" : '{"action" : "immediate-shutdown"}',
	}[options["--action"]]

	logging.debug("Info: set power status to " + options["--action"] + " for LPAR " + options["--plug"] + " instance " + options["--instance"])
	try:
		send_command(conn, "cloud-instances/{}/pvm-instances/{}/action".format(
				options["--instance"], options["--plug"]), "POST", action)
	except Exception as e:
		logging.debug("Failed: Unable to set power to {} for {}".format(options["--action"], e))
		fail(EC_STATUS)

def reboot_cycle(conn, options):
	action = {
		"reboot" :  '{"action" : "hard-reboot"}',
	}[options["--action"]]

	logging.debug("Info: start reboot cycle with action " + options["--action"] + " for LPAR " + options["--plug"] + " instance " + options["--instance"])
	try:
		send_command(conn, "cloud-instances/{}/pvm-instances/{}/action".format(
				options["--instance"], options["--plug"]), "POST", action)
	except Exception as e:
		result = get_power_status(conn, options)
		logging.debug("Info: Status {}".format(result))
		if result == "off":
			return True
		else:
			logging.debug("Failed: Unable to cycle with {} for {}".format(options["--action"], e))
			fail(EC_STATUS)
	return True

def connect(opt, token):
	conn = pycurl.Curl()

	## setup correct URL
	conn.base_url = "https://" + opt["--region"] + ".power-iaas.cloud.ibm.com/pcloud/v1/"
	if opt["--api-type"] == "private":
		conn.base_url = "https://private." + opt["--region"] + ".power-iaas.cloud.ibm.com/pcloud/v1/"

	if opt["--verbose-level"] < 3:
		conn.setopt(pycurl.VERBOSE, 0)

	conn.setopt(pycurl.CONNECTTIMEOUT,int(opt["--shell-timeout"]))
	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	conn.setopt(pycurl.SSL_VERIFYPEER, 1)
	conn.setopt(pycurl.SSL_VERIFYHOST, 2)
	conn.setopt(pycurl.PROXY, "{}".format(opt["--proxy"]))

	# set auth token for later requests
	conn.setopt(pycurl.HTTPHEADER, [
		"Content-Type: application/json",
		"Authorization: Bearer {}".format(token),
		"CRN: {}".format(opt["--crn"]),
		"User-Agent: curl",
	])

	return conn

def auth_connect(opt):
	conn = pycurl.Curl()

	# setup correct URL
	if opt["--api-type"] == "private":
		conn.base_url = "https://private.iam.cloud.ibm.com/"
	else:
		conn.base_url = "https://iam.cloud.ibm.com/"

	if opt["--verbose-level"] > 1:
		conn.setopt(pycurl.VERBOSE, 1)

	conn.setopt(pycurl.CONNECTTIMEOUT,int(opt["--shell-timeout"]))
	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	conn.setopt(pycurl.SSL_VERIFYPEER, 1)
	conn.setopt(pycurl.SSL_VERIFYHOST, 2)
	conn.setopt(pycurl.PROXY, "{}".format(opt["--proxy"]))

	# set auth token for later requests
	conn.setopt(pycurl.HTTPHEADER, [
		"Content-type: application/x-www-form-urlencoded",
		"Accept: application/json",
		"User-Agent: curl",
	])

	return conn

def disconnect(conn):
	conn.close()

def send_command(conn, command, method="GET", action=None, printResult=True):
	url = conn.base_url + command

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
		logging.error("send_command(): {}".format(e))
		raise(e)

	rc = conn.getinfo(pycurl.HTTP_CODE)
	result = web_buffer.getvalue().decode("UTF-8")

	web_buffer.close()

	if rc != 200:
		if len(result) > 0:
			raise Exception("{}: {}".format(rc,result))
		else:
			raise Exception("Remote returned {} for request to {}".format(rc, url))

	if len(result) > 0:
		result = json.loads(result)

	logging.debug("url: {}".format(url))
	logging.debug("method: {}".format(method))
	logging.debug("response code: {}".format(rc))
	if printResult:
		logging.debug("result: {}\n".format(result))

	return result

def define_new_opts():
	all_opt["token"] = {
		"getopt" : ":",
		"longopt" : "token",
		"help" : "--token=[token]                API Token",
		"required" : "1",
		"shortdesc" : "API Token",
		"order" : 0
	}
	all_opt["crn"] = {
		"getopt" : ":",
		"longopt" : "crn",
		"help" : "--crn=[crn]                    CRN",
		"required" : "1",
		"shortdesc" : "CRN",
		"order" : 0
	}
	all_opt["instance"] = {
		"getopt" : ":",
		"longopt" : "instance",
		"help" : "--instance=[instance]          PowerVS Instance",
		"required" : "1",
		"shortdesc" : "PowerVS Instance",
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
	all_opt["api-type"] = {
		"getopt" : ":",
		"longopt" : "api-type",
		"help" : "--api-type=[private|public]          API-type: 'private' (default) or 'public'",
		"required" : "0",
		"shortdesc" : "API-type (private|public)",
		"default" : "private",
		"order" : 0
	}
	all_opt["proxy"] = {
		"getopt" : ":",
		"longopt" : "proxy",
		"help" : "--proxy=[http://<URL>:<PORT>]          Proxy: 'http://<URL>:<PORT>'",
		"required" : "0",
		"shortdesc" : "Network proxy",
		"order" : 0
	}


def main():
	device_opt = [
		"token",
		"crn",
		"instance",
		"region",
		"api-type",
		"proxy",
		"port",
		"no_password",
		"method",
	]

	atexit.register(atexit_handler)
	define_new_opts()

	all_opt["shell_timeout"]["default"] = "500"
	all_opt["power_timeout"]["default"] = "120"
	all_opt["power_wait"]["default"] = "15"
	all_opt["stonith_status_sleep"]["default"] = "10"
	all_opt["proxy"]["default"] = ""

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for IBM PowerVS"
	docs["longdesc"] = """fence_ibm_powervs is a power fencing agent for \
IBM Power Virtual Server (IBM PowerVS) to fence virtual server instances."""
	docs["vendorurl"] = "https://www.ibm.com"
	show_docs(options, docs)

	####
	## Fence operations
	####
	run_delay(options)

	auth_conn = auth_connect(options)
	token = get_token(auth_conn, options)
	disconnect(auth_conn)
	conn = connect(options, token)
	atexit.register(disconnect, conn)

	result = fence_action(conn, options, set_power_status, get_power_status, get_list, reboot_cycle)

	sys.exit(result)

if __name__ == "__main__":
	main()
