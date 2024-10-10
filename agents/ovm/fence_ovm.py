#!@PYTHON@ -tt

import sys, time
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, Timeout, RequestException
from json.decoder import JSONDecodeError
import logging
import atexit
import itertools
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, run_delay, EC_GENERIC_ERROR, EC_CONNECTION_LOST, EC_TIMED_OUT

state = {"RUNNING" : "on", "STOPPED" : "off", "SUSPENDED" : "off"}

class SSLAdapter(HTTPAdapter):
	def __init__(self, certfile, password):
		import ssl
		from ssl import SSLError
		self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
		try:
			self.context.load_cert_chain(certfile=certfile, password=password)
		except SSLError as e:
			logging.error("Failed: The private key doesn't match with the certificate")
			fail(EC_GENERIC_ERROR)
		except OSError as e:
			logging.error("%s: %s", certfile, str(e))
			fail(EC_GENERIC_ERROR)
		super().__init__()

	def init_poolmanager(self, *args, **kwargs):
		kwargs["ssl_context"] = self.context
		return super().init_poolmanager(*args, **kwargs)

def get_power_status(connection, options):
	vm = send_command(connection, options, "/Vm/{}".format(options["--plug"]))
	return state.get(vm["vmRunState"])

def sync_set_power_status(connection, options):
	action = {
		"on" : "start",
		"off" : "kill"
	}[options["--action"]]
	job = send_command(connection, options, "/Vm/{}/{}".format(options["--plug"], action), "PUT")
	for _ in itertools.count(1):
		if not job["summaryDone"]:
			job = send_command(connection, options, "/Job/{}".format(job["id"]["value"]))
		if job["summaryDone"]:
			if job["jobRunState"].upper() == "FAILURE":
				logging.error("Job failed: %s", job["error"])
				return False
			elif job["jobRunState"].upper() == "SUCCESS":
				status = get_power_status(connection, options)
				if status != options["--action"]:
					logging.debug("Job succeed, but '%s' power status is %s", options["--plug"], status)
				else:
					return True
		time.sleep(int(options["--stonith-status-sleep"]))
		if int(options["--power-timeout"]) > 0 and _ >= int(options["--power-timeout"]):
			logging.error("Job failed: Timed out waiting for %s to power %s", options["--plug"], options["--action"])
			return False

def get_outlet_list(connection, options):
	virtual_machines = send_command(connection, options, "/Vm")
	result = {}
	for vm in virtual_machines:
		status = state.get(vm["vmRunState"])
		result[vm["id"]["value"]] = (vm["name"], status)
	return result

def connect(options):
	connection = requests.Session()
	password = options.get("--password")
	if "--username" in options:
		connection.auth = (options["--username"], password)
	else:
		base_uri = "https://{}:{}/ovm/core/wsapi/rest".format(options["--ip"], options["--ipport"])
		connection.mount(base_uri, SSLAdapter(options["--ssl-client-certificate-file"], password))
	connection.verify = ("--ssl-secure" in options) or ("--ssl-insecure" not in options)
	if connection.verify:
		if "--ssl-insecure" in options:
			logging.warning("The option '--ssl-insecure' is ignored")
	else:
		import urllib3
		urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
	connection.headers.update({
		"Accept" : "application/json",
		"Content-Type" : "application/json"
	})
	return connection

def send_command(connection, options, resources_path, method="GET"):
	uri = "https://{}:{}/ovm/core/wsapi/rest{}".format(options["--ip"], options["--ipport"], resources_path)
	timeout = int(options["--shell-timeout"])
	timeout = timeout if timeout != 0 else None
	try:
		if method == "GET":
			response = connection.get(uri, timeout=timeout)
		elif method == "PUT":
			response = connection.put(uri, timeout=timeout)
		else:
			logging.error("The method '%s' is not supported yet", method)
			fail(EC_GENERIC_ERROR)
	except ConnectionError as e:
		logging.error(str(e))
		fail(EC_CONNECTION_LOST)
	except Timeout as e:
		logging.error(str(e))
		fail(EC_TIMED_OUT)
	except RequestException as e:
		logging.error(str(e))
		fail(EC_GENERIC_ERROR)
	try:
		result = response.json()
	except JSONDecodeError as e:
		logging.error("%s is not valid JSON. Status code is %d", repr(str(response.content, response.encoding or "utf-8")), response.status_code)
		fail(EC_GENERIC_ERROR)
	logging.debug(result)
	if (method == "GET" and response.status_code != 200) or (method == "PUT" and response.status_code != 201):
		message = result.get("message") if type(result) is dict else None
		if message is None:
			logging.error("Failed: Remote returned %d for '%s' request to %s", response.status_code, method, uri)
		else:
			logging.error("Failed: %s: %d: %s", method, response.status_code, result["message"])
		fail(EC_GENERIC_ERROR)
	return result

def define_new_opts():
	all_opt["ssl_client_certificate_file"] = {
		"getopt" : ":",
		"longopt" : "ssl-client-certificate-file",
		"help" : "--ssl-client-certificate-file=[filename]   SSL client certificate file",
		"required" : "0",
		"order" : 1
	}

def validate_input(opt, stop=True):
	valid_input = True
	if "--username" not in opt and "--ssl-client-certificate-file" not in opt:
		valid_input = False
		fail_usage("Failed: You have to enter username or ssl client certificate file", stop)
	if "--username" in opt and "--ssl-client-certificate-file" in opt:
		valid_input = False
		fail_usage("Failed: You have to enter eather username or ssl client certificate file", stop)
	if "--username" in opt and ("--password" not in opt and "--password-script" not in opt):
		valid_input = False
		fail_usage("Failed: You have to enter password or password script", stop)
	if "--shell-timeout" in opt:
		try:
			timeout = int(opt["--shell-timeout"])
			if timeout < 0:
				valid_input = False
				fail_usage("Failed: Attempted to set --shell-timeout to %d, but the timeout cannot be set to a value less than 0" % timeout, stop)
		except ValueError:
			# Expect ValueError of --shell-timeout to be checked by fencing.check_input function
			pass
	return valid_input

def main():
	device_opt = ["ipaddr", "ipport", "login", "no_login", "passwd", "no_password", "port", "ssl", "ssl_client_certificate_file"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["ipport"]["default"] = "7002"

	opt = process_input(device_opt)
	if not(opt.get("--action") in ["metadata", "manpage"] or any(k in opt for k in ("--help", "--version"))):
		if opt.get("--action") == "validate-all":
			if not validate_input(opt, False):
				fail_usage("validate-all failed")
		else:
			validate_input(opt, True)
	options = check_input(device_opt, opt)

	docs = {}
	docs["shortdesc"] = "Fence agent for Oracle VM"
	docs["longdesc"] = "fence_ovm is a Power Fencing agent \
which can be used with the virtual machines managed by Oracle VM Manager."
	docs["vendorurl"] = "https://www.oracle.com/virtualization/technologies/vm/"
	show_docs(options, docs)

	run_delay(options)

	connection = connect(options)
	result = fence_action(connection, options, None, get_power_status, get_outlet_list=get_outlet_list, sync_set_power_fn=sync_set_power_status)

	sys.exit(result)

if __name__ == "__main__":
	main()
