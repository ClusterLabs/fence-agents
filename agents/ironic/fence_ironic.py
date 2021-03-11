#!@PYTHON@ -tt

import atexit
import logging
import os
import re
import sys
from pipes import quote
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, is_executable, run_command, run_delay

def get_name_or_uuid(options):
	return options["--uuid"] if "--uuid" in options else options["--plug"]

def get_power_status(_, options):
    output = ironic_run_command(options, "status")
    stdout = output[1]
    match = re.search('power[\\s]*([a-zA-Z]{2,3})', str(stdout))
    status = match.group(1) if match else None
    return status

def set_power_status(_, options):
    ironic_run_command(options, options["--action"])
    return

def get_devices_list(_, options):
    nodes = {}
    output = ironic_run_command(options, "list")
    stdout = output[1]
    for line in stdout.splitlines():
        uuid = "UUID"
        try:
            (uuid, name, state) = line.split(',')
        except ValueError:
            pass
        if "UUID" in uuid:
            continue # skip line header
        match = re.search('power[\\s]*([a-zA-Z]{2,3})', state)
        status = match.group(1) if match else None
        nodes[uuid] = (name, status)

    return nodes

def ironic_run_command(options, action, timeout=None):
    cmd = options["--openstack-path"] + " baremetal"
    env = os.environ.copy()
    # --username / -l
    if "--username" in options and len(options["--username"]) != 0:
        env["OS_USERNAME"] = options["--username"]

    # --password / -p
    if "--password" in options:
        env["OS_PASSWORD"] = options["--password"]

    # --tenant-name -t
    if "--tenant-name" in options:
        env["OS_TENANT_NAME"] = options["--tenant-name"]

    #  --auth-url
    if "--auth-url" in options:
        env["OS_AUTH_URL"] = options["--auth-url"]

    # --action / -o
    if action == "status":
        cmd += " show %s -c power_state --format value" % (get_name_or_uuid(options))
    elif action in ["on", "off"]:
        cmd += " power %s %s" % (action, get_name_or_uuid(options))
    elif action == "list":
        cmd += " list -c 'Instance UUID' -c Name -c 'Power State' --format csv --quote minimal"


    logging.debug("cmd -> %s" % cmd)
    return run_command(options, cmd, timeout, env)

def define_new_opts():
    all_opt["auth-url"] = {
        "getopt" : ":",
        "longopt" : "auth-url",
        "help" : "--auth-url=[authurl]            Auth URL",
        "required" : "1",
        "shortdesc" : "Keystone Admin Auth URL",
        "order": 1
    }
    all_opt["tenant-name"] = {
        "getopt" : "t:",
        "longopt" : "tenant-name",
        "help" : "-t, --tenant-name=[tenant]      Tenantname",
        "required" : "0",
        "shortdesc" : "Keystone Admin Tenant",
        "default": "admin",
        "order": 1
    }
    all_opt["openstack-path"] = {
        "getopt" : ":",
        "longopt" : "openstack-path",
        "help" : "--openstack-path=[path]       Path to openstack binary",
        "required" : "0",
        "shortdesc" : "Path to the OpenStack binary",
        "default" : "@OPENSTACK_PATH@",
        "order": 200
    }

def main():
    atexit.register(atexit_handler)

    device_opt = ["login", "passwd", "port", "auth-url", "tenant-name", "openstack-path"]
    define_new_opts()

    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence agent for OpenStack's Ironic (Bare Metal as a service) service"
    docs["longdesc"] = "fence_ironic is a Fencing agent \
which can be used with machines controlled by the Ironic service. \
This agent calls the openstack CLI. \
WARNING! This fence agent is not intended for production use. Relying on a functional ironic service for fencing is not a good design choice."
    docs["vendorurl"] = "https://wiki.openstack.org/wiki/Ironic"
    show_docs(options, docs)

    run_delay(options)

    if not is_executable(options["--openstack-path"]):
        fail_usage("openstack tool not found or not accessible")

    result = fence_action(None, options, set_power_status, get_power_status, get_devices_list)
    sys.exit(result)

if __name__ == "__main__":
    main()
