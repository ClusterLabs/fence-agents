#!@PYTHON@ -tt

import sys, re, pexpect
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay

def get_nodes_list(compute_client, options):
    result = {}
    if compute_client:
        rgName = options["--resourceGroup"]
        vms = compute_client.virtual_machines.list(rgName)
        try:
            for vm in vms:
                result[vm.name] = ("", None)
        except Exception as e:
            fail_usage("Failed: %s" % e)

    return result

def get_power_status(compute_client, options):
    logging.info("getting power status for VM " + options["--plug"])

    if compute_client:
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]

        powerState = "unknown"
        try:
            vmStatus = compute_client.virtual_machines.get(rgName, vmName, "instanceView")
        except Exception as e:
            fail_usage("Failed: %s" % e)
        for status in vmStatus.instance_view.statuses:
            if status.code.startswith("PowerState"):
                powerState = status.code
                break

        logging.info("Found power state of VM: " + powerState)
        if powerState == "PowerState/running":
            return "on"

    return "off"

def set_power_status(compute_client, options):
    logging.info("setting power status for VM " + options["--plug"] + " to " + options["--action"])

    if compute_client:
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]

        if (options["--action"]=="off"):
            logging.info("Deallocating " + vmName + "in resource group " + rgName)
            compute_client.virtual_machines.deallocate(rgName, vmName)
        elif (options["--action"]=="on"):
            logging.info("Starting " + vmName + "in resource group " + rgName)
            compute_client.virtual_machines.start(rgName, vmName)


def define_new_opts():
    all_opt["resourceGroup"] = {
        "getopt" : ":",
        "longopt" : "resourceGroup",
        "help" : "--resourceGroup=[name]         Name of the resource group",
        "shortdesc" : "Name of resource group.",
        "required" : "1",
        "order" : 2
    }
    all_opt["tenantId"] = {
        "getopt" : ":",
        "longopt" : "tenantId",
        "help" : "--tenantId=[name]              Id of the Azure Active Directory tenant",
        "shortdesc" : "Id of Azure Active Directory tenant.",
        "required" : "1",
        "order" : 3
    }
    all_opt["subscriptionId"] = {
        "getopt" : ":",
        "longopt" : "subscriptionId",
        "help" : "--subscriptionId=[name]        Id of the Azure subscription",
        "shortdesc" : "Id of the Azure subscription.",
        "required" : "1",
        "order" : 4
    }

# Main agent method
def main():
    compute_client = None

    device_opt = ["resourceGroup", "login", "passwd", "tenantId", "subscriptionId","port"]

    atexit.register(atexit_handler)

    define_new_opts()

    all_opt["power_timeout"]["default"] = "150"

    all_opt["login"]["help"] = "-l, --username=[appid]         Application ID"
    all_opt["passwd"]["help"] = "-p, --password=[authkey]       Authentication key"

    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence agent for Azure Resource Manager"
    docs["longdesc"] = "Used to deallocate virtual machines and to report power state of virtual machines running in Azure. It uses Azure SDK for Python to connect to Azure.\
\n.P\n\
For instructions to setup credentials see: https://docs.microsoft.com/en-us/azure/azure-resource-manager/resource-group-create-service-principal-portal\
\n.P\n\
Username and password are application ID and authentication key from \"App registrations\"."
    docs["vendorurl"] = "http://www.microsoft.com"
    show_docs(options, docs)

    run_delay(options)

    try:
        from azure.common.credentials import ServicePrincipalCredentials
        from azure.mgmt.compute import ComputeManagementClient

        tenantid = options["--tenantId"]
        servicePrincipal = options["--username"]
        spPassword = options["--password"]
        subscriptionId = options["--subscriptionId"]
        credentials = ServicePrincipalCredentials(
            client_id = servicePrincipal,
            secret = spPassword,
            tenant = tenantid
        )
        compute_client = ComputeManagementClient(
            credentials,
            subscriptionId
        )
    except ImportError:
        fail_usage("Azure Resource Manager Python SDK not found or not accessible")
    except Exception as e:
        fail_usage("Failed: %s" % re.sub("^, ", "", str(e)))

    # Operate the fencing device
    result = fence_action(compute_client, options, set_power_status, get_power_status, get_nodes_list)
    sys.exit(result)

if __name__ == "__main__":
    main()
