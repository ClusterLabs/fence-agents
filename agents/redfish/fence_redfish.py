#!@PYTHON@ -tt

# Copyright (c) 2018 Dell Inc. or its subsidiaries. All Rights Reserved.

# Fence agent for devices that support the Redfish API Specification.

import sys
import re
import json
import requests
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")

from requests.packages.urllib3.exceptions import InsecureRequestWarning
from fencing import *
from fencing import fail_usage

def get_power_status(conn, options):
    uri = options["--systems-uri"]
    response = send_get_request(options, uri)
    if response['ret'] is False:
        fail_usage("Couldn't get power information")
    data = response['data']
    if data[u'PowerState'].strip() == "On":
        return "on"
    else:
        return "off"

def set_power_status(conn, options):
    action = {
        'on' : "On",
        'off': "ForceOff",
        'reboot': "GracefulRestart"
    }[options["--action"]]

    payload = {'ResetType': action}
    headers = {'content-type': 'application/json'}

    # Search for 'Actions' key and extract URI from it
    uri = options["--systems-uri"]
    response = send_get_request(options, uri)
    if response['ret'] is False:
        return {'ret': False}
    data = response['data']
    uri = data["Actions"]["#ComputerSystem.Reset"]["target"]

    response = send_post_request(options, uri, payload, headers)
    if response['ret'] is False:
        fail_usage("Error sending power command")
    return

def send_get_request(options, uri):
    full_uri = "https://" + options["--ip"] + uri
    try:
        resp = requests.get(full_uri, verify=False,
                            auth=(options["--username"], options["--password"]))
        data = resp.json()
    except:
        return {'ret': False}
    return {'ret': True, 'data': data}

def send_post_request(options, uri, payload, headers):
    full_uri = "https://" + options["--ip"] + uri
    try:
        requests.post(full_uri, data=json.dumps(payload),
                      headers=headers, verify=False,
                      auth=(options["--username"], options["--password"]))
    except:
        return {'ret': False}
    return {'ret': True}

def find_systems_resource(options):
    uri = options["--redfish-uri"]
    response = send_get_request(options, uri)
    if response['ret'] is False:
        return {'ret': False}
    data = response['data']

    if 'Systems' not in data:
        # Systems resource not found"
        return {'ret': False}
    else:
        uri = data["Systems"]["@odata.id"]
        response = send_get_request(options, uri)
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
        "help" : "--redfish-uri=[uri]            Base or starting Redifsh URI",
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
    device_opt = ["ipaddr", "login", "passwd", "redfish-uri", "systems-uri", "ssl"]
    define_new_opts()

    opt = process_input(device_opt)

    all_opt["ipport"]["default"] = "443"
    options = check_input(device_opt, opt)

    docs = {}
    docs["shortdesc"] = "I/O Fencing agent for Redfish"
    docs["longdesc"] = "fence_redfish is an I/O Fencing agent which can be used with \
Out-of-Band controllers that support Redfish APIs. These controllers provide remote \
access to control power on a server."
    docs["vendorurl"] = "http://www.dmtf.org"
    show_docs(options, docs)

    ##
    ## Operate the fencing device
    ####

    # Disable insecure-certificate-warning message
    if "--ssl-insecure" in opt:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    if "--systems-uri" not in opt:
        # Systems URI not provided, find it
        sysresult = find_systems_resource(options)
        if sysresult['ret'] is False:
            sys.exit(1)
        else:
            options["--systems-uri"] = sysresult["uri"]

    result = fence_action(None, options, set_power_status, get_power_status, None)
    sys.exit(result)

if __name__ == "__main__":
    main()
