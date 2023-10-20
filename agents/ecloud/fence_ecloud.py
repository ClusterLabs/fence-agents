#!@PYTHON@ -tt
#
# Fence agent for eCloud and eCloud VPC
# https://www.ans.co.uk/cloud-and-infrastructure/ecloud/
#
# Copyright (c) 2022 ANS Group Limited
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see
# <http://www.gnu.org/licenses/>.

import sys
import time
import atexit
import logging
import requests
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import run_delay, fail_usage, fail, EC_TIMED_OUT

API_BASE = "https://api.ukfast.io/ecloud"
API_MONITOR = API_BASE + "/ping"
API_VPC_INSTANCE_DATA = API_BASE + "/v2/instances/:ID"
API_VPC_POWER_ON = API_BASE + "/v2/instances/:ID/power-on"
API_VPC_POWER_OFF = API_BASE + "/v2/instances/:ID/power-off"
API_V1_INSTANCE_DATA = API_BASE + "/v1/vms/:ID"
API_V1_POWER_ON = API_BASE + "/v1/vms/:ID/power-on"
API_V1_POWER_OFF = API_BASE + "/v1/vms/:ID/power-off"


def set_power_fn(conn, options):
    logging.debug("setting power {}".format(options['--action']))
    del conn

    action = options['--action']
    vpc = options['--ecloud-vpc']
    plug = options['--plug']

    url = fence_url(vpc, action, plug)
    hdrs = headers(options['--apikey'])

    logging.info("executing '{}' action on '{}'".format(action, plug))

    retries = 0
    while True:
        resp = requests.put(url, headers=hdrs)
        if resp.status_code == 409:
            # If we attempt to power the instance back on too soon after powering it off,
            # e.g. during a reboot, the API will return a 409 because while the power status
            # has changed, the task is still executing. Retry the action until we exceed
            # retries or get a different status code.
            if retries >= 6:
                logging.error("timed out trying to execute '{}' action after repeated 409 codes from API", action)
                fail(EC_TIMED_OUT)

            time.sleep(2)
            retries += 1
            continue

        if resp.status_code != 202:
            logging.error("unexpected status code '{}' from endpoint '{}': {}".format(
                resp.status_code, url, resp.text
            ))
            
        break


def get_power_fn(conn, options):
    logging.debug("getting power state")
    del conn

    vpc = options['--ecloud-vpc']
    plug = options['--plug']

    url = instance_data_url(vpc, plug)
    hdrs = headers(options['--apikey'])

    resp = requests.get(url, headers=hdrs)
    if resp.status_code != 200:
        logging.error("unexpected status code ('{}') from endpoint '{}': {}".format(
            resp.status_code, url, resp.text
        ))
        return "bad status {}".format(resp.status_code)

    instance = resp.json()['data']
    if vpc:
        logging.debug("power state return value: {}".format(instance['online']))
        return "on" if instance['online'] else "off"
    else:
        if instance['power_status'] == "Online":
            return "on"
        elif instance['power_status'] == "Offline":
            return "off"
        else:
            # Could be 'Unknown' or other value
            return instance['power_status']


def headers(apikey):
    return {
        "Authorization": apikey,
        "User-Agent": "fence_ecloud"
    }


def itp(url, plug):
    return url.replace(':ID', plug)


def fence_url(vpc, action, plug):
    if action == "on":
        return itp(API_VPC_POWER_ON, plug) if vpc else itp(API_V1_POWER_ON, plug)
    if action == "off":
        return itp(API_VPC_POWER_OFF, plug) if vpc else itp(API_V1_POWER_OFF, plug)
    
    fail_usage("no available API configured for action '{}'".format(action))


def instance_data_url(vpc, plug):
    return itp(API_VPC_INSTANCE_DATA, plug) if vpc else itp(API_V1_INSTANCE_DATA, plug)


def main():
    device_opt = ["apikey", "port", "no_login", "no_password"]

    all_opt["apikey"] = {
        "getopt": ":",
        "longopt": "apikey",
        "help": "--apikey=[key]                 eCloud API Key",
        "required": "1",
        "shortdesc": "API Key",
        "order": 0,
    }
    all_opt["port"]["help"] = "-n, --plug=[instance]          Instance ID (VPC) or server ID (v1)"

    atexit.register(atexit_handler)

    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence Agent for ANS eCloud"
    docs["longdesc"] = "fence_ecloud is a Power Fencing agent for use with the ANS \
eCloud platform which is compatible with eCloud VPC and eCloud v1."
    docs["vendorurl"] = "https://www.ans.co.uk"
    show_docs(options, docs)

    if options['--action'] in ['on', 'off', 'reboot', 'status']:
        plug = options['--plug']

        options['--ecloud-vpc'] = True
        if not plug.startswith("i-"):
            options['--ecloud-vpc'] = False

    run_delay(options)
    fence_action(None, options, set_power_fn, get_power_fn)


if __name__ == '__main__':
    main()
