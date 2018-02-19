#!@PYTHON@ -tt

import sys, re, pexpect
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay
import time

FENCE_SUBNET_NAME = "fence-subnet"
FENCE_INBOUND_RULE_NAME = "FENCE_DENY_ALL_INBOUND"
FENCE_INBOUND_RULE_DIRECTION = "Inbound"
FENCE_OUTBOUND_RULE_NAME = "FENCE_DENY_ALL_OUTBOUND"
FENCE_OUTBOUND_RULE_DIRECTION = "Outbound"
VM_STATE_POWER_PREFIX = "PowerState"
VM_STATE_POWER_DEALLOCATED = "deallocated"
VM_STATE_POWER_STOPPED = "stopped"
FENCE_STATE_OFF = "off"
FENCE_STATE_ON = "on"
TAG_SUBNET_ID = "FENCE_TAG_SUBNET_ID"
TAG_IP_TYPE = "FENCE_TAG_IP_TYPE"
TAG_IP = "FENCE_TAG_IP"

class AzureSubResource:
    Type = None
    Name = None

class AzureResource:
    Id = None
    SubscriptionId = None
    ResourceGroupName = None
    ResourceName = None
    SubResources = []

def get_azure_resource(id):
    match = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?(/([^/]*)/([^/]*))?', id)
    resource = AzureResource()
    resource.Id = id
    resource.SubscriptionId = match.group(2)
    resource.ResourceGroupName = match.group(3)
    resource.ResourceName = match.group(6)
    i = 7
    while i < len(match.groups):
        subRes = AzureSubResource()
        subRes.Type = match.group(i + 1)
        subRes.Name = match.group(i + 2)
        resource.SubResources.append(subRes)
        i += 3

    return resource

# get_fence_subnet(nicId, network_client):
#     nicresource = get_azure_resource(nicId)
#     nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)
#     if nic.ip_configurations:
#         for ipConfig in nic.ip_configurations:                                
#             subnetResource = get_azure_resource(ipConfig.subnet.id)
#             vnet = network_client.virtual_networks.get(subnetResource.ResourceGroupName, subnetResource.ResourceName)
#             for avSubnet in vnet.subnets:
#                 if (avSubnet.name == FENCE_SUBNET_NAME):                    
#                         return avSubnet
#     return None

def get_fence_subnet_for_config(ipConfig, network_client):
    subnetResource = get_azure_resource(ipConfig.subnet.id)
    logging.info("{get_fence_subnet_for_config} testing virtual network %s in resource group %s for a fence subnet" %(subnetResource.ResourceName, subnetResource.ResourceGroupName))
    vnet = network_client.virtual_networks.get(subnetResource.ResourceGroupName, subnetResource.ResourceName)
    return get_subnet(vnet, FENCE_SUBNET_NAME)

def get_subnet(vnet, subnetName):
    for avSubnet in vnet.subnets:
        logging.info("{get_subnet} searching subnet %s testing subnet %s" % (subnetName, avSubnet.name))
        if (avSubnet.name.lower() == subnetName.lower()):
                logging.info("{get_subnet} subnet %s found" % subnetName)
                return avSubnet

def test_fence_subnet(fenceSubnet, nic, network_client):
    logging.info("{test_fence_subnet}")
    testOk = True
    if not fenceSubnet:
        testOk = False
        logging.info("{test_fence_subnet} No fence subnet found for virtual network of network interface %s" % nic.id)
    else:
        if not fenceSubnet.network_security_group:
            testOk = False
            logging.info("{test_fence_subnet} Fence subnet %s has not network security group" % fenceSubnet.id)
        else:
            nsgResource = get_azure_resource(fenceSubnet.network_security_group.id)
            logging.info("{test_fence_subnet} Getting network security group %s in resource group %s" % (nsgResource.ResourceName, nsgResource.ResourceGroupName))
            nsg = network_client.network_security_groups.get(nsgResource.ResourceGroupName, nsgResource.ResourceName)
            inboundRule = get_inbound_rule_for_nsg(nsg)
            outboundRule = get_outbound_rule_for_nsg(nsg)
            if not outboundRule:
                testOk = False
                logging.info("{test_fence_subnet} Network Securiy Group %s of fence subnet %s has no outbound security rule that blocks all traffic" % (nsgResource.ResourceName, fenceSubnet.id))
            elif not inboundRule:
                testOk = False
                logging.info("{test_fence_subnet} Network Securiy Group %s of fence subnet %s has no inbound security rule that blocks all traffic" % (nsgResource.ResourceName, fenceSubnet.id))
    
    return testOk


def get_inbound_rule_for_nsg(nsg):
    return get_rule_for_nsg(nsg, FENCE_INBOUND_RULE_NAME, FENCE_INBOUND_RULE_DIRECTION)

def get_outbound_rule_for_nsg(nsg):
    return get_rule_for_nsg(nsg, FENCE_OUTBOUND_RULE_NAME, FENCE_OUTBOUND_RULE_DIRECTION)

def get_rule_for_nsg(nsg, ruleName, direction):
    logging.info("{get_rule_for_nsg} Looking for security rule %s with direction %s" % (ruleName, direction))
    if not nsg:
        logging.info("{get_rule_for_nsg} Network security group not set")
        return None

    for rule in nsg.security_rules:
        logging.info("{get_rule_for_nsg} Testing a %s securiy rule %s" % (rule.direction, rule.name))
        if (rule.access == "Deny") and (rule.direction == direction)  \
                and (rule.source_port_range == "*") and (rule.destination_port_range == "*") \
                and (rule.protocol == "*") and (rule.destination_address_prefix == "*") \
                and (rule.source_address_prefix == "*") and (rule.provisioning_state == "Succeeded") \
                and (rule.priority == 100) and (rule.name == ruleName):
            logging.info("{get_rule_for_nsg} %s rule found" % direction)
            return rule

    return None

def get_vm_state(vm, prefix):
    for status in vm.instance_view.statuses:
        if status.code.startswith(prefix):
            return status.code.replace(prefix + "/", "").lower()

    return None

def get_vm_power_state(vm):
    return get_vm_state(vm, VM_STATE_POWER_PREFIX)

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

                    nicresource = get_azure_resource(nicRef.id)
                    nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)
                    if nic.ip_configurations:
                        for ipConfig in nic.ip_configurations:
                            logging.info("{get_nodes_list} testing network interface ip config")
                            fenceSubnet = get_fence_subnet_for_config(ipConfig, network_client)
                            testOk = test_fence_subnet(fenceSubnet, nic, network_client)
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
    result = FENCE_STATE_ON

    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]
        
        try:
            logging.info("{get_power_status} Testing VM state")            
            vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")
            powerState = get_vm_power_state(vm)            
            if powerState == VM_STATE_POWER_DEALLOCATED:
                return FENCE_STATE_OFF
            if powerState == VM_STATE_POWER_STOPPED:
                return FENCE_STATE_OFF
            
            allNICOK = True
            for nicRef in vm.network_profile.network_interfaces:
                nicresource = get_azure_resource(nicRef.id)
                nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)
                for ipConfig in nic.ip_configurations: 
                    fenceSubnet = get_fence_subnet_for_config(ipConfig, network_client)
                    testOk = test_fence_subnet(fenceSubnet, nic, network_client)
                    if not testOk:
                        allNICOK = False
                    elif fenceSubnet.id != ipConfig.subnet.id:            
                        allNICOK = False
            if allNICOK:
                logging.info("{get_power_status} All IP configurations of all network interfaces are in the fence subnet. Declaring VM as off")
                result = FENCE_STATE_OFF
        except Exception as e:
            fail_usage("{get_power_status} Failed: %s" % e)        
    else:
        fail_usage("{get_power_status} No Azure clients configured. Contact support")
    
    logging.info("{get_power_status} result is %s" % result)
    return result

def set_power_status(clients, options):
    from azure.mgmt.network.models import SecurityRule
    logging.info("{set_power_status} setting power status for VM " + options["--plug"] + " to " + options["--action"])

    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]
        try:
        
            if (options["--action"]=="off"):
                logging.info("{set_power_status} Fencing %s in resource group %s" % (vmName, rgName))
                          
                vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")
                
                operations = []
                for nicRef in vm.network_profile.network_interfaces:
                    nicresource = get_azure_resource(nicRef.id)
                    nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)
                    for ipConfig in nic.ip_configurations: 
                        fenceSubnet = get_fence_subnet_for_config(ipConfig, network_client)
                        testOk = test_fence_subnet(fenceSubnet, nic, network_client)
                        if testOk:
                            logging.info("{set_power_status} Changing subnet of ip config of nic %s" % nic.id)
                            ipConfig.subnet = fenceSubnet                
                        else:            
                            fail_usage("{get_power_status} Network interface id %s does not have a network security group." % nic.id)
                    
                    op = network_client.network_interfaces.create_or_update(nicresource.ResourceGroupName, nicresource.ResourceName, nic)
                    operations.append(op)

                iCount = 1
                for waitOp in operations:
                    logging.info("{set_power_status} Waiting for network update operation (%s/%s)" % (iCount, len(operations)))
                    iCount += 1
                    waitOp.wait()

            elif (options["--action"]=="on"):
                logging.info("{set_power_status} Unfencing %s in resource group %s" % (vmName, rgName))
                          
                vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")
                
                operations = []
                for nicRef in vm.network_profile.network_interfaces:
                    nicresource = get_azure_resource(nicRef.id)
                    nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)
                    logging.info("{set_power_status} Searching for tags required to unfence this virtual machine")                    
                    for ipConfig in nic.ip_configurations:
                        subnetId = None
                        ipType = None
                        ipAddress = None
                        
                        for tagKey in nic.tags.keys():
                            if (tagKey.startswith(FENCE_TAG_SUBNET_ID)):
                                subnetId = nic.tags.get(tagKey).replace(FENCE_TAG_SUBNET_ID, "")
                            elif (tagKey.startswith(FENCE_TAG_IP_TYPE)):
                                ipType = nic.tags.get(tagKey).replace(FENCE_TAG_IP_TYPE, "")
                            elif (tagKey.startswith(FENCE_TAG_IP)):
                                ipAddress = nic.tags.get(tagKey).replace(FENCE_TAG_IP, "")

                        if (subnetId and ipType and ipAddress):
                            subnetResource = get_azure_resource(subnetId)
                            vnet = network_client.virtual_networks.get(subnetResource.ResourceGroupName, subnetResource.ResourceName)                            
                            oldSubnet = get_subnet(vnet, subnetResource.SubResources[0].ResourceName)
                            ipConfig.subnet = oldSubnet
                            ipConfig.private_ip_address = ipAddress
                            ipConfig.private_ip_allocation_method = ipType
                    
                    op = network_client.network_interfaces.create_or_update(nicresource.ResourceGroupName, nicresource.ResourceName, nic)
                    operations.append(op)

                iCount = 1
                for waitOp in operations:
                    logging.info("{set_power_status} Waiting for network update operation (%s/%s)" % (iCount, len(operations)))
                    iCount += 1
                    waitOp.wait()

        except Exception as e:
            fail_usage("Failed: %s" % e)      
    else:
        fail_usage("No Azure clients configured. Contact support")

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

    msi_opt = ["resourceGroup","subscriptionId","port","useMSI","login","passwd","tenantId","cloud"]
    msiOptions = process_input(msi_opt)

    if "--useMSI" in msiOptions:
        device_opt = ["resourceGroup", "subscriptionId","port","useMSI","no_login","no_password"]
    else:
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
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.network import NetworkManagementClient        

        cloud_environment = None
        if "--cloud" in options:                
            cloud = options["--cloud"]
            logging.info("Cloud parameter %s provided." % (cloud))

                
            if (cloud.lower() == "china"):
                from msrestazure.azure_cloud import AZURE_CHINA_CLOUD
                cloud_environment = AZURE_CHINA_CLOUD
            elif (cloud.lower() == "germany"):
                from msrestazure.azure_cloud import AZURE_GERMAN_CLOUD
                cloud_environment = AZURE_GERMAN_CLOUD
            elif (cloud.lower() == "usgov"):
                from msrestazure.azure_cloud import AZURE_US_GOV_CLOUD
                cloud_environment = AZURE_US_GOV_CLOUD
            else:
                fail_usage("Value %s for cloud parameter not supported. Supported values are china, germany and usgov" % cloud)

        if ("--useMSI" in options) and (options["--useMSI"] == "1"):
            from msrestazure.azure_active_directory import MSIAuthentication
            if cloud_environment:
                credentials = MSIAuthentication(cloud_environment=cloud_environment)
            else:
                credentials = MSIAuthentication()
        else:
            from azure.common.credentials import ServicePrincipalCredentials
            tenantid = options["--tenantId"]
            servicePrincipal = options["--username"]
            spPassword = options["--password"]         
            
            if cloud_environment:
                credentials = ServicePrincipalCredentials(
                    client_id = servicePrincipal,
                    secret = spPassword,
                    tenant = tenantid,
                    cloud_environment=cloud_environment
                )
            else:
                credentials = ServicePrincipalCredentials(
                    client_id = servicePrincipal,
                    secret = spPassword,
                    tenant = tenantid
                )
        

        subscriptionId = options["--subscriptionId"]
        if cloud_environment:
            compute_client = ComputeManagementClient(
                credentials,
                subscriptionId,
                base_url=cloud_environment.endpoints.resource_manager
            )
            network_client = NetworkManagementClient(
                credentials,
                subscriptionId,
                base_url=cloud_environment.endpoints.resource_manager
            )
        else:
            compute_client = ComputeManagementClient(
                credentials,
                subscriptionId
            )
            network_client = NetworkManagementClient(
                credentials,
                subscriptionId
            )
    
    except ImportError as ie:
        fail_usage("Azure Resource Manager Python SDK not found or not accessible: %s" % re.sub("^, ", "", str(ie)))
    except Exception as e:
        fail_usage("Failed: %s" % re.sub("^, ", "", str(e)))

    # Operate the fencing device
    result = fence_action([compute_client,network_client], options, set_power_status, get_power_status, get_nodes_list)
    sys.exit(result)

if __name__ == "__main__":
    main()
