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
from keystoneclient.v3 import client as ksclient
from novaclient import client as novaclient
from keystoneclient import session as ksc_session
from keystoneclient.auth.identity import v3

def get_name_or_uuid(options):
        return options["--uuid"] if "--uuid" in options else options["--plug"]

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
        auth=v3.Password(username=username,password=password,project_name=projectname,user_domain_name=user_domain_name,project_domain_name=project_domain_name,auth_url=auth_url)
        session = ksc_session.Session(auth=auth)
        keystone = ksclient.Client(session=session)
        nova = novaclient.Client(session=session)
        return nova

def nova_run_command(options,action,timeout=None):
        username=options["--username"]
        password=options["--password"]
        projectname=options["--project-name"]
        auth_url=options["--auth-url"]
        user_domain_name=options["--user-domain-name"]
        project_domain_name=options["--project-domain-name"]
        novaclient=nova_login(username,password,projectname,auth_url,user_domain_name,project_domain_name)
        server = novaclient.servers.get(options["--uuid"])
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
        "help" : "--auth-url=[authurl]            Keystone Auth URL",
        "required" : "1",
        "shortdesc" : "Keystone Auth URL",
        "order": 1
    }
    all_opt["project-name"] = {
        "getopt" : ":",
        "longopt" : "project-name",
        "help" : "--project-name=[project]      Tenant Or Project Name",
        "required" : "1",
        "shortdesc" : "Keystone Project",
        "default": "admin",
        "order": 1
    }
    all_opt["user-domain-name"] = {
        "getopt" : ":",
        "longopt" : "user-domain-name",
        "help" : "--user-domain-name=[user-domain]      Keystone User Domain Name",
        "required" : "0",
        "shortdesc" : "Keystone User Domain Name",
        "default": "Default",
        "order": 1
    }
    all_opt["project-domain-name"] = {
        "getopt" : ":",
        "longopt" : "project-domain-name",
        "help" : "--project-domain-name=[project-domain]      Keystone Project Domain Name",
        "required" : "0",
        "shortdesc" : "Keystone Project Domain Name",
        "default": "Default",
        "order": 1
    }
    all_opt["uuid"] = {
        "getopt" : ":",
        "longopt" : "uuid",
        "help" : "--uuid=[uuid]      UUID of the nova instance",
        "required" : "1",
        "shortdesc" : "UUID of the nova instance",
        "order": 1
    }

def main():
    atexit.register(atexit_handler)

    device_opt = ["login", "passwd", "auth-url", "project-name", "user-domain-name", "project-domain-name", "uuid"]
    define_new_opts()

    options = check_input(device_opt, process_input(device_opt))

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

