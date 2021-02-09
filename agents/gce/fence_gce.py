#!@PYTHON@ -tt

#
# Requires the googleapiclient and oauth2client
# RHEL 7.x: google-api-python-client==1.6.7 python-gflags==2.0 pyasn1==0.4.8 rsa==3.4.2
# RHEL 8.x: nothing additional needed
# SLES 12.x: python-google-api-python-client python-oauth2client python-oauth2client-gce
# SLES 15.x: python3-google-api-python-client python3-oauth2client
#

import atexit
import httplib2
import logging
import json
import re
import os
import socket
import sys
import time

if sys.version_info >= (3, 0):
  # Python 3 imports.
  import urllib.parse as urlparse
  import urllib.request as urlrequest
else:
  # Python 2 imports.
  import urllib as urlparse
  import urllib2 as urlrequest
sys.path.append("@FENCEAGENTSLIBDIR@")

from fencing import fail_usage, run_delay, all_opt, atexit_handler, check_input, process_input, show_docs, fence_action
try:
  import googleapiclient.discovery
  from oauth2client.client import GoogleCredentials
  from oauth2client.service_account import ServiceAccountCredentials
  import socks
except:
  pass

METADATA_SERVER = 'http://metadata.google.internal/computeMetadata/v1/'
METADATA_HEADERS = {'Metadata-Flavor': 'Google'}

#
# Will use baremetalsolution setting or the environment variable
# FENCE_GCE_URI_REPLACEMENTS to replace the uri for calls to *.googleapis.com.
#
def replace_api_uri(options, http_request):
	uri_replacements = []
	# put any env var replacements first, then baremetalsolution if in options
	if "FENCE_GCE_URI_REPLACEMENTS" in os.environ:
		logging.debug("FENCE_GCE_URI_REPLACEMENTS environment variable exists")
		env_uri_replacements = os.environ["FENCE_GCE_URI_REPLACEMENTS"]
		try:
			uri_replacements_json = json.loads(env_uri_replacements)
			if isinstance(uri_replacements_json, list):
				uri_replacements = uri_replacements_json
			else:
				logging.warning("FENCE_GCE_URI_REPLACEMENTS exists, but is not a JSON List")
		except ValueError as e:
			logging.warning("FENCE_GCE_URI_REPLACEMENTS exists but is not valid JSON")
	if "--baremetalsolution" in options:
		uri_replacements.append(
			{
				"matchlength": 4,
				"match": "https://compute.googleapis.com/compute/v1/projects/(.*)/zones/(.*)/instances/(.*)/reset(.*)",
				"replace": "https://baremetalsolution.googleapis.com/v1alpha1/projects/\\1/locations/\\2/instances/\\3:resetInstance\\4"
			})
	for uri_replacement in uri_replacements:
		# each uri_replacement should have matchlength, match, and replace
		if "matchlength" not in uri_replacement or "match" not in uri_replacement or "replace" not in uri_replacement:
			logging.warning("FENCE_GCE_URI_REPLACEMENTS missing matchlength, match, or replace in %s" % uri_replacement)
			continue
		match = re.match(uri_replacement["match"], http_request.uri)
		if match is None or len(match.groups()) != uri_replacement["matchlength"]:
			continue
		replaced_uri = re.sub(uri_replacement["match"], uri_replacement["replace"], http_request.uri)
		match = re.match("https:\/\/.*.googleapis.com", replaced_uri)
		if match is None or match.start() != 0:
			logging.warning("FENCE_GCE_URI_REPLACEMENTS replace is not "
				"targeting googleapis.com, ignoring it: %s" % replaced_uri)
			continue
		logging.debug("Replacing googleapis uri %s with %s" % (http_request.uri, replaced_uri))
		http_request.uri = replaced_uri
		break
	return http_request

def retry_api_execute(options, http_request):
	replaced_http_request = replace_api_uri(options, http_request)
	retries = 3
	if options.get("--retries"):
		retries = int(options.get("--retries"))
	retry_sleep = 5
	if options.get("--retrysleep"):
		retry_sleep = int(options.get("--retrysleep"))
	retry = 0
	current_err = None
	while retry <= retries:
		if retry > 0:
			time.sleep(retry_sleep)
		try:
			return replaced_http_request.execute()
		except Exception as err:
			current_err = err
			logging.warning("Could not execute api call to: %s, retry: %s, "
				"err: %s" % (replaced_http_request.uri, retry, str(err)))
		retry += 1
	raise current_err


def translate_status(instance_status):
	"Returns on | off | unknown."
	if instance_status == "RUNNING":
		return "on"
	elif instance_status == "TERMINATED":
		return "off"
	return "unknown"


def get_nodes_list(conn, options):
	result = {}
	try:
		instanceList = retry_api_execute(options, conn.instances().list(
			project=options["--project"],
			zone=options["--zone"]))
		for instance in instanceList["items"]:
			result[instance["id"]] = (instance["name"], translate_status(instance["status"]))
	except Exception as err:
		fail_usage("Failed: get_nodes_list: {}".format(str(err)))

	return result


def get_power_status(conn, options):
	logging.debug("get_power_status")
	# if this is bare metal we need to just send back the opposite of the
	# requested action: if on send off, if off send on
	if "--baremetalsolution" in options:
		if options.get("--action") == "on":
			return "off"
		else:
			return "on"
	try:
		instance = retry_api_execute(options, conn.instances().get(
				project=options["--project"],
				zone=options["--zone"],
				instance=options["--plug"]))
		return translate_status(instance["status"])
	except Exception as err:
		fail_usage("Failed: get_power_status: {}".format(str(err)))


def wait_for_operation(conn, options, operation):
	if 'name' not in operation:
		logging.warning('Cannot wait for operation to complete, the'
		' requested operation will continue asynchronously')
		return
	project = options["--project"]
	zone = options["--zone"]
	while True:
		result = retry_api_execute(options, conn.zoneOperations().get(
			project=project,
			zone=zone,
			operation=operation['name']))
		if result['status'] == 'DONE':
			if 'error' in result:
				raise Exception(result['error'])
			return
		time.sleep(1)


def set_power_status(conn, options):
	logging.debug("set_power_status");
	try:
		if options["--action"] == "off":
			logging.info("Issuing poweroff of %s in zone %s" % (options["--plug"], options["--zone"]))
			operation = retry_api_execute(options, conn.instances().stop(
					project=options["--project"],
					zone=options["--zone"],
					instance=options["--plug"]))
			logging.info("Poweroff command completed, waiting for the operation to complete")
			wait_for_operation(conn, options, operation)
			logging.info("Poweroff of %s in zone %s complete" % (options["--plug"], options["--zone"]))
		elif options["--action"] == "on":
			logging.info("Issuing poweron of %s in zone %s" % (options["--plug"], options["--zone"]))
			operation = retry_api_execute(options, conn.instances().start(
					project=options["--project"],
					zone=options["--zone"],
					instance=options["--plug"]))
			wait_for_operation(conn, options, operation)
			logging.info("Poweron of %s in zone %s complete" % (options["--plug"], options["--zone"]))
	except Exception as err:
		fail_usage("Failed: set_power_status: {}".format(str(err)))


def power_cycle(conn, options):
	logging.debug("power_cycle");
	try:
		logging.info('Issuing reset of %s in zone %s' % (options["--plug"], options["--zone"]))
		operation = retry_api_execute(options, conn.instances().reset(
				project=options["--project"],
				zone=options["--zone"],
				instance=options["--plug"]))
		logging.info("Reset command completed, waiting for the operation to complete")
		wait_for_operation(conn, options, operation)
		logging.info('Reset of %s in zone %s complete' % (options["--plug"], options["--zone"]))
		return True
	except Exception as err:
		logging.error("Failed: power_cycle: {}".format(str(err)))
		return False


def get_zone(conn, options):
	logging.debug("get_zone");
	project = options['--project']
	instance = options['--plug']
	fl = 'name="%s"' % instance
	request = replace_api_uri(options, conn.instances().aggregatedList(project=project, filter=fl))
	while request is not None:
		response = request.execute()
		zones = response.get('items', {})
		for zone in zones.values():
			for inst in zone.get('instances', []):
				if inst['name'] == instance:
					return inst['zone'].split("/")[-1]
		request = replace_api_uri(options, conn.instances().aggregatedList_next(
				previous_request=request, previous_response=response))
	raise Exception("Unable to find instance %s" % (instance))


def get_metadata(metadata_key, params=None, timeout=None):
	"""Performs a GET request with the metadata headers.

	Args:
		metadata_key: string, the metadata to perform a GET request on.
		params: dictionary, the query parameters in the GET request.
		timeout: int, timeout in seconds for metadata requests.

	Returns:
		HTTP response from the GET request.

	Raises:
		urlerror.HTTPError: raises when the GET request fails.
	"""
	logging.debug("get_metadata");
	timeout = timeout or 60
	metadata_url = os.path.join(METADATA_SERVER, metadata_key)
	params = urlparse.urlencode(params or {})
	url = '%s?%s' % (metadata_url, params)
	request = urlrequest.Request(url, headers=METADATA_HEADERS)
	request_opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
	return request_opener.open(request, timeout=timeout * 1.1).read().decode("utf-8")


def define_new_opts():
	all_opt["zone"] = {
		"getopt" : ":",
		"longopt" : "zone",
		"help" : "--zone=[name]                  Zone, e.g. us-central1-b",
		"shortdesc" : "Zone.",
		"required" : "0",
		"order" : 2
	}
	all_opt["project"] = {
		"getopt" : ":",
		"longopt" : "project",
		"help" : "--project=[name]               Project ID",
		"shortdesc" : "Project ID.",
		"required" : "0",
		"order" : 3
	}
	all_opt["stackdriver-logging"] = {
		"getopt" : "",
		"longopt" : "stackdriver-logging",
		"help" : "--stackdriver-logging          Enable Logging to Stackdriver",
		"shortdesc" : "Stackdriver-logging support.",
		"longdesc" : "If enabled IP failover logs will be posted to stackdriver logging.",
		"required" : "0",
		"order" : 4
	}
	all_opt["baremetalsolution"] = {
		"getopt" : "",
		"longopt" : "baremetalsolution",
		"help" : "--baremetalsolution            Enable on bare metal",
		"shortdesc" : "If enabled this is a bare metal offering from google.",
		"required" : "0",
		"order" : 5
	}
	all_opt["apitimeout"] = {
		"getopt" : ":",
		"type" : "second",
		"longopt" : "apitimeout",
		"help" : "--apitimeout=[seconds]         Timeout to use for API calls",
		"shortdesc" : "Timeout in seconds to use for API calls, default is 60.",
		"required" : "0",
		"default" : 60,
		"order" : 6
	}
	all_opt["retries"] = {
		"getopt" : ":",
		"type" : "integer",
		"longopt" : "retries",
		"help" : "--retries=[retries]            Number of retries on failure for API calls",
		"shortdesc" : "Number of retries on failure for API calls, default is 3.",
		"required" : "0",
		"default" : 3,
		"order" : 7
	}
	all_opt["retrysleep"] = {
		"getopt" : ":",
		"type" : "second",
		"longopt" : "retrysleep",
		"help" : "--retrysleep=[seconds]         Time to sleep between API retries",
		"shortdesc" : "Time to sleep in seconds between API retries, default is 5.",
		"required" : "0",
		"default" : 5,
		"order" : 8
	}
	all_opt["serviceaccount"] = {
		"getopt" : ":",
		"longopt" : "serviceaccount",
		"help" : "--serviceaccount=[filename]    Service account json file location e.g. serviceaccount=/somedir/service_account.json",
		"shortdesc" : "Service Account to use for authentication to the google cloud APIs.",
		"required" : "0",
		"order" : 9
	}
	all_opt["proxyhost"] = {
		"getopt" : ":",
		"longopt" : "proxyhost",
		"help" : "--proxyhost=[proxy_host]       The proxy host to use, if one is needed to access the internet (Example: 10.122.0.33)",
		"shortdesc" : "If a proxy is used for internet access, the proxy host should be specified.",
		"required" : "0",
		"order" : 10
	}
	all_opt["proxyport"] = {
		"getopt" : ":",
		"type" : "integer",
		"longopt" : "proxyport",
		"help" : "--proxyport=[proxy_port]       The proxy port to use, if one is needed to access the internet (Example: 3127)",
		"shortdesc" : "If a proxy is used for internet access, the proxy port should be specified.",
		"required" : "0",
		"order" : 11
	}


def main():
	conn = None

	device_opt = ["port", "no_password", "zone", "project", "stackdriver-logging",
		"method", "baremetalsolution", "apitimeout", "retries", "retrysleep",
		"serviceaccount", "proxyhost", "proxyport"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["power_timeout"]["default"] = "60"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for GCE (Google Cloud Engine)"
	docs["longdesc"] = "fence_gce is an I/O Fencing agent for GCE (Google Cloud " \
			   "Engine). It uses the googleapiclient library to connect to GCE.\n" \
			   "googleapiclient can be configured with Google SDK CLI or by " \
			   "executing 'gcloud auth application-default login'.\n" \
			   "For instructions see: https://cloud.google.com/compute/docs/tutorials/python-guide"
	docs["vendorurl"] = "http://cloud.google.com"
	show_docs(options, docs)

	run_delay(options)

	# Prepare logging
	if options.get('--verbose') is None:
		logging.getLogger('googleapiclient').setLevel(logging.ERROR)
		logging.getLogger('oauth2client').setLevel(logging.ERROR)
	if options.get('--stackdriver-logging') is not None and options.get('--plug'):
		try:
			import google.cloud.logging.handlers
			client = google.cloud.logging.Client()
			handler = google.cloud.logging.handlers.CloudLoggingHandler(client, name=options['--plug'])
			handler.setLevel(logging.INFO)
			formatter = logging.Formatter('gcp:stonith "%(message)s"')
			handler.setFormatter(formatter)
			root_logger = logging.getLogger()
			if options.get('--verbose') is None:
				root_logger.setLevel(logging.INFO)
			root_logger.addHandler(handler)
		except ImportError:
			logging.error('Couldn\'t import google.cloud.logging, '
				'disabling Stackdriver-logging support')

  # if apitimeout is defined we set the socket timeout, if not we keep the
  # socket default which is 60s
	if options.get("--apitimeout"):
		socket.setdefaulttimeout(options["--apitimeout"])

	# Prepare cli
	try:
		if options.get("--serviceaccount"):
			scope = ['https://www.googleapis.com/auth/cloud-platform']
			credentials = ServiceAccountCredentials.from_json_keyfile_name(options.get("--serviceaccount"), scope)
			logging.debug("using credentials from service account")
		else:
			credentials = GoogleCredentials.get_application_default()
			logging.debug("using application default credentials")

		if options.get("--proxyhost") and options.get("--proxyport"):
			proxy_info = httplib2.ProxyInfo(
				proxy_type=socks.PROXY_TYPE_HTTP,
				proxy_host=options.get("--proxyhost"),
				proxy_port=int(options.get("--proxyport")))
			http = credentials.authorize(httplib2.Http(proxy_info=proxy_info))
			conn = googleapiclient.discovery.build(
				'compute', 'v1', http=http, cache_discovery=False)
		else:
			conn = googleapiclient.discovery.build(
				'compute', 'v1', credentials=credentials, cache_discovery=False)
	except Exception as err:
		fail_usage("Failed: Create GCE compute v1 connection: {}".format(str(err)))

	# Get project and zone
	if not options.get("--project"):
		try:
			options["--project"] = get_metadata('project/project-id')
		except Exception as err:
			fail_usage("Failed retrieving GCE project. Please provide --project option: {}".format(str(err)))

	if "--baremetalsolution" in options:
		options["--zone"] = "none"
	if not options.get("--zone"):
		try:
			options["--zone"] = get_zone(conn, options)
		except Exception as err:
			fail_usage("Failed retrieving GCE zone. Please provide --zone option: {}".format(str(err)))

	# Operate the fencing device
	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list, power_cycle)
	sys.exit(result)

if __name__ == "__main__":
	main()
