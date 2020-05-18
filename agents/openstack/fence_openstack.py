#!@PYTHON@ -tt

import atexit
import logging
import os
import re
import sys
from pipes import quote
sys.path.append("/usr/share/fence")
from fencing import *
from fencing import fail_usage, is_executable, run_command, run_delay

def get_power_status(_, options):
        output = nova_run_command(options, "status")
        if (output == 'ACTIVE'):
                return 'on'
        else:
                return 'off'

def set_power_status(_, options):
    nova_run_command(options, options["--action"])
    return

def nova_login(username,password,projectname,auth_url,user_domain_name,project_domain_name):
        try:
                from novaclient import client as novaclient
                from keystoneauth1 import session as ksc_session
                from keystoneauth1 import loading
                legacy_import = False
        except ImportError:
                try:
                        from novaclient import client as novaclient
                        from keystoneclient import session as ksc_session
                        from keystoneclient.auth.identity import v3
                        legacy_import = True
                except ImportError:
                        fail_usage("Failed: Nova not found or not accessible")

        if not legacy_import:
                loader = loading.get_plugin_loader('password')
                auth = loader.load_from_options(auth_url=auth_url,
                                        username=username,
                                        password=password,
                                        project_name=projectname,
                                        user_domain_name=user_domain_name,
                                        project_domain_name=project_domain_name)
        else:
                auth = v3.Password(username=username,
                                   password=password,
                                   project_name=projectname,
                                   user_domain_name=user_domain_name,
                                   project_domain_name=project_domain_name,
                                   auth_url=auth_url)
        session = ksc_session.Session(auth=auth)
        nova = novaclient.Client("2", session=session)
        return nova

def nova_run_command(options,action,timeout=None):
        username=options["--username"]
        password=options["--password"]
        projectname=options["--project-name"]
        auth_url=options["--auth-url"]
        user_domain_name=options["--user-domain-name"]
        project_domain_name=options["--project-domain-name"]
        novaclient=nova_login(username,password,projectname,auth_url,user_domain_name,project_domain_name)
        server = novaclient.servers.get(options["--plug"])
        if action == "status":
                return server.status
        if action == "on":
                server.start()
        if action == "off":
                server.stop()
        if action == "reboot":
                server.reboot('REBOOT_HARD')

def define_new_opts():
    all_opt["auth-url"] = {
        "getopt" : ":",
        "longopt" : "auth-url",
        "help" : "--auth-url=[authurl]           Keystone Auth URL",
        "required" : "1",
        "shortdesc" : "Keystone Auth URL",
        "order": 1
    }
    all_opt["project-name"] = {
        "getopt" : ":",
        "longopt" : "project-name",
        "help" : "--project-name=[project]       Tenant Or Project Name",
        "required" : "1",
        "shortdesc" : "Keystone Project",
        "default": "admin",
        "order": 1
    }
    all_opt["user-domain-name"] = {
        "getopt" : ":",
        "longopt" : "user-domain-name",
        "help" : "--user-domain-name=[domain]    Keystone User Domain Name",
        "required" : "0",
        "shortdesc" : "Keystone User Domain Name",
        "default": "Default",
        "order": 1
    }
    all_opt["project-domain-name"] = {
        "getopt" : ":",
        "longopt" : "project-domain-name",
        "help" : "--project-domain-name=[domain] Keystone Project Domain Name",
        "required" : "0",
        "shortdesc" : "Keystone Project Domain Name",
        "default": "Default",
        "order": 1
    }
    all_opt["uuid"] = {
        "getopt" : ":",
        "longopt" : "uuid",
        "help" : "--uuid=[uuid]                  Replaced by -n, --plug",
        "required" : "0",
        "shortdesc" : "Replaced by port/-n/--plug",
        "order": 1
    }

def main():
    atexit.register(atexit_handler)

    device_opt = [  "login", "passwd", "auth-url", "project-name",
                    "user-domain-name", "project-domain-name",
                    "port", "no_port", "uuid" ]
    define_new_opts()

    all_opt["port"]["required"] = "0"
    all_opt["port"]["help"] = "-n, --plug=[UUID]              UUID of the node to be fenced"
    all_opt["port"]["shortdesc"] = "UUID of the node to be fenced."

    options = check_input(device_opt, process_input(device_opt))

    # hack to remove list/list-status actions which are not supported
    options["device_opt"] = [ o for o in options["device_opt"] if o != "separator" ]

    # workaround to avoid regressions
    if "--uuid" in options:
        options["--plug"] = options["--uuid"]
        del options["--uuid"]
    elif "--help" not in options and options["--action"] in ["off", "on", \
         "reboot", "status", "validate-all"] and "--plug" not in options:
        stop_after_error = False if options["--action"] == "validate-all" else True
        fail_usage("Failed: You have to enter plug number or machine identification", stop_after_error)

    docs = {}
    docs["shortdesc"] = "Fence agent for OpenStack's Nova service"
    docs["longdesc"] = "fence_openstack is a Fencing agent \
which can be used with machines controlled by the Openstack's Nova service. \
This agent calls the python-novaclient and it is mandatory to be installed "
    docs["vendorurl"] = "https://wiki.openstack.org/wiki/Nova"
    show_docs(options, docs)

    run_delay(options)

    result = fence_action(None, options, set_power_status, get_power_status,None)
    sys.exit(result)

if __name__ == "__main__":
    main()

