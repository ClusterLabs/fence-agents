#!@PYTHON@ -tt

import sys, re
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, NoRegionError

def get_nodes_list(conn, options):
	result = {}
	try:
		for instance in conn.instances.all():
			result[instance.id] = ("", None)
	except ClientError:
		fail_usage("Failed: Incorrect Access Key or Secret Key.")
	except EndpointConnectionError:
		fail_usage("Failed: Incorrect Region.")

	return result

def get_power_status(conn, options):
	try:
		instance = conn.instances.filter(Filters=[{"Name": "instance-id", "Values": [options["--plug"]]}])
		state = list(instance)[0].state["Name"]
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
		return "fail"

def set_power_status(conn, options):
	if (options["--action"]=="off"):
		conn.instances.filter(InstanceIds=[options["--plug"]]).stop(Force=True)
	elif (options["--action"]=="on"):
		conn.instances.filter(InstanceIds=[options["--plug"]]).start()


def define_new_opts():
	all_opt["region"] = {
		"getopt" : "r:",
		"longopt" : "region",
		"help" : "-r, --region=[name]            Region, e.g. us-east-1",
		"shortdesc" : "Region.",
		"required" : "0",
		"order" : 2
	}
	all_opt["access_key"] = {
		"getopt" : "a:",
		"longopt" : "access-key",
		"help" : "-a, --access-key=[name]         Access Key",
		"shortdesc" : "Access Key.",
		"required" : "0",
		"order" : 3
	}
	all_opt["secret_key"] = {
		"getopt" : "s:",
		"longopt" : "secret-key",
		"help" : "-s, --secret-key=[name]         Secret Key",
		"shortdesc" : "Secret Key.",
		"required" : "0",
		"order" : 4
	}

# Main agent method
def main():
	conn = None

	device_opt = ["port", "no_password", "region", "access_key", "secret_key"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["power_timeout"]["default"] = "60"

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

	if "--region" in options and "--access-key" in options and "--secret-key" in options:  
		region = options["--region"]
		access_key = options["--access-key"]
		secret_key = options["--secret-key"]
		try:
			conn = boto3.resource('ec2', region_name=region,
					      aws_access_key_id=access_key,
					      aws_secret_access_key=secret_key)
		except:
			fail_usage("Failed: Unable to connect to AWS. Check your configuration.")
	else:
		# If setup with "aws configure" or manually in
		# ~/.aws/credentials
		try:
			conn = boto3.resource('ec2')
		except:
			# If any of region/access/secret are missing
			fail_usage("Failed: Unable to connect to AWS. Check your configuration.")

	# Operate the fencing device
	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
	sys.exit(result)

if __name__ == "__main__":
	main()
