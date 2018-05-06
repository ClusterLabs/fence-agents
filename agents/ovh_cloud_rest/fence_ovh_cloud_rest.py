#!@PYTHON@ -tt

import sys
import time
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, run_command, run_delay
import ovh

POLL_INTERVAL_SECONDS = 1

def define_new_opts():
    all_opt["application_key"] = {
            "getopt" : "k:",
            "longopt" : "application-key",
            "help" : "-k, --application-key=[application-key]               OVH Oauth application key",
            "required" : "1",
            "shortdesc" : "OVH Oauth application key",
            "order" : 1}
    all_opt["application_secret"] = {
            "getopt" : "s:",
            "longopt" : "application-secret",
            "help" : "-s, --application-secret=[application-secret]         OVH Oauth application secret",
            "required" : "1",
            "shortdesc" : "OVH Oauth application secret",
            "order" : 2}
    all_opt["token"] = {
            "getopt" : "t:",
            "longopt" : "token",
            "help" : "-t, --token=[token]                                   OVH Oauth token ",
            "required" : "1",
            "shortdesc" : "OVH Oauth token ",
            "order" : 3}
    all_opt["region"] = {
            "getopt" : "r:",
            "longopt" : "region",
            "help" : "-r, --region=[region]                                 OVH region (example: ovh-ca)",
            "required" : "1",
            "shortdesc" : "OVH region",
            "order" : 4}
    all_opt["service_name"] = {
            "getopt" : "n:",
            "longopt" : "service-name",
            "help" : "-n, --service-name=[service-name]                     OVH service name",
            "required" : "1",
            "shortdesc" : "OVH service name",
            "order" : 5}
    all_opt["instance_id"] = {
            "getopt" : "i:",
            "longopt" : "instance-id",
            "help" : "-i, --instance-id=[instance-id]                       OVH instance id",
            "required" : "1",
            "shortdesc" : "OVH service name",
            "order" : 6}

def ovh_login(options):
    session = ovh.Client(
        endpoint=options["--region"],
        application_key=options["--application-key"],
        application_secret=options["--application-secret"],
        consumer_key=options["--token"],
    )
    options["session"] = session;
    return session;

def status(options, expected_status):
    session = options["session"]
    status_url = "/cloud/project/%s/instance/%s" % (options['--service-name'], options['--instance-id'])
    response = session.get(status_url)
    return True if response["status"] == expected_status else False

def main():
    atexit.register(atexit_handler)

    device_opt = ["application_key", "application_secret", "token", "region", "service_name", "instance_id", "no_password"]

    define_new_opts()
    options = check_input(device_opt, process_input(device_opt), other_conditions=True)

    docs = {}
    docs["shortdesc"] = "Fence agent for OVH Cloud (REST API)"
    docs["longdesc"] = "Fence agent for OVH Cloud (REST API) with authentication via Oauth"
    docs["vendorurl"] = "https://api.ovh.com/"
    show_docs(options, docs)

    run_delay(options)

    session = ovh_login(options);

    if options["--action"] == "off":
        try:
            url = "/cloud/project/%s/instance/%s/rescueMode" % (options['--service-name'], options['--instance-id'])
            response = session.post(url, rescue=True)
            if response["adminPassword"] != None:
                result = 1
            while not status(options, "RESCUE"):
                time.sleep(POLL_INTERVAL_SECONDS)
        except Exception as exception:
            print(exception)
            result = 0

    if options["--action"] == "on":
        try:
            url = "/cloud/project/%s/instance/%s/rescueMode" % (options['--service-name'], options['--instance-id'])
            response = session.post(url, rescue=False)
            if response["adminPassword"] == None:
                result = 1
            while not status(options, "ACTIVE"):
                time.sleep(POLL_INTERVAL_SECONDS)
        except Exception as exception:
            print(exception)
            result = 0

    sys.exit(result)

if __name__ == "__main__":
	main()
