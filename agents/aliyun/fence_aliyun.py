#!/usr/bin/python -tt

import sys, re
import logging
import atexit
import json
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay

from aliyunsdkcore import client

from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest
from aliyunsdkecs.request.v20140526.StartInstanceRequest import StartInstanceRequest
from aliyunsdkecs.request.v20140526.StopInstanceRequest import StopInstanceRequest
from aliyunsdkecs.request.v20140526.RebootInstanceRequest import RebootInstanceRequest

def _send_request(conn, request):
	request.set_accept_format('json')
	try:
		response_str = conn.do_action_with_exception(request)
		response_detail = json.loads(response_str)
		return response_detail
	except Exception as e:
		fail_usage("Failed: _send_request failed")

def start_instance(conn, instance_id):
	request = StartInstanceRequest()
	request.set_InstanceId(instance_id)
	_send_request(conn, request)

def stop_instance(conn, instance_id):
	request = StopInstanceRequest()
	request.set_InstanceId(instance_id)
	request.set_ForceStop('true')
	_send_request(conn, request)

def reboot_instance(conn, instance_id):
	request = RebootInstanceRequest()
	request.set_InstanceId(instance_id)
	request.set_ForceStop('true')
	_send_request(conn, request)

def get_status(conn, instance_id):
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
	result = {}
	request = DescribeInstancesRequest()
	response = _send_request(conn, request)
	instance_status = None
	if response is not None:
		instance_list = response.get('Instances').get('Instance')
		for item in instance_list:
			instance_id = item.get('InstanceId')
			result[instance_id] = ("", None)
	return result

def get_power_status(conn, options):
	state = get_status(conn, options["--plug"])
	if state == "Running":
		return "on"
	elif state == "Stopped":
		return "off"
	else:
		return "unknown"


def set_power_status(conn, options):
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
	docs["shortdesc"] = "Fence agent for Aliyun (Aliyun Web Services)"
	docs["longdesc"] = "fence_aliyun is an I/O Fencing agent for Aliyun"
	docs["vendorurl"] = "http://www.aliyun.com"
	show_docs(options, docs)

	run_delay(options)

	if "--region" in options and "--access-key" in options and "--secret-key" in options:  
		region = options["--region"]
		access_key = options["--access-key"]
		secret_key = options["--secret-key"]
		conn = client.AcsClient(access_key, secret_key, region)


	# Operate the fencing device
	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
	sys.exit(result)

if __name__ == "__main__":
	main()
