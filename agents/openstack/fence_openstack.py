#!@PYTHON@ -tt

import atexit
import logging
import sys
import os

import urllib3

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, run_delay, source_env

try:
    from novaclient import client
    from novaclient.exceptions import Conflict, NotFound
except ImportError:
    pass

urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)


def translate_status(instance_status):
    if instance_status == "ACTIVE":
        return "on"
    elif instance_status == "SHUTOFF":
        return "off"
    return "unknown"

def get_cloud(options):
    import yaml

    clouds_yaml = "~/.config/openstack/clouds.yaml"
    if not os.path.exists(os.path.expanduser(clouds_yaml)):
        clouds_yaml = "/etc/openstack/clouds.yaml"
    if not os.path.exists(os.path.expanduser(clouds_yaml)):
        fail_usage("Failed: ~/.config/openstack/clouds.yaml and /etc/openstack/clouds.yaml does not exist")

    clouds_yaml = os.path.expanduser(clouds_yaml)
    if os.path.exists(clouds_yaml):
        with open(clouds_yaml, "r") as yaml_stream:
            try:
                clouds = yaml.safe_load(yaml_stream)
            except yaml.YAMLError as exc:
                fail_usage("Failed: Unable to read: " + clouds_yaml)

    cloud = clouds.get("clouds").get(options["--cloud"])
    if not cloud:
        fail_usage("Cloud: {} not found.".format(options["--cloud"]))

    return cloud


def get_nodes_list(conn, options):
    logging.info("Running %s action", options["--action"])
    result = {}
    response = conn.servers.list(detailed=True)
    if response is not None:
        for item in response:
            instance_id = item.id
            instance_name = item.name
            instance_status = item.status
            result[instance_id] = (instance_name, translate_status(instance_status))
    return result


def get_power_status(conn, options):
    logging.info("Running %s action on %s", options["--action"], options["--plug"])
    server = None
    try:
        server = conn.servers.get(options["--plug"])
    except NotFound as e:
        fail_usage("Failed: Not Found: " + str(e))
    if server is None:
        fail_usage("Server %s not found", options["--plug"])
    state = server.status
    status = translate_status(state)
    logging.info("get_power_status: %s (state: %s)" % (status, state))
    return status


def set_power_status(conn, options):
    logging.info("Running %s action on %s", options["--action"], options["--plug"])
    action = options["--action"]
    server = None
    try:
        server = conn.servers.get(options["--plug"])
    except NotFound as e:
        fail_usage("Failed: Not Found: " + str(e))
    if server is None:
        fail_usage("Server %s not found", options["--plug"])
    if action == "on":
        logging.info("Starting instance " + server.name)
        try:
            server.start()
        except Conflict as e:
            fail_usage(e)
        logging.info("Called start API call for " + server.id)
    if action == "off":
        logging.info("Stopping instance " + server.name)
        try:
            server.stop()
        except Conflict as e:
            fail_usage(e)
        logging.info("Called stop API call for " + server.id)
    if action == "reboot":
        logging.info("Rebooting instance " + server.name)
        try:
            server.reboot("HARD")
        except Conflict as e:
            fail_usage(e)
        logging.info("Called reboot hard API call for " + server.id)


def nova_login(username, password, projectname, auth_url, user_domain_name,
               project_domain_name, ssl_insecure, cacert, apitimeout):
    legacy_import = False

    try:
        from keystoneauth1 import loading
        from keystoneauth1 import session as ksc_session
        from keystoneauth1.exceptions.discovery import DiscoveryFailure
        from keystoneauth1.exceptions.http import Unauthorized
    except ImportError:
        try:
            from keystoneclient import session as ksc_session
            from keystoneclient.auth.identity import v3

            legacy_import = True
        except ImportError:
            fail_usage("Failed: Keystone client not found or not accessible")

    if not legacy_import:
        loader = loading.get_plugin_loader("password")
        auth = loader.load_from_options(
            auth_url=auth_url,
            username=username,
            password=password,
            project_name=projectname,
            user_domain_name=user_domain_name,
            project_domain_name=project_domain_name,
        )
    else:
        auth = v3.Password(
            auth_url=auth_url,
            username=username,
            password=password,
            project_name=projectname,
            user_domain_name=user_domain_name,
            project_domain_name=project_domain_name,
            cacert=cacert,
        )

    caverify=True
    if ssl_insecure:
        caverify=False
    elif cacert:
        caverify=cacert

    session = ksc_session.Session(auth=auth, verify=caverify, timeout=apitimeout)
    nova = client.Client("2", session=session, timeout=apitimeout)
    apiversion = None
    try:
        apiversion = nova.versions.get_current()
    except DiscoveryFailure as e:
        fail_usage("Failed: Discovery Failure: " + str(e))
    except Unauthorized as e:
        fail_usage("Failed: Unauthorized: " + str(e))
    except Exception as e:
        logging.error(e)
    logging.debug("Nova version: %s", apiversion)
    return nova


def define_new_opts():
    all_opt["auth-url"] = {
        "getopt": ":",
        "longopt": "auth-url",
        "help": "--auth-url=[authurl]           Keystone Auth URL",
        "required": "0",
        "shortdesc": "Keystone Auth URL",
        "order": 2,
    }
    all_opt["project-name"] = {
        "getopt": ":",
        "longopt": "project-name",
        "help": "--project-name=[project]       Tenant Or Project Name",
        "required": "0",
        "shortdesc": "Keystone Project",
        "default": "admin",
        "order": 3,
    }
    all_opt["user-domain-name"] = {
        "getopt": ":",
        "longopt": "user-domain-name",
        "help": "--user-domain-name=[domain]    Keystone User Domain Name",
        "required": "0",
        "shortdesc": "Keystone User Domain Name",
        "default": "Default",
        "order": 4,
    }
    all_opt["project-domain-name"] = {
        "getopt": ":",
        "longopt": "project-domain-name",
        "help": "--project-domain-name=[domain] Keystone Project Domain Name",
        "required": "0",
        "shortdesc": "Keystone Project Domain Name",
        "default": "Default",
        "order": 5,
    }
    all_opt["cloud"] = {
        "getopt": ":",
        "longopt": "cloud",
        "help": "--cloud=[cloud]              Openstack cloud (from ~/.config/openstack/clouds.yaml or /etc/openstack/clouds.yaml).",
        "required": "0",
        "shortdesc": "Cloud from clouds.yaml",
        "order": 6,
    }
    all_opt["openrc"] = {
        "getopt": ":",
        "longopt": "openrc",
        "help": "--openrc=[openrc]              Path to the openrc config file",
        "required": "0",
        "shortdesc": "openrc config file",
        "order": 7,
    }
    all_opt["uuid"] = {
        "getopt": ":",
        "longopt": "uuid",
        "help": "--uuid=[uuid]                  Replaced by -n, --plug",
        "required": "0",
        "shortdesc": "Replaced by port/-n/--plug",
        "order": 8,
    }
    all_opt["cacert"] = {
        "getopt": ":",
        "longopt": "cacert",
        "help": "--cacert=[cacert]              Path to the PEM file with trusted authority certificates (override global CA trust)",
        "required": "0",
        "shortdesc": "SSL X.509 certificates file",
        "default": "",
        "order": 9,
    }
    all_opt["apitimeout"] = {
        "getopt": ":",
        "type": "second",
        "longopt": "apitimeout",
        "help": "--apitimeout=[seconds]         Timeout to use for API calls",
        "shortdesc": "Timeout in seconds to use for API calls, default is 60.",
        "required": "0",
        "default": 60,
        "order": 10,
    }


def main():
    conn = None

    device_opt = [
        "login",
        "no_login",
        "passwd",
        "no_password",
        "auth-url",
        "project-name",
        "user-domain-name",
        "project-domain-name",
        "cloud",
        "openrc",
        "port",
        "no_port",
        "uuid",
        "ssl_insecure",
        "cacert",
        "apitimeout",
    ]

    atexit.register(atexit_handler)

    define_new_opts()

    all_opt["port"]["required"] = "0"
    all_opt["port"]["help"] = "-n, --plug=[UUID]              UUID of the node to be fenced"
    all_opt["port"]["shortdesc"] = "UUID of the node to be fenced."
    all_opt["power_timeout"]["default"] = "60"

    options = check_input(device_opt, process_input(device_opt))

    # workaround to avoid regressions
    if "--uuid" in options:
        options["--plug"] = options["--uuid"]
        del options["--uuid"]
    elif ("--help" not in options
          and options["--action"] in ["off", "on", "reboot", "status", "validate-all"]
          and "--plug" not in options):
        stop_after_error = False if options["--action"] == "validate-all" else True
        fail_usage(
            "Failed: You have to enter plug number or machine identification",
            stop_after_error,
        )

    docs = {}
    docs["shortdesc"] = "Fence agent for OpenStack's Nova service"
    docs["longdesc"] = "fence_openstack is a Power Fencing agent \
which can be used with machines controlled by the Openstack's Nova service. \
This agent calls the python-novaclient and it is mandatory to be installed "
    docs["vendorurl"] = "https://wiki.openstack.org/wiki/Nova"
    show_docs(options, docs)

    run_delay(options)

    if options.get("--cloud"):
        cloud = get_cloud(options)
        username = cloud.get("auth").get("username")
        password = cloud.get("auth").get("password")
        projectname = cloud.get("auth").get("project_name")
        auth_url = None
        try:
            auth_url = cloud.get("auth").get("auth_url")
        except KeyError:
            fail_usage("Failed: You have to set the Keystone service endpoint for authorization")
        user_domain_name = cloud.get("auth").get("user_domain_name")
        project_domain_name = cloud.get("auth").get("project_domain_name")
        caverify = cloud.get("verify")
        if caverify in [True, False]:
                options["--ssl-insecure"] = caverify
        else:
                options["--cacert"] = caverify
    elif options.get("--openrc"):
        if not os.path.exists(os.path.expanduser(options["--openrc"])):
            fail_usage("Failed: {} does not exist".format(options.get("--openrc")))
        source_env(options["--openrc"])
        env = os.environ
        username = env.get("OS_USERNAME")
        password = env.get("OS_PASSWORD")
        projectname = env.get("OS_PROJECT_NAME")
        auth_url = None
        try:
            auth_url = env["OS_AUTH_URL"]
        except KeyError:
            fail_usage("Failed: You have to set the Keystone service endpoint for authorization")
        user_domain_name = env.get("OS_USER_DOMAIN_NAME")
        project_domain_name = env.get("OS_PROJECT_DOMAIN_NAME")
    else:
        username = options["--username"]
        password = options["--password"]
        projectname = options["--project-name"]
        auth_url = None
        try:
            auth_url = options["--auth-url"]
        except KeyError:
            fail_usage("Failed: You have to set the Keystone service endpoint for authorization")
        user_domain_name = options["--user-domain-name"]
        project_domain_name = options["--project-domain-name"]

    ssl_insecure = "--ssl-insecure" in options
    cacert = options["--cacert"]
    apitimeout = options["--apitimeout"]

    try:
        conn = nova_login(
            username,
            password,
            projectname,
            auth_url,
            user_domain_name,
            project_domain_name,
            ssl_insecure,
            cacert,
            apitimeout,
        )
    except Exception as e:
        fail_usage("Failed: Unable to connect to Nova: " + str(e))

    # Operate the fencing device
    result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
    sys.exit(result)


if __name__ == "__main__":
    main()
