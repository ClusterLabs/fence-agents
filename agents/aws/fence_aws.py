#!@PYTHON@ -tt

import sys, re
import logging
import atexit
import requests
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, run_delay, EC_STATUS, SyslogLibHandler

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, NoRegionError

logger = logging.getLogger("fence_aws")
logger.propagate = False
logger.setLevel(logging.INFO)
logger.addHandler(SyslogLibHandler())
logging.getLogger('botocore.vendored').propagate = False
	
def get_instance_id():
	try:
		r = requests.get('http://169.254.169.254/latest/meta-data/instance-id')
		return r.content
	except HTTPError as http_err:
		logger.error('HTTP error occurred while trying to access EC2 metadata server: %s', http_err)
	except Exception as err:
		logger.error('A fatal error occurred while trying to access EC2 metadata server: %s', err)
	return None
	

def get_nodes_list(conn, options):
	logger.info("Starting monitor operation")
	result = {}
	try:
		for instance in conn.instances.all():
			result[instance.id] = ("", None)
	except ClientError:
		fail_usage("Failed: Incorrect Access Key or Secret Key.")
	except EndpointConnectionError:
		fail_usage("Failed: Incorrect Region.")
	except Exception as e:
		logger.error("Failed to get node list: %s", e)
	logger.debug("Monitor operation OK: %s",result)
	return result

def get_power_status(conn, options):
	logger.debug("Starting status operation")
	try:
		instance = conn.instances.filter(Filters=[{"Name": "instance-id", "Values": [options["--plug"]]}])
		state = list(instance)[0].state["Name"]
		logger.info("Status operation for EC2 instance %s returned state: %s",options["--plug"],state.upper())
		if state == "running":
			return "on"
		elif state == "stopped":
			return "off"
		else:
			return "unknown"

	except ClientError:
		fail_usage("Failed: Incorrect Access Key or Secret Key.")
	except EndpointConnectionError:
		fail_usage("Failed: Incorrect Region.")
	except IndexError:
		fail(EC_STATUS)
	except Exception as e:
		logging.error("Failed to get power status: %s", e)
		fail(EC_STATUS)

def get_self_power_status(conn, instance_id):
	try:
		instance = conn.instances.filter(Filters=[{"Name": "instance-id", "Values": [instance_id]}])
		state = list(instance)[0].state["Name"]
		if state == "running":
			logging.debug("Captured my (%s) state and it %s - returning OK - Proceeding with fencing",instance_id,state.upper())
			return "ok"
		else:
			logging.debug("Captured my (%s) state it is %s - returning Alert - Unable to fence other nodes",instance_id,state.upper())
			return "alert"
	
	except ClientError:
		fail_usage("Failed: Incorrect Access Key or Secret Key.")
	except EndpointConnectionError:
		fail_usage("Failed: Incorrect Region.")
	except IndexError:
		return "fail"

def set_power_status(conn, options):
	my_instance = get_instance_id()
	try:
		if (options["--action"]=="off"):
			if (get_self_power_status(conn,my_instance) == "ok"):
				conn.instances.filter(InstanceIds=[options["--plug"]]).stop(Force=True)
				logger.info("Called StopInstance API call for %s", options["--plug"])
			else:
				logger.info("Skipping fencing as instance is not in running status")
		elif (options["--action"]=="on"):
			conn.instances.filter(InstanceIds=[options["--plug"]]).start()
	except Exception as e:
		logger.error("Failed to power %s %s: %s", \
				options["--action"], options["--plug"], e)

def define_new_opts():
	all_opt["region"] = {
		"getopt" : "r:",
		"longopt" : "region",
		"help" : "-r, --region=[region]           Region, e.g. us-east-1",
		"shortdesc" : "Region.",
		"required" : "0",
		"order" : 2
	}
	all_opt["access_key"] = {
		"getopt" : "a:",
		"longopt" : "access-key",
		"help" : "-a, --access-key=[key]         Access Key",
		"shortdesc" : "Access Key.",
		"required" : "0",
		"order" : 3
	}
	all_opt["secret_key"] = {
		"getopt" : "s:",
		"longopt" : "secret-key",
		"help" : "-s, --secret-key=[key]         Secret Key",
		"shortdesc" : "Secret Key.",
		"required" : "0",
		"order" : 4
	}
	all_opt["boto3_debug"] = {
		"getopt" : "b:",
		"longopt" : "boto3_debug",
		"help" : "-b, --boto3_debug=[option]      Boto3 and Botocore library debug logging",
		"shortdesc": "Boto Lib debug",
		"required": "0",
		"order": 5
	}

# Main agent method
def main():
	conn = None

	device_opt = ["port", "no_password", "region", "access_key", "secret_key", "boto3_debug"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["power_timeout"]["default"] = "60"
	all_opt["boto3_debug"]["default"] = "off"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for AWS (Amazon Web Services)"
	docs["longdesc"] = "fence_aws is an I/O Fencing agent for AWS (Amazon Web\
Services). It uses the boto3 library to connect to AWS.\
\n.P\n\
boto3 can be configured with AWS CLI or by creating ~/.aws/credentials.\n\
For instructions see: https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration"
	docs["vendorurl"] = "http://www.amazon.com"
	show_docs(options, docs)

	run_delay(options)

	if options.get("--verbose") is not None:
		lh = logging.FileHandler('/var/log/fence_aws_debug.log')
		logger.addHandler(lh)
		lhf = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		lh.setFormatter(lhf)
		logger.setLevel(logging.DEBUG)
	
	if options["--boto3_debug"] != "on":
		boto3.set_stream_logger('boto3',logging.INFO)
		boto3.set_stream_logger('botocore',logging.INFO)
		logging.getLogger('botocore').propagate = False
		logging.getLogger('boto3').propagate = False
	else:
		log_format = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
		logging.getLogger('botocore').propagate = False
		logging.getLogger('boto3').propagate = False
		fdh = logging.FileHandler('/var/log/fence_aws_boto3.log')
		fdh.setFormatter(log_format)
		logging.getLogger('boto3').addHandler(fdh)
		logging.getLogger('botocore').addHandler(fdh)
		logging.debug("Boto debug level is %s and sending debug info to /var/log/fence_aws_boto3.log", options["--boto3_debug"])

	region = options.get("--region")
	access_key = options.get("--access-key")
	secret_key = options.get("--secret-key")
	try:
		conn = boto3.resource('ec2', region_name=region,
				      aws_access_key_id=access_key,
				      aws_secret_access_key=secret_key)
	except Exception as e:
		fail_usage("Failed: Unable to connect to AWS: " + str(e))

	# Operate the fencing device
	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
	sys.exit(result)

if __name__ == "__main__":

	main()
