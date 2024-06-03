#!@PYTHON@ -tt

import atexit
import sys
import io
import logging
import pycurl
import json

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail_usage, all_opt, fence_action, atexit_handler, check_input, process_input, show_docs, run_delay

def get_power_status(conn, options):
	del conn
	status = send_cmd(options, "containers/%s/json" % options["--plug"])
	if status is None:
		return None
	return "on" if status["State"]["Running"] else "off"


def set_power_status(conn, options):
	del conn
	if options["--action"] == "on":
		send_cmd(options, "containers/%s/start" % options["--plug"], True)
	else:
		send_cmd(options, "containers/%s/kill" % options["--plug"], True)
	return


def reboot_cycle(conn, options):
	del conn
	send_cmd(options, "containers/%s/restart" % options["--plug"], True)
	return get_power_status(conn, options)


def get_list(conn, options):
	del conn
	output = send_cmd(options, "containers/json?all=1")
	containers = {}
	for container in output:
		containers[container["Id"]] = ({True:container["Names"][0][1:], False: container["Names"][0]}[container["Names"][0][0:1] == '/'], {True:"off", False: "on"}[container["Status"][:4].lower() == "exit"])
	return containers


def send_cmd(options, cmd, post = False):
	url = "http%s://%s:%s/v%s/%s" % ("s" if "--ssl-secure" in options or "--ssl-insecure" in options else "", options["--ip"], options["--ipport"], options["--api-version"], cmd)
	conn = pycurl.Curl()
	output_buffer = io.BytesIO()
	if logging.getLogger().getEffectiveLevel() < logging.WARNING:
		conn.setopt(pycurl.VERBOSE, True)
	if "--unix-socket" in options:
		conn.setopt(pycurl.UNIX_SOCKET_PATH, options["--unix-socket"])
	conn.setopt(pycurl.HTTPGET, 1)
	conn.setopt(pycurl.URL, url.encode("ascii"))
	if post:
		conn.setopt(pycurl.POST, 1)
		conn.setopt(pycurl.POSTFIELDSIZE, 0)
	conn.setopt(pycurl.WRITEFUNCTION, output_buffer.write)
	conn.setopt(pycurl.TIMEOUT, int(options["--shell-timeout"]))

	if "--ssl-secure" in options:
		if not (set(("--tlscert", "--tlskey", "--tlscacert")) <= set(options)):
			fail_usage("Failed. If --ssl option is used, You have to also \
specify: --tlscert, --tlskey and --tlscacert")
		conn.setopt(pycurl.SSL_VERIFYPEER, 1)
		conn.setopt(pycurl.SSLCERT, options["--tlscert"])
		conn.setopt(pycurl.SSLKEY, options["--tlskey"])
		conn.setopt(pycurl.CAINFO, options["--tlscacert"])
	elif "--ssl-insecure" in options:
		conn.setopt(pycurl.SSL_VERIFYPEER, 0)
		conn.setopt(pycurl.SSL_VERIFYHOST, 0)

	logging.debug("URL: " + url)

	try:
		conn.perform()
		result = output_buffer.getvalue().decode()
		return_code = conn.getinfo(pycurl.RESPONSE_CODE)

		logging.debug("RESULT [" + str(return_code) + \
			"]: " + result)
		conn.close()
		if return_code == 200:
			return json.loads(result)
	except pycurl.error:
		logging.error("Connection failed")
	except:
		if result is not None:
			logging.error(result)
		logging.error("Cannot parse json")
	return None


def main():
	atexit.register(atexit_handler)

	all_opt["tlscert"] = {
		"getopt" : ":",
		"longopt" : "tlscert",
		"help" : "--tlscert                      "
			"Path to client certificate for TLS authentication",
		"required" : "0",
		"shortdesc" : "Path to client certificate (PEM format) \
for TLS authentication. Required if --ssl option is used.",
		"order": 2
	}

	all_opt["tlskey"] = {
		"getopt" : ":",
		"longopt" : "tlskey",
		"help" : "--tlskey                       "
			"Path to client key for TLS authentication",
		"required" : "0",
		"shortdesc" : "Path to client key (PEM format) for TLS \
authentication.  Required if --ssl option is used.",
		"order": 2
	}

	all_opt["tlscacert"] = {
		"getopt" : ":",
		"longopt" : "tlscacert",
		"help" : "--tlscacert                    "
			"Path to CA certificate for TLS authentication",
		"required" : "0",
		"shortdesc" : "Path to CA certificate (PEM format) for \
TLS authentication.  Required if --ssl option is used.",
		"order": 2
	}

	all_opt["api_version"] = {
		"getopt" : ":",
		"longopt" : "api-version",
		"help" : "--api-version                  "
			"Version of Docker Remote API (default: 1.11)",
		"required" : "0",
		"order" : 2,
		"default" : "1.11",
	}

	all_opt["unix_socket"] = {
		"getopt" : ":",
		"longopt" : "unix-socket",
		"help" : "--unix-socket                  "
			"Path to Docker's unix socket. Use this with --disable-ssl.",
		"required" : "0",
		"order" : 2,
	}

	all_opt["disable_ssl"] = {
		"getopt" : "",
		"longopt" : "disable-ssl",
		"help" : "--disable-ssl                  Don't use SSL connection",
		"required" : "0",
		"shortdesc" : "Don't use SSL",
		"order": 2,
	}

	device_opt = ["ipaddr", "no_password", "no_login", "port", "method", "web",
		"tlscert", "tlskey", "tlscacert", "ssl", "api_version", "unix_socket",
		"disable_ssl"]
	all_opt["ssl"]["default"] = "1"
	options = check_input(device_opt, process_input(device_opt))

	if "--disable-ssl" in options or options["--ssl"] == "0":
		for k in ["--ssl", "--ssl-secure", "--ssl-insecure"]:
			if k in options:
				del options[k]

	docs = { }
	docs["shortdesc"] = "Fence agent for Docker"
	docs["longdesc"] = "fence_docker is a Power Fencing agent which \
can be used with the Docker Engine containers. You can use this \
fence-agent without any authentication, or you can use TLS authentication \
(use --ssl option, more info about TLS authentication in docker: \
http://docs.docker.com/examples/https/)."
	docs["vendorurl"] = "www.docker.io"
	show_docs(options, docs)

	run_delay(options)

	result = fence_action(None, options, set_power_status, get_power_status, get_list, reboot_cycle)

	sys.exit(result)

if __name__ == "__main__":
	main()
