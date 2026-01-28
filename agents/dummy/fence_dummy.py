#!@PYTHON@ -tt

import sys, random
import logging
import time
import atexit
import os
import json
import socket
import uuid
from datetime import datetime

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, run_delay

plug_status = "on"

# Defaults for recorder mode
DEFAULT_REQUEST_PATH = "@FENCETMPDIR@/fence_dummy/requests"
DEFAULT_RESPONSE_PATH = "@FENCETMPDIR@/fence_dummy/responses"
DEFAULT_RECORDER_TIMEOUT = 60
DEFAULT_RECORDER_POLL_INTERVAL = 0.5
DEFAULT_LOG_PATH = "@LOGDIR@"

def get_power_status_file(conn, options):
	del conn

	try:
		status_file = open(options["--status-file"], 'r')
	except Exception:
		return "off"

	status = status_file.read()
	status_file.close()

	return status.lower()

def set_power_status_file(conn, options):
	del conn

	if not (options["--action"] in ["on", "off"]):
		return

	status_file = open(options["--status-file"], 'w')
	status_file.write(options["--action"])
	status_file.close()

def get_power_status_fail(conn, options):
	outlets = get_outlets_fail(conn, options)

	if len(outlets) == 0 or "--plug" not in options:
		fail_usage("Failed: You have to enter existing machine!")
	else:
		return outlets[options["--plug"]][0]

def set_power_status_fail(conn, options):
	global plug_status
	del conn

	plug_status = "unknown"
	if options["--action"] == "on":
		plug_status = "off"

def get_outlets_fail(conn, options):
	del conn

	result = {}
	global plug_status

	if options["--action"] == "on":
		plug_status = "off"

	# This fake agent has no port data to list, so we have to make
	# something up for the list action.
	if options.get("--action", None) == "list":
		result["fake_port_1"] = [plug_status, "fake"]
		result["fake_port_2"] = [plug_status, "fake"]
	elif "--plug" not in options:
		fail_usage("Failed: You have to enter existing machine!")
	else:
		port = options["--plug"]
		result[port] = [plug_status, "fake"]

	return result

# Recorder mode logging functions
def setup_recorder_logging(log_path):
	"""Initialize logging with the specified log directory (recorder mode only)
	
	Adds an additional file handler to log fence events to a separate file.
	Keeps the default root logger format for pacemaker.log compatibility.
	
	Note: The root logger level must be set to INFO to allow INFO messages
	through to handlers. fencing.py sets it to WARNING by default unless
	--verbose is specified.
	"""
	os.makedirs(log_path, exist_ok=True)
	fence_log = os.path.join(log_path, "fence-events.log")
	
	# Add file handler for fence events (keeps existing root logger handlers)
	file_handler = logging.FileHandler(fence_log)
	file_handler.setLevel(logging.INFO)
	file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S'))
	
	# Set root logger level to INFO to allow our INFO messages through
	# (fencing.py defaults to WARNING unless --verbose is set)
	root_logger = logging.getLogger()
	if root_logger.level > logging.INFO:
		root_logger.setLevel(logging.INFO)
	root_logger.addHandler(file_handler)
	
	return log_path, fence_log

def record_fence_event(action, target_node, status, details=""):
	"""Record fencing event to log"""
	logging.info(f"Fence event: action={action}, target={target_node}, status={status}, details={details}")

# Recorder mode functions
def write_fence_request_recorder(action, target_node, request_dir):
	"""Write fence request file (atomic rename pattern)"""
	os.makedirs(request_dir, exist_ok=True)
	
	request_id = str(uuid.uuid4())
	filename = f"{target_node}-{request_id}.json"
	temp_file = os.path.join(request_dir, f".{filename}.tmp")
	final_file = os.path.join(request_dir, filename)
	
	request_data = {
		"request_id": request_id,
		"timestamp": datetime.now().astimezone().isoformat(),
		"action": action,
		"target_node": target_node,
		"recorder_node": socket.gethostname()
	}
	
	try:
		with open(temp_file, 'w') as f:
			json.dump(request_data, f, indent=2)
		os.rename(temp_file, final_file)
		logging.info(f"Wrote fence request: {final_file}")
		return request_id
	except Exception as e:
		logging.error(f"Failed to write fence request: {e}")
		try:
			os.remove(temp_file)
		except OSError:
			pass
		return None

def wait_for_fence_response_recorder(request_id, target_node, response_dir, timeout, poll_interval):
	"""Wait for external component to write response file"""
	os.makedirs(response_dir, exist_ok=True)
	
	response_file = os.path.join(response_dir, f"{target_node}-{request_id}.json")
	start_time = time.time()
	
	logging.info(f"Waiting for fence response: {response_file} (timeout={timeout}s)")
	
	while time.time() - start_time < timeout:
		try:
			if os.path.exists(response_file):
				file_size = os.path.getsize(response_file)
				if file_size > 1024 * 1024:  # 1MB limit
					logging.error(f"Response file too large: {file_size} bytes")
					return False, "Response file exceeds size limit"
				
				with open(response_file, 'r') as f:
					response_data = json.load(f)
				
				success = response_data.get("success", False)
				message = response_data.get("message", "Fence operation completed")
				timestamp = response_data.get("timestamp", "unknown")
				response_target = response_data.get("target_node", "unknown")
				response_recorder = response_data.get("recorder_node", "unknown")
				
				logging.info(f"Fence response received: success={success}, message={message}, timestamp={timestamp}")
				logging.info(f"Response metadata: target={response_target}, recorder={response_recorder}")
				return success, message
		except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
			logging.debug(f"Waiting for response: {e}")
		
		time.sleep(poll_interval)
	
	logging.error(f"Fence response timeout after {timeout}s")
	return False, f"Fence operation timed out after {timeout}s"

def get_power_status_recorder(conn, options):
	"""Recorder mode get_power_status - not used with sync pattern"""
	del conn
	# This shouldn't be called when using sync_set_power_fn pattern
	# Return 'on' as fallback
	return "on"

def sync_set_power_status_recorder(conn, options):
	"""Recorder mode sync_set_power_status - write request and wait for response.
	
	Returns True on success, False on failure. Using sync pattern avoids
	the post-action power state verification that would fail since we can't
	query the actual power state of fenced nodes.
	"""
	del conn
	
	action = options["--action"]
	target_node = options["--plug"]
	request_path = options["--request-path"]
	response_path = options["--response-path"]
	timeout = int(options["--recorder-timeout"])
	poll_interval = float(options["--recorder-poll-interval"])
	
	# Only handle off/reboot actions (not on/status/monitor)
	if action not in ["off", "reboot"]:
		return True
	
	# Record fence event initiation
	record_fence_event(
		action,
		target_node,
		"requested",
		f"Fence action {action} requested"
	)
	
	# Write request
	request_id = write_fence_request_recorder(action, target_node, request_path)
	if not request_id:
		record_fence_event(
			action,
			target_node,
			"failed",
			"Failed to create fence request file"
		)
		return False
	
	# Wait for response
	success, message = wait_for_fence_response_recorder(
		request_id, target_node, response_path, timeout, poll_interval
	)
	
	if not success:
		logging.error(f"Fence operation failed: {message}")
		record_fence_event(
			action,
			target_node,
			"failed",
			f"Fence action {action} failed: {message}"
		)
		return False
	
	# Record successful completion
	record_fence_event(
		action,
		target_node,
		"completed",
		f"Fence action {action} completed successfully: {message}"
	)
	
	return True

def main():
	device_opt = ["no_password", "status_file", "random_sleep_range", "type", "port", "no_port",
		      "request_path", "response_path", "recorder_timeout", "recorder_poll_interval", "log_path"]

	atexit.register(atexit_handler)

	# Port is optional - no_port in device_opt handles runtime validation,
	# but we also need to set required=0 for correct metadata generation
	all_opt["port"]["required"] = "0"

	all_opt["status_file"] = {
		"getopt" : ":",
		"longopt" : "status-file",
		"help":"--status-file=[file]           Name of file that holds current status",
		"required" : "0",
		"shortdesc" : "File with status",
		"default" : "/tmp/fence_dummy.status",
		"order": 1
		}

	all_opt["random_sleep_range"] = {
		"getopt" : ":",
		"longopt" : "random_sleep_range",
		"help":"--random_sleep_range=[seconds] Issue a sleep between 1 and [seconds]",
		"required" : "0",
		"shortdesc" : "Issue a sleep between 1 and X seconds. Used for testing.",
		"order": 1
		}

	all_opt["type"] = {
		"getopt" : ":",
		"longopt" : "type",
		"help":"--type=[type]                  Possible types are: file, fail, and recorder",
		"required" : "0",
		"shortdesc" : "Type of the dummy fence agent",
		"default" : "file",
		"order": 1
		}

	all_opt["request_path"] = {
		"getopt" : ":",
		"longopt" : "request-path",
		"help":"--request-path=[path]          Directory for fence request files (recorder mode)",
		"required" : "0",
		"shortdesc" : "Request directory path for recorder mode",
		"default" : DEFAULT_REQUEST_PATH,
		"order": 1
		}

	all_opt["response_path"] = {
		"getopt" : ":",
		"longopt" : "response-path",
		"help":"--response-path=[path]         Directory for fence response files (recorder mode)",
		"required" : "0",
		"shortdesc" : "Response directory path for recorder mode",
		"default" : DEFAULT_RESPONSE_PATH,
		"order": 1
		}

	all_opt["recorder_timeout"] = {
		"getopt" : ":",
		"longopt" : "recorder-timeout",
		"help":"--recorder-timeout=[seconds]   Timeout for external response (recorder mode)",
		"required" : "0",
		"shortdesc" : "Response timeout for recorder mode",
		"default" : str(DEFAULT_RECORDER_TIMEOUT),
		"order": 1
		}

	all_opt["recorder_poll_interval"] = {
		"getopt" : ":",
		"longopt" : "recorder-poll-interval",
		"help":"--recorder-poll-interval=[sec] Poll interval for response check (recorder mode)",
		"required" : "0",
		"shortdesc" : "Poll interval for recorder mode",
		"default" : str(DEFAULT_RECORDER_POLL_INTERVAL),
		"order": 1
		}

	all_opt["log_path"] = {
		"getopt" : ":",
		"longopt" : "log-path",
		"help":"--log-path=[path]              Directory for fence event logs (recorder mode)",
		"required" : "0",
		"shortdesc" : "Log directory path for fence events",
		"default" : DEFAULT_LOG_PATH,
		"order": 1
		}

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Dummy fence agent"
	docs["longdesc"] = "fence_dummy is a fake fence agent for testing. " \
		"It supports three modes: 'file' (status in file), 'fail' (simulated failures), " \
		"and 'recorder' (request/response coordination with external systems)."
	docs["vendorurl"] = "http://www.example.com"
	show_docs(options, docs)

	# Setup persistent logging for recorder mode only
	if options.get("--type") == "recorder":
		setup_recorder_logging(options["--log-path"])

	run_delay(options)

	# random sleep for testing
	if "--random_sleep_range" in options:
		val = int(options["--random_sleep_range"])
		ran = random.randint(1, val)
		logging.info("Random sleep for %d seconds\n", ran)
		time.sleep(ran)

	if options["--type"] == "fail":
		result = fence_action(None, options, set_power_status_fail, get_power_status_fail, get_outlets_fail)
	elif options["--type"] == "recorder":
		# Use sync_set_power_fn pattern to avoid post-action power state verification
		# (we can't query actual power state - the response file confirms the action)
		# Note: fence_action signature is (conn, options, set_power_fn, get_power_fn, get_outlet_list, reboot_cycle_fn, sync_set_power_fn)
		# The 7th parameter is defined in lib/fencing.py.py but not in agents/autodetect/fencing.py
		result = fence_action(None, options, None, get_power_status_recorder, None, None, sync_set_power_status_recorder)  # type: ignore[call-arg]
	else:
		result = fence_action(None, options, set_power_status_file, get_power_status_file, None)

	sys.exit(result)

if __name__ == "__main__":
	main()
