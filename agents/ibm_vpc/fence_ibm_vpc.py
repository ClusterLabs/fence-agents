#!@PYTHON@ -tt

import sys
import pycurl, io, json
import logging
import atexit
import hashlib
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, run_delay, EC_BAD_ARGS, EC_LOGIN_DENIED, EC_STATUS, EC_GENERIC_ERROR

state = {
	 "running": "on",
	 "stopped": "off",
	 "starting": "unknown",
	 "stopping": "unknown",
	 "restarting": "unknown",
	 "pending": "unknown",
     "deleting": "unknown",
     "failed": "unknown",
}

def get_list(conn, options):
	outlets = {}

	try:
		command = "instances?version=2021-05-25&generation=2&limit={}".format(options["--limit"])
		res = send_command(conn, options, command)
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
		res = send_command(conn, options, command)
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
		send_command(conn, options, command, "POST", action, 201)
	except Exception as e:
		logging.debug("Failed: Unable to set power to {} for {}".format(options["--action"], e))
		fail(EC_STATUS)

def get_bearer_token(conn, options):
	import os, errno

	try:
		# FIPS requires usedforsecurity=False and might not be
		# available on all distros: https://bugs.python.org/issue9216
		hash = hashlib.sha256(options["--apikey"].encode("utf-8"), usedforsecurity=False).hexdigest()
	except (AttributeError, TypeError):
		hash = hashlib.sha256(options["--apikey"].encode("utf-8")).hexdigest()
	file_path = options["--token-file"].replace("[hash]", hash)
	token = None

	if not os.path.isdir(os.path.dirname(file_path)):
		os.makedirs(os.path.dirname(file_path))

	# For security, remove file with potentially elevated mode
	try:
		os.remove(file_path)
	except OSError:
		pass

	try:
		oldumask = os.umask(0)
		file_handle = os.open(file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
	except OSError as e:
		if e.errno == errno.EEXIST:  # Failed as the file already exists.
			logging.error("Failed: File already exists: {}".format(e))
			sys.exit(EC_GENERIC_ERROR)
		else:  # Something unexpected went wrong
			logging.error("Failed: Unable to open file: {}".format(e))
			sys.exit(EC_GENERIC_ERROR)
	else:  # No exception, so the file must have been created successfully.
		with os.fdopen(file_handle, 'w') as file_obj:
			try:
				conn.setopt(pycurl.HTTPHEADER, [
					"Content-Type: application/x-www-form-urlencoded",
					"User-Agent: curl",
				])
				token = send_command(conn, options, "https://iam.cloud.ibm.com/identity/token", "POST", "grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={}".format(options["--apikey"]))["access_token"]
			except Exception as e:
				logging.error("Failed: Unable to authenticate: {}".format(e))
				fail(EC_LOGIN_DENIED)
			if len(token) < 1:
				fail(EC_LOGIN_DENIED)
			file_obj.write(token)
	finally:
		os.umask(oldumask)

	return token

def set_bearer_token(conn, bearer_token):
	conn.setopt(pycurl.HTTPHEADER, [
		"Content-Type: application/json",
		"Authorization: Bearer {}".format(bearer_token),
		"User-Agent: curl",
	])

	return conn

def connect(opt):
	conn = pycurl.Curl()
	bearer_token = ""

	## setup correct URL
	conn.base_url = "https://" + opt["--region"] + ".iaas.cloud.ibm.com/v1/"

	if opt["--verbose-level"] > 1:
		conn.setopt(pycurl.VERBOSE, 1)

	conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
	conn.setopt(pycurl.SSL_VERIFYPEER, 1)
	conn.setopt(pycurl.SSL_VERIFYHOST, 2)
	conn.setopt(pycurl.PROXY, "{}".format(opt["--proxy"]))

	# get bearer token
	try:
		try:
			# FIPS requires usedforsecurity=False and might not be
			# available on all distros: https://bugs.python.org/issue9216
			hash = hashlib.sha256(opt["--apikey"].encode("utf-8"), usedforsecurity=False).hexdigest()
		except (AttributeError, TypeError):
			hash = hashlib.sha256(opt["--apikey"].encode("utf-8")).hexdigest()
		f = open(opt["--token-file"].replace("[hash]", hash))
		bearer_token = f.read()
		f.close()
	except IOError:
		bearer_token = get_bearer_token(conn, opt)

	# set auth token for later requests
	conn = set_bearer_token(conn, bearer_token)

	try:
		command = "instances?version=2021-05-25&generation=2&limit=1"
		res = send_command(conn, opt, command)
	except Exception as e:
		logging.warning("Failed to login/connect. Updating bearer-token.")
		bearer_token = get_bearer_token(conn, opt)
		conn = set_bearer_token(conn, bearer_token)

	return conn

def disconnect(conn):
	conn.close()

def send_command(conn, options, command, method="GET", action=None, expected_rc=200):
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

	# auth if token has expired
	if rc in [400, 401, 415]:
		tokenconn = pycurl.Curl()
		token = get_bearer_token(tokenconn, options)
		tokenconn.close()
		conn = set_bearer_token(conn, token)

		# flush web_buffer
		web_buffer.close()
		web_buffer = io.BytesIO()
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
	all_opt["region"] = {
		"getopt" : ":",
		"longopt" : "region",
		"help" : "--region=[region]              Region",
		"required" : "1",
		"shortdesc" : "Region",
		"order" : 0
	}
	all_opt["proxy"] = {
                "getopt" : ":",
                "longopt" : "proxy",
                "help" : "--proxy=[http://<URL>:<PORT>]  Proxy: 'http://<URL>:<PORT>'",
                "required" : "0",
		"default": "",
                "shortdesc" : "Network proxy",
                "order" : 0
        }
	all_opt["limit"] = {
		"getopt" : ":",
		"longopt" : "limit",
		"help" : "--limit=[number]               Limit number of nodes returned by API",
		"required" : "0",
		"default": 50,
		"shortdesc" : "Number of nodes returned by API",
		"order" : 0
	}
	all_opt["token_file"] = {
		"getopt" : ":",
		"longopt" : "token-file",
		"help" : "--token-file=[path]            Path to the token cache file\n"
			"\t\t\t\t  (Default: @FENCETMPDIR@/fence_ibm_vpc/[hash].token)\n"
			"\t\t\t\t  [hash] will be replaced by a hashed value",
		"required" : "0",
		"default": "@FENCETMPDIR@/fence_ibm_vpc/[hash].token",
		"shortdesc" : "Path to the token cache file",
		"order" : 0
	}


def main():
	device_opt = [
		"apikey",
		"region",
		"proxy",
		"limit",
		"token_file",
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
	docs["longdesc"] = """fence_ibm_vpc is a Power Fencing agent which can be \
used with IBM Cloud VPC to fence virtual machines."""
	docs["vendorurl"] = "https://www.ibm.com"
	show_docs(options, docs)

	####
	## Fence operations
	####
	run_delay(options)

	if options["--apikey"][0] == '@':
		key_file = options["--apikey"][1:]
		try:
			# read the API key from a file
			with open(key_file, "r") as f:
				try:
					keys = json.loads(f.read())
					# data seems to be in json format
					# return the value of the item with the key 'Apikey'
					options["--apikey"] = keys.get("Apikey", "")
					if not options["--apikey"]:
						# backward compatibility: former key name was 'apikey'
						options["--apikey"] = keys.get("apikey", "")
				# data is text, return as is
				except ValueError:
					f.seek(0)
					options["--apikey"] = f.read().strip()
		except FileNotFoundError:
			logging.error("Failed: Cannot open file {}".format(key_file))
			sys.exit(EC_BAD_ARGS)

	conn = connect(options)
	atexit.register(disconnect, conn)

	result = fence_action(conn, options, set_power_status, get_power_status, get_list)

	sys.exit(result)

if __name__ == "__main__":
	main()
