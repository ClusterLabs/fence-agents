#!@PYTHON@ -tt

import sys, re
import logging
import atexit
import time
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, run_delay, EC_STATUS, SyslogLibHandler

import requests
from requests import HTTPError

try:
	import boto3
	from botocore.exceptions import ConnectionError, ClientError, EndpointConnectionError, NoRegionError, ParamValidationError
except ImportError:
	pass

logger = logging.getLogger()
logger.propagate = False
logger.setLevel(logging.INFO)
logger.addHandler(SyslogLibHandler())
logging.getLogger('botocore.vendored').propagate = False

status = {
		"running": "on",
		"stopped": "off",
		"pending": "unknown",
		"stopping": "off",
		"shutting-down": "off",
		"terminated": "off"
}

# IMDSv2 endpoints. Timeout is (connect, read) in seconds; the fence path must
# never block on an unreachable metadata service.
IMDS_TOKEN_URL = "http://169.254.169.254/latest/api/token"
IMDS_META_URL = "http://169.254.169.254/latest/meta-data"
IMDS_TIMEOUT = (2, 5)

def _imds_fetch(path, options):
	"""Fetch a single IMDSv2 metadata path. Returns the value as str, or None on any failure."""
	try:
		token = requests.put(
			IMDS_TOKEN_URL,
			headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
			timeout=IMDS_TIMEOUT).content.decode("UTF-8")
		return requests.get(
			"{}/{}".format(IMDS_META_URL, path),
			headers={"X-aws-ec2-metadata-token": token},
			timeout=IMDS_TIMEOUT).content.decode("UTF-8")
	except HTTPError as http_err:
		logger.error("HTTP error accessing EC2 metadata (%s): %s", path, http_err)
	except Exception as err:
		if "--skip-race-check" not in options:
			logger.error("Error accessing EC2 metadata (%s): %s", path, err)
		else:
			logger.debug("Error accessing EC2 metadata (%s): %s", path, err)
	return None

def get_instance_id(options):
	return _imds_fetch("instance-id", options)


def get_instance_by_tag(conn, tag_name, tag_value, options, max_retries=3, retry_delay=2):
	"""
	Look up EC2 instance ID by tag name and value.
	Returns instance ID if found, None otherwise.

	Includes retry logic for AWS API eventual consistency.

	For blue/green deployments with multiple running instances:
	1. Get current instance's build_number tag (from cached values)
	2. Filter for non-terminated instances with matching tag
	3. Prefer instance with SAME build_number as current instance
	4. If no build_number match and multiple instances, REFUSE to guess
	"""
	last_error = None

	for attempt in range(1, max_retries + 1):
		try:
			region = options.get("--region")
			logger.debug("Looking up instance by tag %s=%s in region %s (attempt %d/%d)",
				tag_name, tag_value, region, attempt, max_retries)

			my_build_number = options.get("my_build_number")

			filters = [
				{"Name": "tag:{}".format(tag_name), "Values": [tag_value]},
				{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}
			]
			instances = list(conn.instances.filter(Filters=filters))

			if not instances:
				if attempt < max_retries:
					logger.debug("No instance found with tag %s=%s in fenceable states (attempt %d/%d), retrying in %ds",
						tag_name, tag_value, attempt, max_retries, retry_delay)
					time.sleep(retry_delay)
					continue
				logger.warning("No instance found with tag %s=%s in fenceable states after %d attempts",
					tag_name, tag_value, max_retries)
				return None

			if len(instances) > 1:
				logger.warning("Multiple running instances found with tag %s=%s:", tag_name, tag_value)

				instances_with_build = []
				for inst in instances:
					build_num = None
					if inst.tags:
						for tag in inst.tags:
							if tag['Key'] == 'build_number':
								build_num = tag['Value']
								break
					instances_with_build.append((inst, build_num))
					logger.warning("  - %s (build_number=%s, launched=%s)",
						inst.id, build_num if build_num else "N/A", inst.launch_time)

				selected_inst = None
				if my_build_number:
					for inst, build_num in instances_with_build:
						if build_num == my_build_number:
							selected_inst = inst
							logger.warning("Selecting instance with matching build_number=%s: %s",
								my_build_number, inst.id)
							break

				if not selected_inst:
					logger.error("Multiple instances match tag %s=%s but none match build_number=%s. "
						"Refusing to guess. Manual intervention required.",
						tag_name, tag_value, my_build_number)
					return None

				instance_id = selected_inst.id
			else:
				instance_id = instances[0].id
				logger.debug("Single instance found: %s", instance_id)

			logger.debug("Selected instance %s with tag %s=%s", instance_id, tag_name, tag_value)
			return instance_id

		except (ClientError, EndpointConnectionError, ConnectionError) as e:
			last_error = e
			if attempt < max_retries:
				logger.warning("AWS API error during tag lookup (attempt %d/%d): %s. Retrying in %ds",
					attempt, max_retries, e, retry_delay)
				time.sleep(retry_delay)
				continue
			logger.error("Failed to lookup instance by tag after %d attempts: %s", max_retries, e)
			return None

	logger.error("Failed to lookup instance by tag after %d attempts: %s", max_retries, last_error)
	return None


def get_instance_by_eni(conn, eni_id, max_retries=3, retry_delay=2):
	"""
	Resolve ENI ID to attached instance ID.
	Returns (instance_id, None) on success or (None, error_msg) on failure.

	When the ENI exists but is not attached, the target instance is gone
	(terminated or being replaced). The caller decides the semantics:
	- get_power_status treats "not attached" as OFF (safe)
	- set_power_status fails safe when the target cannot be resolved
	"""
	last_error = None

	for attempt in range(1, max_retries + 1):
		try:
			client = conn.meta.client
			response = client.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
			enis = response.get('NetworkInterfaces', [])

			if not enis:
				return (None, "ENI {} not found".format(eni_id))

			eni = enis[0]
			eni_status = eni.get('Status', 'unknown')
			attachment = eni.get('Attachment')

			if not attachment:
				return (None, "ENI {} exists but not attached (status: {})".format(eni_id, eni_status))

			attach_status = attachment.get('Status', 'unknown')
			if attach_status not in ('attached', 'attaching'):
				return (None, "ENI {} attachment in transitional state: {}".format(eni_id, attach_status))

			instance_id = attachment.get('InstanceId')
			if not instance_id:
				return (None, "ENI {} attached but no InstanceId in response".format(eni_id))

			logger.debug("ENI %s is attached to instance %s", eni_id, instance_id)
			return (instance_id, None)

		except ClientError as e:
			error_code = e.response.get('Error', {}).get('Code', '')
			if error_code == 'InvalidNetworkInterfaceID.NotFound':
				return (None, "ENI {} does not exist".format(eni_id))
			last_error = e
			if attempt < max_retries:
				logger.warning("AWS API error during ENI lookup (attempt %d/%d): %s. Retrying in %ds",
					attempt, max_retries, e, retry_delay)
				time.sleep(retry_delay)
				continue
			return (None, "AWS API error after {} attempts: {}".format(max_retries, e))
		except (EndpointConnectionError, ConnectionError) as e:
			last_error = e
			if attempt < max_retries:
				logger.warning("Connection error during ENI lookup (attempt %d/%d): %s. Retrying in %ds",
					attempt, max_retries, e, retry_delay)
				time.sleep(retry_delay)
				continue
			return (None, "Connection error after {} attempts: {}".format(max_retries, e))

	return (None, "ENI lookup failed after {} attempts: {}".format(max_retries, last_error))


def get_instance_by_volume(conn, volume_id, max_retries=3, retry_delay=2):
	"""
	Resolve EBS volume ID to attached instance ID.
	Returns (instance_id, None) on success or (None, error_msg) on failure.

	When the volume exists but is not attached, the target instance is gone
	(terminated or being replaced). Same caller semantics as ENI resolution.
	"""
	last_error = None

	for attempt in range(1, max_retries + 1):
		try:
			client = conn.meta.client
			response = client.describe_volumes(VolumeIds=[volume_id])
			volumes = response.get('Volumes', [])

			if not volumes:
				return (None, "Volume {} not found".format(volume_id))

			volume = volumes[0]
			vol_state = volume.get('State', 'unknown')
			attachments = volume.get('Attachments', [])

			if not attachments:
				return (None, "Volume {} exists but not attached (state: {})".format(volume_id, vol_state))

			if len(attachments) > 1:
				return (None, "Volume {} has {} attachments (multi-attach). Cannot determine target.".format(
					volume_id, len(attachments)))

			attach = attachments[0]
			attach_status = attach.get('State', 'unknown')
			if attach_status not in ('attached', 'attaching'):
				return (None, "Volume {} attachment in transitional state: {}".format(volume_id, attach_status))

			instance_id = attach.get('InstanceId')
			if not instance_id:
				return (None, "Volume {} attached but no InstanceId in response".format(volume_id))

			logger.debug("Volume %s is attached to instance %s", volume_id, instance_id)
			return (instance_id, None)

		except ClientError as e:
			error_code = e.response.get('Error', {}).get('Code', '')
			if error_code == 'InvalidVolume.NotFound':
				return (None, "Volume {} does not exist".format(volume_id))
			last_error = e
			if attempt < max_retries:
				logger.warning("AWS API error during EBS lookup (attempt %d/%d): %s. Retrying in %ds",
					attempt, max_retries, e, retry_delay)
				time.sleep(retry_delay)
				continue
			return (None, "AWS API error after {} attempts: {}".format(max_retries, e))
		except (EndpointConnectionError, ConnectionError) as e:
			last_error = e
			if attempt < max_retries:
				logger.warning("Connection error during EBS lookup (attempt %d/%d): %s. Retrying in %ds",
					attempt, max_retries, e, retry_delay)
				time.sleep(retry_delay)
				continue
			return (None, "Connection error after {} attempts: {}".format(max_retries, e))

	return (None, "EBS lookup failed after {} attempts: {}".format(max_retries, last_error))


def resolve_plug_to_instance_id(conn, options):
	"""
	Resolve the --plug parameter to an instance ID.

	Dispatches by --identity-method:
	  instance-id (default): --plug is the instance ID directly
	  tag:                   --plug is a tag value, resolved via DescribeInstances
	  eni:                   --plug is an ENI ID, resolved via DescribeNetworkInterfaces
	  ebs:                   --plug is a volume ID, resolved via DescribeVolumes

	Uses a per-invocation cache to minimise AWS control plane calls.
	The identity -> instance ID mapping is resolved ONCE and reused for all
	subsequent calls within the same fence operation (status checks,
	power actions, polling).

	The cache is safe because:
	- The instance ID cannot change while the instance is being fenced
	- The agent process is short-lived (one fence operation per invocation)
	- If the cached ID becomes invalid (instance terminated between calls),
	  the StopInstances call fails gracefully with InvalidInstanceID.NotFound
	"""
	plug_value = options.get("--plug")
	identity_method = options.get("--identity-method", "instance-id")

	if not plug_value:
		logger.error("No --plug parameter provided")
		return None

	cache_key = "cached_instance_id"
	cached = options.get(cache_key)
	if cached:
		logger.debug("Using cached instance ID %s for plug=%s", cached, plug_value)
		return cached

	instance_id = None

	if identity_method == "eni":
		logger.debug("ENI-based lookup: %s", plug_value)
		instance_id, error = get_instance_by_eni(conn, plug_value)
		if error:
			logger.error("ENI resolution failed: %s", error)
			return None

	elif identity_method == "ebs":
		logger.debug("EBS-based lookup: %s", plug_value)
		instance_id, error = get_instance_by_volume(conn, plug_value)
		if error:
			logger.error("EBS resolution failed: %s", error)
			return None

	elif identity_method == "tag" or options.get("--tag"):
		tag_name = options.get("--tag", "Name")
		logger.debug("Tag-based lookup: %s=%s", tag_name, plug_value)
		instance_id = get_instance_by_tag(conn, tag_name, plug_value, options)
		if not instance_id:
			logger.error("Failed to find instance with tag %s=%s", tag_name, plug_value)

	else:
		logger.debug("Direct instance ID: %s", plug_value)
		instance_id = plug_value

	if instance_id:
		options[cache_key] = instance_id
		logger.debug("Resolved plug=%s to instance %s (method: %s)",
			plug_value, instance_id, identity_method)

	return instance_id


def check_tag_target_is_dead(conn, options):
	"""
	When tag lookup returns no fenceable instances, determine whether the
	target is genuinely dead (all terminated) or if the lookup failed for
	other reasons (wrong tag, API error, etc.).

	Returns True if the target is confirmed dead, False otherwise.
	"""
	tag_name = options.get("--tag")
	plug_value = options.get("--plug")

	if not tag_name:
		return False

	try:
		all_states = list(conn.instances.filter(Filters=[
			{"Name": "tag:{}".format(tag_name), "Values": [plug_value]}
		]))

		if all_states and all(i.state["Name"] in ("terminated", "shutting-down") for i in all_states):
			logger.info("All instances with tag %s=%s are terminated/shutting-down. Target confirmed dead.",
				tag_name, plug_value)
			return True

		if not all_states:
			logger.error("No instance has ever existed with tag %s=%s. This is a configuration error.",
				tag_name, plug_value)
			return False

		live_states = [i.state["Name"] for i in all_states if i.state["Name"] not in ("terminated", "shutting-down")]
		logger.error("Instances with tag %s=%s exist in unexpected states: %s. Cannot confirm target is dead.",
			tag_name, plug_value, live_states)
		return False

	except (ClientError, EndpointConnectionError, ConnectionError) as e:
		logger.error("AWS API error during dead-target check: %s", e)
		return False


def get_nodes_list(conn, options):
	logger.debug("Starting monitor operation")
	result = {}
	filter = []
	try:
		tag_name = options.get("--tag")

		if "--filter" in options:
			filter_key   = options["--filter"].split("=")[0].strip()
			filter_value = options["--filter"].split("=")[1].strip()
			filter = [{ "Name": filter_key, "Values": [filter_value] }]
			logging.debug("Filter: {}".format(filter))

		for instance in conn.instances.filter(Filters=filter):
			instance_name = ""
			for tag in instance.tags or []:
				if tag.get("Key") == "Name":
					instance_name = tag["Value"]
					break

			port_name = instance.id
			if tag_name and instance.tags:
				for tag in instance.tags:
					if tag['Key'] == tag_name:
						port_name = tag['Value']
						logger.debug("Mapped instance %s to port name %s via tag %s",
							instance.id, port_name, tag_name)
						break

			try:
				result[port_name] = (instance_name, status[instance.state["Name"]])
			except KeyError as e:
				if options.get("--original-action") == "list-status":
					logger.error("Unknown status \"{}\" returned for {} ({})".format(
						instance.state["Name"], instance.id, instance_name))
				result[port_name] = (instance_name, "unknown")
	except ClientError:
		fail_usage("Failed: Incorrect Access Key or Secret Key.")
	except EndpointConnectionError:
		fail_usage("Failed: Incorrect Region.")
	except ConnectionError as e:
		fail_usage("Failed: Unable to connect to AWS: " + str(e))
	except Exception as e:
		logger.error("Failed to get node list: %s", e)
	logger.debug("Monitor operation OK: %s",result)
	return result

def check_eni_ebs_target_is_dead(conn, options):
	"""
	For ENI/EBS modes, when resolve returns None, check whether
	the resource exists but is simply not attached (target dead)
	vs a real error (resource doesn't exist, API failure, etc.).

	Returns True if the target is confirmed dead, False otherwise.
	"""
	identity_method = options.get("--identity-method", "instance-id")
	plug_value = options.get("--plug")

	if identity_method == "eni":
		try:
			client = conn.meta.client
			response = client.describe_network_interfaces(NetworkInterfaceIds=[plug_value])
			enis = response.get('NetworkInterfaces', [])
			if enis and not enis[0].get('Attachment'):
				logger.info("ENI %s exists but not attached. Target confirmed dead.", plug_value)
				return True
		except ClientError as e:
			error_code = e.response.get('Error', {}).get('Code', '')
			if error_code == 'InvalidNetworkInterfaceID.NotFound':
				logger.error("ENI %s does not exist. Configuration error.", plug_value)
			else:
				logger.error("AWS API error during ENI dead-target check [%s]: %s", error_code, e)
		return False

	elif identity_method == "ebs":
		try:
			client = conn.meta.client
			response = client.describe_volumes(VolumeIds=[plug_value])
			volumes = response.get('Volumes', [])
			if volumes and not volumes[0].get('Attachments'):
				logger.info("Volume %s exists but not attached. Target confirmed dead.", plug_value)
				return True
		except ClientError as e:
			error_code = e.response.get('Error', {}).get('Code', '')
			if error_code == 'InvalidVolume.NotFound':
				logger.error("Volume %s does not exist. Configuration error.", plug_value)
			else:
				logger.error("AWS API error during EBS dead-target check [%s]: %s", error_code, e)
		return False

	return False


def get_power_status(conn, options):
	logger.debug("Starting status operation")
	try:
		instance_id = resolve_plug_to_instance_id(conn, options)
		if not instance_id:
			# The fencing library learns target state only through this function
			# (fence_action pre-check and the post-off status poll). For tag/eni/ebs
			# identity a terminated instance no longer resolves, so the
			# confirmed-dead-vs-unknown decision must be made here: report OFF only
			# when the target is positively confirmed dead, otherwise fail.
			identity_method = options.get("--identity-method", "instance-id")

			if identity_method in ("eni", "ebs"):
				if check_eni_ebs_target_is_dead(conn, options):
					logger.info("No fenceable instance for plug=%s — target confirmed dead (method: %s). Reporting OFF.",
						options.get("--plug"), identity_method)
					return "off"
			elif check_tag_target_is_dead(conn, options):
				logger.info("No fenceable instance for plug=%s — target confirmed dead. Reporting OFF.",
					options.get("--plug"))
				return "off"

			logger.error("No instance resolved for plug=%s and target not confirmed dead. Reporting FAILED.",
				options.get("--plug"))
			fail(EC_STATUS)

		instance = conn.instances.filter(Filters=[{"Name": "instance-id", "Values": [instance_id]}])
		instance_list = list(instance)
		if not instance_list:
			logger.debug("Instance %s not found (likely terminated). Reporting OFF.", instance_id)
			return "off"

		state = instance_list[0].state["Name"]
		logger.debug("Status operation for EC2 instance %s returned state: %s", instance_id, state.upper())
		try:
			return status[state]
		except KeyError as e:
			logger.error("Unknown status \"{}\" returned".format(state))
			return "unknown"
	except ClientError:
		fail_usage("Failed: Incorrect Access Key or Secret Key.")
	except EndpointConnectionError:
		fail_usage("Failed: Incorrect Region.")
	except IndexError:
		logger.debug("Instance not found (IndexError). Reporting OFF.")
		return "off"
	except Exception as e:
		logger.error("Failed to get power status: %s", e)
		fail(EC_STATUS)

def get_self_power_status(conn, instance_id):
	try:
		instance = conn.instances.filter(Filters=[{"Name": "instance-id", "Values": [instance_id]}])
		state = list(instance)[0].state["Name"]
		if state == "running":
			logger.debug("Captured my (%s) state and it %s - returning OK - Proceeding with fencing", instance_id, state.upper())
			return "ok"
		else:
			logger.debug("Captured my (%s) state it is %s - returning Alert - Unable to fence other nodes", instance_id, state.upper())
			return "alert"

	except ClientError:
		fail_usage("Failed: Incorrect Access Key or Secret Key.")
	except EndpointConnectionError:
		fail_usage("Failed: Incorrect Region.")
	except IndexError:
		return "fail"

def set_power_status(conn, options):
	my_instance = options.get("my_instance_id") or get_instance_id(options)
	try:
		instance_id = resolve_plug_to_instance_id(conn, options)
		if not instance_id:
			# get_power_status() runs before and after this call and owns the
			# confirmed-dead-vs-unknown decision (and the resolve result is cached
			# within the invocation). If we reach here we could not resolve a target,
			# so fail safe. Never report success here — that would be a false-positive
			# fence. The status poll and Pacemaker's retry re-confirm the outcome.
			logger.error("Could not resolve instance ID for plug=%s; failing safe.",
				options.get("--plug"))
			fail(EC_STATUS)

		if options.get("--skip-os-shutdown", "true").lower() in ["1", "yes", "on", "true"]:
			shutdown_option = {
				"SkipOsShutdown": True,
				"Force": True
			}
		else:
			shutdown_option = {
				"SkipOsShutdown": False,
				"Force": True
			}
		if (options["--action"]=="off"):
			if "--skip-race-check" in options or get_self_power_status(conn,my_instance) == "ok":
				try:
					conn.instances.filter(InstanceIds=[instance_id]).stop(**shutdown_option)
					logger.info("Called StopInstance API call for %s", instance_id)
				except ParamValidationError:
					logger.warning("SkipOsShutdown not supported with the current boto3 version %s - falling back to graceful shutdown", boto3.__version__)
					conn.instances.filter(InstanceIds=[instance_id]).stop(Force=True)
				except ClientError as e:
					error_code = e.response.get('Error', {}).get('Code', '')
					if error_code in ('InvalidInstanceID.NotFound', 'IncorrectInstanceState'):
						logger.info("Instance %s cannot be stopped (error: %s). Assuming already OFF.", instance_id, error_code)
					else:
						raise
			else:
				logger.warning("Skipping fencing as instance is not in running status")
		elif (options["--action"]=="on"):
			conn.instances.filter(InstanceIds=[instance_id]).start()
			logger.info("Called StartInstance API call for %s", instance_id)
	except Exception as e:
		logger.error("Failed to power %s %s: %s", \
				options["--action"], instance_id, e)
		fail(EC_STATUS)

def define_new_opts():
	all_opt["region"] = {
		"getopt" : "r:",
		"longopt" : "region",
		"help" : "-r, --region=[region]          Region, e.g. us-east-1",
		"shortdesc" : "Region.",
		"required" : "1",
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
	all_opt["filter"] = {
		"getopt" : ":",
		"longopt" : "filter",
		"help" : "--filter=[key=value]           Filter (e.g. vpc-id=[vpc-XXYYZZAA])",
		"shortdesc": "Filter for list-action",
		"required": "0",
		"order": 5
	}
	all_opt["boto3_debug"] = {
		"getopt" : "b:",
		"longopt" : "boto3_debug",
		"help" : "-b, --boto3_debug=[option]     Boto3 and Botocore library debug logging",
		"shortdesc": "Boto Lib debug",
		"required": "0",
		"default": "False",
		"order": 6
	}
	all_opt["skip_race_check"] = {
		"getopt" : "",
		"longopt" : "skip-race-check",
		"help" : "--skip-race-check              Skip race condition check",
		"shortdesc": "Skip race condition check",
		"required": "0",
		"order": 7
	}
	all_opt["skip_os_shutdown"] = {
		"getopt" : ":",
		"longopt" : "skip-os-shutdown",
		"help" : "--skip-os-shutdown=[true|false]    Uses SkipOsShutdown flag",
		"shortdesc" : "Use SkipOsShutdown flag to stop the EC2 instance",
		"required" : "0",
		"default" : "true",
		"order" : 8
	}
	all_opt["tag"] = {
		"getopt" : ":",
		"longopt" : "tag",
		"help" : "--tag=[tag_name]               Tag name for instance lookup (e.g. 'Name'). When specified, --plug is treated as tag value instead of instance ID",
		"shortdesc": "Tag name for instance identification",
		"required": "0",
		"order": 9
	}
	all_opt["identity_method"] = {
		"getopt" : ":",
		"longopt" : "identity-method",
		"help" : "--identity-method=[method]     Identity resolution method: instance-id (default), tag, eni, ebs",
		"shortdesc": "How to resolve --plug to an instance ID. 'instance-id' treats plug as a direct instance ID, 'tag' uses EC2 tag lookup, 'eni' resolves via ENI attachment, 'ebs' resolves via EBS volume attachment.",
		"required": "0",
		"default": "instance-id",
		"order": 10
	}

def main():
	conn = None

	device_opt = ["port", "no_password", "region", "access_key", "secret_key", "filter", "boto3_debug", "skip_race_check", "skip_os_shutdown", "tag", "identity_method"]

	atexit.register(atexit_handler)

	define_new_opts()

	all_opt["power_timeout"]["default"] = "60"

	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for AWS (Amazon Web Services) with multiple identity resolution methods"
	docs["longdesc"] = "fence_aws is a Power Fencing agent for AWS (Amazon Web\
Services). It uses the boto3 library to connect to AWS.\
\n.P\n\
It supports four identity resolution methods via --identity-method:\
\n.P\n\
instance-id (default): --plug is treated as a direct EC2 instance ID.\
\n.P\n\
tag: --plug is treated as a tag value. Requires --tag to specify the tag name.\
For example: --identity-method=tag --tag=Name --plug=hostname\
\n.P\n\
eni: --plug is treated as an ENI ID. The agent resolves the ENI attachment to find\
the instance. Ideal for architectures with persistent ENIs that survive instance replacement.\
For example: --identity-method=eni --plug=eni-0a1b2c3d4e5f67890\
\n.P\n\
ebs: --plug is treated as an EBS volume ID. The agent resolves the volume attachment to\
find the instance. Ideal for architectures with persistent EBS volumes.\
For example: --identity-method=ebs --plug=vol-0a1b2c3d4e5f67890\
\n.P\n\
boto3 can be configured with AWS CLI or by creating ~/.aws/credentials.\n\
For instructions see: https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration"
	docs["vendorurl"] = "http://www.amazon.com"
	show_docs(options, docs)

	run_delay(options)

	if "--debug-file" in options:
		for handler in logger.handlers:
			if isinstance(handler, logging.FileHandler):
				logger.removeHandler(handler)
		lh = logging.FileHandler(options["--debug-file"])
		logger.addHandler(lh)
		lhf = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		lh.setFormatter(lhf)
		lh.setLevel(logging.DEBUG)

	if options["--boto3_debug"].lower() not in ["1", "yes", "on", "true"]:
		boto3.set_stream_logger('boto3',logging.INFO)
		boto3.set_stream_logger('botocore',logging.CRITICAL)
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
		if options.get("--action", "") not in ["metadata", "manpage", "validate-all"]:
			fail_usage("Failed: Unable to connect to AWS: " + str(e))

	# Cache own instance ID and build_number at startup
	# These values never change during the instance's lifetime.
	# Caching here eliminates IMDS calls from the fencing hot path.
	options["my_instance_id"] = get_instance_id(options)
	if options.get("my_instance_id"):
		logger.debug("Cached own instance ID: %s", options["my_instance_id"])
		try:
			my_inst = list(conn.instances.filter(
				Filters=[{"Name": "instance-id", "Values": [options["my_instance_id"]]}]))
			if my_inst and my_inst[0].tags:
				for tag in my_inst[0].tags:
					if tag['Key'] == 'build_number':
						options["my_build_number"] = tag['Value']
						logger.debug("Cached own build_number: %s", options["my_build_number"])
						break
		except Exception as e:
			logger.debug("Could not cache own build_number: %s", e)

	result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
	sys.exit(result)

if __name__ == "__main__":
	main()
