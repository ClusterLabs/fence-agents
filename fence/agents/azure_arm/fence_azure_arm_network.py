#!@PYTHON@ -tt

import sys, re, pexpect
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay
import time
import azure_fence_lib

#import ptvsd

def get_azure_config(options):
    config = azure_fence_lib.AzureConfiguration()

    config.RGName = options.get("--resourceGroup")
    config.VMName = options.get("--plug")
    config.SubscriptionId = options.get("--subscriptionId")    
    config.Cloud = options.get("--cloud")
    config.UseMSI = options.get("--useMSI")
    config.Tenantid = options.get("--tenantId")
    config.ApplicationId = options.get("--username")
    config.ApplicationKey = options.get("--password")
    config.Verbose = options.get("--verbose") 
    
    return config

def get_nodes_list(clients, options):
    logging.info("{get_nodes_list}")
    result = {}
    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        logging.info("{get_nodes_list} listing virtual machines")
        vms = compute_client.virtual_machines.list(rgName)
        logging.info("{get_nodes_list} listing virtual machines done")
        try:
            for vm in vms:
                allOk = True

                for nicRef in vm.network_profile.network_interfaces:
                    logging.info("{get_nodes_list} testing network interface %s" % nicRef.id)

                    nicresource = azure_fence_lib.get_azure_resource(nicRef.id)
                    nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)
                    if nic.ip_configurations:
                        for ipConfig in nic.ip_configurations:
                            logging.info("{get_nodes_list} testing network interface ip config")
                            fenceSubnet = azure_fence_lib.get_fence_subnet_for_config(ipConfig, network_client)
                            testOk = azure_fence_lib.test_fence_subnet(fenceSubnet, nic, network_client)
                            if not testOk:
                                allOk = False

                if allOk:
                    logging.info("{get_nodes_list} Virtual machine %s can be fenced" % vm.name)
                    result[vm.name] = ("", None)
                
        except Exception as e:
            fail_usage("{get_nodes_list} Failed: %s" % e)
    else:
        fail_usage("{get_nodes_list} No Azure clients configured. Contact support")

    return result

def get_power_status(clients, options):
    logging.info("{get_power_status} getting power status for VM %s" % (options["--plug"]))
    result = azure_fence_lib.FENCE_STATE_ON

    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]
        
        result = azure_fence_lib.get_power_status_impl(compute_client, network_client, rgName, vmName)
    else:
        fail_usage("{get_power_status} No Azure clients configured. Contact support")
    
    logging.info("{get_power_status} result is %s" % result)
    return result

def set_power_status(clients, options):
    logging.info("{set_power_status} setting power status for VM " + options["--plug"] + " to " + options["--action"])

    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]
        try:        
            if (options["--action"]=="off"):
                azure_fence_lib.set_power_status_off(compute_client, network_client, rgName, vmName)
            elif (options["--action"]=="on"):
                azure_fence_lib.set_power_status_on(compute_client, network_client, rgName, vmName)
        except Exception as e:
            fail_usage("Failed: %s" % e)
    else:
        fail_usage("No Azure clients configured. Contact support")

    logging.info("{set_power_status} done")

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
        "required" : "0",
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
    all_opt["useMSI"] = {
        "getopt" : ":",
        "longopt" : "useMSI",
        "help" : "--useMSI=[value]        Determines if Managed Service Identity should be used instead of username and password. If this parameter is specified, parameters tenantId, login and passwd are not allowed.",
        "shortdesc" : "Determines if Managed Service Identity should be used.",
        "required" : "0",
        "order" : 5
    }
    all_opt["cloud"] = {
        "getopt" : ":",
        "longopt" : "cloud",
        "help" : "--cloud=[value]        Name of the cloud you want to use. Supported values are china, germany or usgov. Do not use this parameter if you want to use public Azure",
        "shortdesc" : "Name of the cloud you want to use.",
        "required" : "0",
        "order" : 6
    }

# Main agent method
def main():
    logging.getLogger().setLevel(logging.INFO)
    # handler = logging.StreamHandler(sys.stdout)
    # handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',datefmt='%a, %d %b %Y %H:%M:%S'))
    # logging.getLogger().addHandler(handler)
    compute_client = None
    network_client = None
    device_opt = None
    credentials = None

    atexit.register(atexit_handler)

    define_new_opts()

    all_opt["power_timeout"]["default"] = "150"

    all_opt["login"]["help"] = "-l, --username=[appid]         Application ID"
    all_opt["passwd"]["help"] = "-p, --password=[authkey]       Authentication key"

    msi_opt = ["resourceGroup","subscriptionId","port","useMSI","login","passwd","tenantId","cloud","no_login","no_password"]
    msiOptions = process_input(msi_opt)

    if "--action" in msiOptions and (msiOptions["--action"] == "meta-data" or msiOptions["--action"] == "metadata"):
        logging.info("{main} Checking params metadata")
        device_opt = msi_opt
    elif "--useMSI" in msiOptions:
        logging.info("{main} Checking params MSI")
        device_opt = ["resourceGroup", "subscriptionId","port","useMSI","no_login","no_password"]
    else:
        logging.info("{main} Checking params Service Principal")
        device_opt = ["resourceGroup", "login", "passwd", "tenantId", "subscriptionId","port","cloud"]

    options = check_input(device_opt, msiOptions)

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
        #if options["--action"] != "metadata":
        #    ptvsd.enable_attach('my_secret')
        #    ptvsd.wait_for_attach()
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.network import NetworkManagementClient        

        config = get_azure_config(options)

        compute_client = azure_fence_lib.get_azure_compute_client(config)
        network_client = azure_fence_lib.get_azure_network_client(config)
    
    except ImportError as ie:
        fail_usage("Azure Resource Manager Python SDK not found or not accessible: %s" % re.sub("^, ", "", str(ie)))
    except Exception as e:
        fail_usage("Failed: %s" % re.sub("^, ", "", str(e)))

    # Operate the fencing device
    result = fence_action([compute_client,network_client], options, set_power_status, get_power_status, get_nodes_list)
    sys.exit(result)

if __name__ == "__main__":
    main()
