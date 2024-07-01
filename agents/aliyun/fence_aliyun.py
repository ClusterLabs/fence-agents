#!@PYTHON@ -tt

import sys
import logging
import atexit
import json

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, run_delay


try:
	from aliyunsdkcore import client
	from aliyunsdkcore.auth.credentials import EcsRamRoleCredential
	from aliyunsdkcore.profile import region_provider
except ImportError as e:
	logging.warning("The 'aliyunsdkcore' module has been not installed or is unavailable, try to execute the command 'pip install aliyun-python-sdk-core --upgrade' to solve. error: %s" % e)


try:
	from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest
	from aliyunsdkecs.request.v20140526.StartInstanceRequest import StartInstanceRequest
	from aliyunsdkecs.request.v20140526.StopInstanceRequest import StopInstanceRequest
	from aliyunsdkecs.request.v20140526.RebootInstanceRequest import RebootInstanceRequest
except ImportError as e:
	logging.warning("The 'aliyunsdkecs' module has been not installed or is unavailable, try to execute the command 'pip install aliyun-python-sdk-ecs --upgrade' to solve. error: %s" % e)


def _send_request(conn, request):
	logging.debug("send request action: %s" % request.get_action_name())
	request.set_accept_format('json')
	try:
		response_str = conn.do_action_with_exception(request)
	except Exception as e:
		fail_usage("Failed: send request failed: Error: %s" % e)

	response_detail = json.loads(response_str)
	logging.debug("reponse: %s" % response_detail)
	return response_detail

def start_instance(conn, instance_id):
	logging.debug("start instance %s" % instance_id)
	request = StartInstanceRequest()
	request.set_InstanceId(instance_id)
	_send_request(conn, request)

def stop_instance(conn, instance_id):
	logging.debug("stop instance %s" % instance_id)
	request = StopInstanceRequest()
	request.set_InstanceId(instance_id)
	request.set_ForceStop('true')
	_send_request(conn, request)

def reboot_instance(conn, instance_id):
	logging.debug("reboot instance %s" % instance_id)
	request = RebootInstanceRequest()
	request.set_InstanceId(instance_id)
	request.set_ForceStop('true')
	_send_request(conn, request)

def get_status(conn, instance_id):
	logging.debug("get instance %s status" % instance_id)
	request = DescribeInstancesRequest()
	request.set_InstanceIds(json.dumps([instance_id]))
	response = _send_request(conn, request)
	instance_status = None
	if response is not None:
		instance_list = response.get('Instances').get('Instance')
		for item in instance_list:
			instance_status = item.get('Status')
	return instance_status

def get_nodes_list(conn, options):
	logging.debug("start to get nodes list")
	result = {}
	request = DescribeInstancesRequest()
	request.set_PageSize(100)

	if "--filter" in options:
		filter_key = options["--filter"].split("=")[0].strip()
		filter_value = options["--filter"].split("=")[1].strip()
		params = request.get_query_params()
		params[filter_key] = filter_value
		request.set_query_params(params)

	response = _send_request(conn, request)
	if response is not None:
		instance_list = response.get('Instances').get('Instance')
		for item in instance_list:
			instance_id = item.get('InstanceId')
			instance_name = item.get('InstanceName')
			result[instance_id] = (instance_name, None)
	logging.debug("get nodes list: %s" % result)
	return result

def get_power_status(conn, options):
	logging.debug("start to get power(%s) status" % options["--plug"])
	state = get_status(conn, options["--plug"])

	if state == "Running":
		status = "on"
	elif state == "Stopped":
		status = "off"
	else:
		status = "unknown"
	logging.debug("the power(%s) status is %s" % (options["--plug"], status))
	return status

def set_power_status(conn, options):
	logging.info("start to set power(%s) status to %s" % (options["--plug"], options["--action"]))

	if (options["--action"]=="off"):
		stop_instance(conn, options["--plug"])
	elif (options["--action"]=="on"):
		start_instance(conn, options["--plug"])
	elif (options["--action"]=="reboot"):
		reboot_instance(conn, options["--plug"])

def define_new_opts():
	all_opt["region"] = {
		"getopt" : "r:",
		"longopt" : "region",
		"help" : "-r, --region=[name]            Region, e.g. cn-hangzhou",
		"shortdesc" : "Region.",
		"required" : "0",
		"order" : 2
	}
	all_opt["access_key"] = {
		"getopt" : "a:",
		"longopt" : "access-key",
		"help" : "-a, --access-key=[name]        Access Key",
		"shortdesc" : "Access Key.",
		"required" : "0",
		"order" : 3
	}
	all_opt["secret_key"] = {
		"getopt" : "s:",
		"longopt" : "secret-key",
		"help" : "-s, --secret-key=[name]        Secret Key",
		"shortdesc" : "Secret Key.",
		"required" : "0",
		"order" : 4
	}
	all_opt["ram_role"] = {
		"getopt": ":",
		"longopt": "ram-role",
		"help": "--ram-role=[name]              Ram Role",
		"shortdesc": "Ram Role.",
		"required": "0",
		"order": 5
	}
	all_opt["credentials_file"] = {
		"getopt": ":",
		"longopt": "credentials-file",
		"help": "--credentials-file=[path]            Path to aliyun-cli credentials file",
		"shortdesc": "Path to credentials file",
		"required": "0",
		"order": 6
	}
	all_opt["credentials_file_profile"] = {
		"getopt": ":",
		"longopt": "credentials-file-profile",
		"help": "--credentials-file-profile=[profile] Credentials file profile",
		"shortdesc": "Credentials file profile",
		"required": "0",
		"default": "default",
		"order": 7
	}
	all_opt["filter"] = {
		"getopt": ":",
		"longopt": "filter",
		"help": "--filter=[key=value]           Filter (e.g. InstanceIds=[\"i-XXYYZZAA1\",\"i-XXYYZZAA2\"]",
		"shortdesc": "Filter for list-action.",
		"required": "0",
		"order": 8
	}

# Main agent method
def main():
	conn = None

	device_opt = ["port", "no_password", "region", "access_key", "secret_key", "ram_role", "credentials_file", "credentials_file_profile", "filter"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["power_timeout"]["default"] = "60"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for Aliyun (Aliyun Web Services)"
	docs["longdesc"] = "fence_aliyun is a Power Fencing agent for Aliyun."
	docs["vendorurl"] = "http://www.aliyun.com"
	show_docs(options, docs)

	run_delay(options)

	if "--region" in options:
		region = options["--region"]
		if "--access-key" in options and "--secret-key" in options:
			access_key = options["--access-key"]
			secret_key = options["--secret-key"]
			conn = client.AcsClient(access_key, secret_key, region)
		elif "--ram-role" in options:
			ram_role = options["--ram-role"]
			role = EcsRamRoleCredential(ram_role)
			conn = client.AcsClient(region_id=region, credential=role)
		elif "--credentials-file" in options and "--credentials-file-profile" in options:
			import os, configparser
			try:
				config = configparser.ConfigParser()
				config.read(os.path.expanduser(options["--credentials-file"]))
				access_key = config.get(options["--credentials-file-profile"], "aliyun_access_key_id")
				secret_key = config.get(options["--credentials-file-profile"], "aliyun_access_key_secret")
				conn = client.AcsClient(access_key, secret_key, region)
			except Exception as e:
				fail_usage("Failed: failed to read credentials file: %s" % e)
		else:
			fail_usage("Failed: User credentials are not set. Please set the Access Key and the Secret Key, or configure the RAM role.")

		# Use intranet endpoint to access ECS service
		try:
			region_provider.modify_point('Ecs', region, 'ecs.%s.aliyuncs.com' % region)
		except Exception as e:
			logging.warning("Failed: failed to modify endpoint to 'ecs.%s.aliyuncs.com': %s" % (region, e))

	# Operate the fencing device
	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
	sys.exit(result)

if __name__ == "__main__":
	main()
