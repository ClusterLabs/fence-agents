#!@PYTHON@ -tt

# The Following Agent Has Been Tested On:
# ePowerSwitch 8M+ version 1.0.0.4

import sys, os, re
import base64, socket
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_LOGIN_DENIED, EC_TIMED_OUT, run_delay

if sys.version_info[0] > 2:
	import http.client as httplib
else:
	import httplib

# Run command on EPS device.
# @param options Device options
# @param params HTTP GET parameters (without ?)
def eps_run_command(options, params):
	try:
		# New http connection
		conn = httplib.HTTPConnection(options["--ip"])

		request_str = "/"+options["--page"]

		if params != "":
			request_str += "?"+params

		logging.debug("GET %s\n", request_str)
		conn.putrequest('GET', request_str)

		if "--username" in options:
			if "--password" not in options:
				options["--password"] = "" # Default is empty password

			# String for Authorization header
			auth_str = 'Basic ' + str(base64.encodebytes(bytes(options["--username"]+':'+options["--password"], "utf-8")).decode("utf-8").strip())
			logging.debug("Authorization: %s\n", auth_str)
			conn.putheader('Authorization', auth_str)

		conn.endheaders()

		response = conn.getresponse()

		logging.debug("%d %s\n", response.status, response.reason)

		#Response != OK -> couldn't login
		if response.status != 200:
			fail(EC_LOGIN_DENIED)

		result = response.read()
		logging.debug("%s \n", result)
		conn.close()
	except socket.timeout:
		fail(EC_TIMED_OUT)
	except socket.error as e:
		logging.error("Failed: {}".format(str(e)))
		fail(EC_LOGIN_DENIED)

	return result.decode("utf-8", "ignore")

def get_power_status(conn, options):
	del conn
	ret_val = eps_run_command(options, "")

	result = {}
	if os.path.basename(sys.argv[0]) == "fence_eps":
		status = re.findall(r"p(\d{2})=(0|1)\s*\<br\>", ret_val.lower())
	elif os.path.basename(sys.argv[0]) == "fence_epsr2":
		status = re.findall(r"m0:o(\d)=(on|off)\s*", ret_val.lower())
	for out_num, out_stat in status:
		if os.path.basename(sys.argv[0]) == "fence_eps":
			result[out_num] = ("", (out_stat == "1" and "on" or "off"))
		elif os.path.basename(sys.argv[0]) == "fence_epsr2":
			result[out_num] = ("", out_stat)

	if not options["--action"] in ['monitor', 'list']:
		if not options["--plug"] in result:
			fail_usage("Failed: You have to enter existing physical plug!")
		else:
			return result[options["--plug"]][1]
	else:
		return result

def set_power_status(conn, options):
	del conn
	if os.path.basename(sys.argv[0]) == "fence_eps":
		eps_run_command(options, "P%s=%s"%(options["--plug"], (options["--action"] == "on" and "1" or "0")))
	elif os.path.basename(sys.argv[0]) == "fence_epsr2":
		if options["--action"] == "reboot":
			options["--action"] = "off"
		eps_run_command(options, "M0:O%s=%s"%(options["--plug"], options["--action"]))

# Define new option
def eps_define_new_opts():
	all_opt["hidden_page"] = {
		"getopt" : "c:",
		"longopt" : "page",
		"help":"-c, --page=[page]              Name of hidden page (default: hidden.htm)",
		"required" : "0",
		"shortdesc" : "Name of hidden page",
		"default" : "hidden.htm",
		"order": 1
		}

# Starting point of fence agent
def main():
	device_opt = ["ipaddr", "login", "passwd", "no_login", "no_password", \
			"port", "hidden_page", "web"]

	atexit.register(atexit_handler)

	eps_define_new_opts()

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["agent_name"] = "fence_eps"
	docs["shortdesc"] = "Fence agent for ePowerSwitch"
	docs["longdesc"] = os.path.basename(sys.argv[0]) + " is a Power Fencing agent \
which can be used with the ePowerSwitch 8M+ power switch to fence \
connected machines. It ONLY works on 8M+ devices, as \
they support the hidden page feature. \
\n.TP\n\
The agent works by connecting to the hidden page and pass \
the appropriate arguments to GET request. This means, that the hidden \
page feature must be enabled and properly configured. \
\n.TP\n\
NOTE: In most cases you want to use fence_epsr2, as fence_eps \
only works with older hardware."
	docs["vendorurl"] = "https://www.neol.com"
	docs["symlink"] = [("fence_epsr2", "Fence agent for ePowerSwitch R2 and newer")]
	show_docs(options, docs)

	run_delay(options)
	#Run fence action. Conn is None, because we always need open new http connection
	result = fence_action(None, options, set_power_status, get_power_status, get_power_status)

	sys.exit(result)

if __name__ == "__main__":
	main()
