#!@PYTHON@ -tt
import sys
import pycurl
import io
import json
import logging
import atexit

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, run_delay, EC_LOGIN_DENIED, EC_STATUS


state = {True: "on", False: "off"}


def get_power_status(conn, opt):
	try:
		result = send_command(conn, gen_payload(opt, "Switch.GetStatus"))
	except Exception as e:
		fail(EC_STATUS)
	# Shelly Documentation Uses `params` subkey:
	# https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Switch/#switchgetstatus-example
	# Observed behavior (ShellyHTTP/1.0.0) uses `result` subkey
	# Used Shelly Plus Plug US - FW 1.5.1
	if "params" in result:
		subkey = "params"
	elif "result" in result:
		subkey = "result"
	return state[result[subkey]["output"]]


def set_power_status(conn, opt):
	action = {state[k]: k for k in state}
	output = action[opt["--action"]]
	try:
		result = send_command(conn, gen_payload(opt, "Switch.Set", output=output))
	except Exception as e:
		fail(EC_STATUS)


# We use method here as the RPC procedure not HTTP method as all commands use POST
def gen_payload(opt, method, output=None):
	ret = {"id": 1,
		   "method": method,
		   "params": {"id": opt["--plug"]}}
	if output is not None:
		ret["params"]["on"] = output
	return ret


def connect(opt):
	conn = pycurl.Curl()

	## setup correct URL
	if "--ssl-secure" in opt or "--ssl-insecure" in opt:
		conn.base_url = "https:"
	else:
		conn.base_url = "http:"

	api_path = "/rpc"
	conn.base_url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + api_path

	## send command through pycurl
	conn.setopt(pycurl.HTTPHEADER, [
		"Accept: application/json",
	])

	# Shelly always uses a default user of admin
	# ex. https://shelly-api-docs.shelly.cloud/gen2/General/Authentication#successful-request-with-authentication-details
	if "--password" in opt:
		conn.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_ANY)
		conn.setopt(pycurl.USERPWD, "admin:" + opt["--password"])
	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	if "--ssl-secure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 1)
		conn.setopt(pycurl.SSL_VERIFYHOST, 2)
	elif "--ssl-insecure" in opt:
		conn.setopt(pycurl.SSL_VERIFYPEER, 0)
		conn.setopt(pycurl.SSL_VERIFYHOST, 0)

	# Check general reachability (unprotected method)
	try:
		device_info_payload = {"id": 1, "method": "Shelly.GetDeviceInfo"}
		_ = send_command(conn, device_info_payload)
	except Exception as e:
		logging.debug("Failed: {}".format(e))
		fail(EC_LOGIN_DENIED)

	# Check method requiring authentication
	try:
		_ = send_command(conn, gen_payload(opt, "Switch.GetStatus"))
	except Exception as e:
		logging.debug("Invalid Authentication: {}".format(e))
	return conn


def send_command(conn, payload):
	conn.setopt(pycurl.URL, conn.base_url.encode("ascii"))
	conn.setopt(pycurl.POSTFIELDS, json.dumps(payload))
	web_buffer = io.BytesIO()
	conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)
	try:
		conn.perform()
	except Exception as e:
		raise(e)
	rc = conn.getinfo(pycurl.HTTP_CODE)
	result = web_buffer.getvalue().decode("UTF-8")
	web_buffer.close()
	if rc != 200:
		if len(result) > 0:
			raise Exception("Remote returned {}: {}".format(rc, result))
		else:
			raise Exception("Remote returned {} for request to {}".format(rc, conn.base_url))
	if len(result) > 0:
		result = json.loads(result)
	logging.debug("url: {}".format(conn.base_url))
	logging.debug("POST method payload: {}".format(payload))
	logging.debug("response code: {}".format(rc))
	logging.debug("result: {}\n".format(result))
	return result

def main():
	device_opt = [
		"ipaddr",
		"passwd",
		"ssl",
		"notls",
		"web",
		"port",
	]

	atexit.register(atexit_handler)
	all_opt["shell_timeout"]["default"] = "5"
	all_opt["power_wait"]["default"] = "1"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Shelly Gen 2+ Switches"
	docs["longdesc"] = """fence_shelly_gen2 is a Power Fencing agent which can be \
used with Shelly Switches supporting the gen 2+ API to fence attached hardware."""
	docs["vendorurl"] = "https://shelly-api-docs.shelly.cloud/gen2/"
	show_docs(options, docs)

	####
	## Fence operations
	####
	run_delay(options)
	conn = connect(options)
	atexit.register(conn.close)
	result = fence_action(conn, options, set_power_status, get_power_status)
	sys.exit(result)

if __name__ == "__main__":
	main()

