#!@PYTHON@ -tt

# Copyright (c) 2018 Dell Inc. or its subsidiaries. All Rights Reserved.

# Fence agent for devices that support the Redfish API Specification.

import sys
import re
import logging
import json
import requests
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")

from fencing import *
from fencing import fail_usage, run_delay

GET_HEADERS = {'accept': 'application/json', 'OData-Version': '4.0'}
POST_HEADERS = {'content-type': 'application/json', 'accept': 'application/json',
                'OData-Version': '4.0'}


def get_power_status(conn, options):
    response = send_get_request(options, options["--systems-uri"])
    if response['ret'] is False:
        fail_usage("Couldn't get power information")
    data = response['data']

    try:
        logging.debug("PowerState is: " + data[u'PowerState'])
    except Exception:
        fail_usage("Unable to get PowerState: " + "https://" + options["--ip"] + ":" + str(options["--ipport"]) + options["--systems-uri"])

    if data[u'PowerState'].strip() == "Off":
        return "off"
    else:
        return "on"

def set_power_status(conn, options):
    action = {
        'on' : "On",
        'off': "ForceOff",
        'reboot': "ForceRestart",
        'diag': "Nmi"
    }[options.get("original-action") or options["--action"]]

    payload = {'ResetType': action}

    # Search for 'Actions' key and extract URI from it
    response = send_get_request(options, options["--systems-uri"])
    if response['ret'] is False:
        return {'ret': False}
    data = response['data']
    action_uri = data["Actions"]["#ComputerSystem.Reset"]["target"]

    response = send_post_request(options, action_uri, payload)
    if response['ret'] is False:
        fail_usage("Error sending power command")
    if options.get("original-action") == "diag":
        return True
    return

def send_get_request(options, uri):
    full_uri = "https://" + options["--ip"] + ":" + str(options["--ipport"]) + uri
    try:
        resp = requests.get(full_uri, verify=not "--ssl-insecure" in options,
                            headers=GET_HEADERS,
                            auth=(options["--username"], options["--password"]))
        data = resp.json()
    except Exception as e:
        fail_usage("Failed: send_get_request: " + str(e))
    return {'ret': True, 'data': data}

def send_post_request(options, uri, payload):
    full_uri = "https://" + options["--ip"] + ":" + str(options["--ipport"]) + uri
    try:
        requests.post(full_uri, data=json.dumps(payload),
                      headers=POST_HEADERS, verify=not "--ssl-insecure" in options,
                      auth=(options["--username"], options["--password"]))
    except Exception as e:
        fail_usage("Failed: send_post_request: " + str(e))
    return {'ret': True}

def find_systems_resource(options):
    response = send_get_request(options, options["--redfish-uri"])
    if response['ret'] is False:
        return {'ret': False}
    data = response['data']

    if 'Systems' not in data:
        # Systems resource not found"
        return {'ret': False}
    else:
        response = send_get_request(options, data["Systems"]["@odata.id"])
        if response['ret'] is False:
            return {'ret': False}
        data = response['data']

        # need to be able to handle more than one entry
        for member in data[u'Members']:
            system_uri = member[u'@odata.id']
        return {'ret': True, 'uri': system_uri}

def define_new_opts():
    all_opt["redfish-uri"] = {
        "getopt" : ":",
        "longopt" : "redfish-uri",
        "help" : "--redfish-uri=[uri]            Base or starting Redfish URI",
        "required" : "0",
        "default" : "/redfish/v1",
        "shortdesc" : "Base or starting Redfish URI",
        "order": 1
    }
    all_opt["systems-uri"] = {
        "getopt" : ":",
        "longopt" : "systems-uri",
        "help" : "--systems-uri=[uri]            Redfish Systems resource URI",
        "required" : "0",
        "shortdesc" : "Redfish Systems resource URI, i.e. /redfish/v1/Systems/System.Embedded.1",
        "order": 1
    }

def main():
    atexit.register(atexit_handler)
    device_opt = ["ipaddr", "login", "passwd", "redfish-uri", "systems-uri",
                  "ssl", "diag"]
    define_new_opts()

    opt = process_input(device_opt)

    all_opt["ssl"]["default"] = "1"
    options = check_input(device_opt, opt)

    docs = {}
    docs["shortdesc"] = "Power Fencing agent for Redfish"
    docs["longdesc"] = "fence_redfish is a Power Fencing agent which can be used with \
Out-of-Band controllers that support Redfish APIs. These controllers provide remote \
access to control power on a server."
    docs["vendorurl"] = "http://www.dmtf.org"
    show_docs(options, docs)
    run_delay(options)

    ##
    ## Operate the fencing device
    ####

    # Disable insecure-certificate-warning message
    if "--ssl-insecure" in opt:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # backwards compatibility for <ip>:<port>
    if options["--ip"].count(":") == 1:
        (options["--ip"], options["--ipport"]) = options["--ip"].split(":")

    if "--systems-uri" not in opt:
        # Systems URI not provided, find it
        sysresult = find_systems_resource(options)
        if sysresult['ret'] is False:
            sys.exit(1)
        else:
            options["--systems-uri"] = sysresult["uri"]

    reboot_fn = None
    if options["--action"] == "diag":
        # Diag is a special action that can't be verified so we will reuse reboot functionality
        # to minimize impact on generic library
        options["original-action"] = options["--action"]
        options["--action"] = "reboot"
        options["--method"] = "cycle"
        reboot_fn = set_power_status

    result = fence_action(None, options, set_power_status, get_power_status, None, reboot_fn)
    sys.exit(result)

if __name__ == "__main__":
    main()
