#!@PYTHON@ -tt

import sys, re, pexpect
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_TIMED_OUT, run_delay
import time

def get_nodes_list(clients, options):
    result = {}
    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        vms = compute_client.virtual_machines.list(rgName)
        try:
            for vm in vms:
                for nic in vm.network_profile.network_interfaces:
                    match = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.id)
                    if match:
                        nic = network_client.network_interfaces.get(match.group(3), match.group(6))
                        if nic.network_security_group:
                            
                            nsgmatch = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.network_security_group.id)
                            if nsgmatch:

                                nsg = network_client.network_security_groups.get(nsgmatch.group(3), nsgmatch.group(6))                                
                                if len(nsg.network_interfaces) == 1 and ((not nsg.subnets) or len(nsg.subnets) == 0):
                                    result[vm.name] = ("", None)
                                elif len(nsg.network_interfaces) != 1:
                                    logging.warn("Network security group %s of network interface %s is used by multiple network interfaces. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))
                                else:
                                    logging.warn("Network security group %s of network interface %s is also used by a subnet. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))
                            else:
                                fail_usage("Network Security Group id %s could not be parsed. Contact support" % nic.network_security_group.id)
                        else:
                            logging.warn("Network interface %s does not have a Network Security Group that could be used to fence the node. \
Make sure that every network interface has a network security group" % nic.id)
                    else:
                        fail_usage("Network interface id %s could not be parsed. Contact support" % nic.id)
                
        except Exception as e:
            fail_usage("Failed: %s" % e)
    else:
        fail_usage("No Azure clients configured. Contact support")

    return result

def get_power_status(clients, options):
    logging.info("getting power status for VM %s" % (options["--plug"]))
    result = "on"

    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]
        
        try:
            logging.info("Testing VM state")
            powerState = "unknown"
            vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")
            for status in vm.instance_view.statuses:
                if status.code.startswith("PowerState"):
                    powerState = status.code
                    break
            if powerState == "PowerState/deallocated":
                return "off"
            if powerState == "PowerState/stopped":
                return "off"
            
            allNICOK = True
            for nic in vm.network_profile.network_interfaces:
                match = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.id)
                
                if match:
                    logging.info("Getting network interface.")
                    nic = network_client.network_interfaces.get(match.group(3), match.group(6))
                    logging.info("Getting network interface done.")
                    if nic.network_security_group:
                        nsgmatch = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.network_security_group.id)
                        if nsgmatch:
                            logging.info("Getting NSG.")
                            nsg = network_client.network_security_groups.get(nsgmatch.group(3), nsgmatch.group(6))                                
                            logging.info("Getting NSG done.")

                            if len(nsg.network_interfaces) == 1 and ((not nsg.subnets) or len(nsg.subnets) == 0):
                                inboundOk = False
                                outboundOk = False
                                for rule in nsg.security_rules:                                    
                                    if (rule.access == "Deny") and (rule.direction == "Inbound")  \
                                        and (rule.source_port_range == "*") and (rule.destination_port_range == "*") \
                                        and (rule.protocol == "*") and (rule.destination_address_prefix == "*") \
                                        and (rule.source_address_prefix == "*") and (rule.provisioning_state == "Succeeded") \
                                        and (rule.priority == 100):
                                        logging.info("Inbound rule found.")
                                        inboundOk = True
                                    elif (rule.access == "Deny") and (rule.direction == "Outbound")  \
                                        and (rule.source_port_range == "*") and (rule.destination_port_range == "*") \
                                        and (rule.protocol == "*") and (rule.destination_address_prefix == "*") \
                                        and (rule.source_address_prefix == "*") and (rule.provisioning_state == "Succeeded") \
                                        and (rule.priority == 100):
                                        logging.info("Outbound rule found.")
                                        outboundOk = True
                                
                                nicOK = outboundOk and inboundOk
                                allNICOK = allNICOK & nicOK

                            elif len(nsg.network_interfaces) != 1:
                                fail_usage("Network security group %s of network interface %s is used by multiple network interfaces. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))
                            else:
                                fail_usage("Network security group %s of network interface %s is also used by a subnet. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))                        
                        else:
                            fail_usage("Network Security Group id %s could not be parsed. Contact support" % nic.network_security_group.id)
                    else:            
                        fail_usage("Network interface id %s does not have a network security group." % nic.id)
                else:
                    fail_usage("Network interface id %s could not be parsed. Contact support" % nic.id)
        except Exception as e:
            fail_usage("Failed: %s" % e)
        if allNICOK:
            logging.info("All network interface have inbound and outbound deny all rules. Declaring VM as off")
            result = "off"
    else:
        fail_usage("No Azure clients configured. Contact support")
    
    return result

def set_power_status(clients, options):        
    logging.info("setting power status for VM " + options["--plug"] + " to " + options["--action"])

    if clients:
        compute_client = clients[0]
        network_client = clients[1]
        rgName = options["--resourceGroup"]
        vmName = options["--plug"]
        try:
        
            if (options["--action"]=="off"):
                logging.info("Fencing %s in resource group %s" % (vmName, rgName))
           
                from azure.mgmt.network.models import SecurityRule

                powerState = "unknown"
                vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")
                for status in vm.instance_view.statuses:
                    if status.code.startswith("PowerState"):
                        powerState = status.code
                        break
                if powerState == "PowerState/deallocated" or powerState == "PowerState/stopped":
                    logging.info("VM %s is already fenced. Powerstate is %s" % (vmName, powerState))
                    return            
                
                for nic in vm.network_profile.network_interfaces:
                    match = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.id)
                    
                    if match:
                        logging.info("Getting network interface.")
                        nic = network_client.network_interfaces.get(match.group(3), match.group(6))
                        logging.info("Getting network interface done.")
                        if nic.network_security_group:
                            nsgmatch = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.network_security_group.id)
                            if nsgmatch:
                                logging.info("Getting NSG.")
                                nsg = network_client.network_security_groups.get(nsgmatch.group(3), nsgmatch.group(6))                                
                                logging.info("Getting NSG done.")

                                if len(nsg.network_interfaces) == 1 and ((not nsg.subnets) or len(nsg.subnets) == 0):
                                    inboundOk = False
                                    outboundOk = False
                                    for rule in nsg.security_rules:                                    
                                        if (rule.access == "Deny") and (rule.direction == "Inbound")  \
                                            and (rule.source_port_range == "*") and (rule.destination_port_range == "*") \
                                            and (rule.protocol == "*") and (rule.destination_address_prefix == "*") \
                                            and (rule.source_address_prefix == "*") and (rule.provisioning_state == "Succeeded") \
                                            and (rule.priority == 100):
                                            logging.info("Inbound rule found.")
                                            inboundOk = True
                                        elif (rule.access == "Deny") and (rule.direction == "Outbound")  \
                                            and (rule.source_port_range == "*") and (rule.destination_port_range == "*") \
                                            and (rule.protocol == "*") and (rule.destination_address_prefix == "*") \
                                            and (rule.source_address_prefix == "*") and (rule.provisioning_state == "Succeeded") \
                                            and (rule.priority == 100):
                                            logging.info("Outbound rule found.")
                                            outboundOk = True
                                    
                                    if (not inboundOk):
                                        logging.info("Creating new inbound deny all rule for network security group %s" % nsg.name)
                                        newIRule = SecurityRule("*", source_address_prefix="*", destination_address_prefix="*", \
                                            access="Deny", direction="Inbound", source_port_range="*", destination_port_range="*", \
                                            priority=100, name="FENCE_DENY_ALL_INBOUND")
                                        nsg.security_rules.append(newIRule)

                                    if (not outboundOk):
                                        logging.info("Creating new outbound deny all rule for network security group %s" % nsg.name)
                                        newORule = SecurityRule("*", source_address_prefix="*", destination_address_prefix="*", \
                                            access="Deny", direction="Outbound", source_port_range="*", destination_port_range="*", \
                                            priority=100, name="FENCE_DENY_ALL_OUTBOUND")
                                        nsg.security_rules.append(newORule)
                                    
                                    if ((not inboundOk) or (not outboundOk)):
                                        logging.info("Updating %s" % nsg.name)                               
                                        op = network_client.network_security_groups.create_or_update(nsgmatch.group(3), nsg.name, nsg)
                                        logging.info("Updating of %s started - waiting" % nsg.name)
                                        op.wait()
                                        logging.info("Updating of %s done" % nsg.name)

                                elif len(nsg.network_interfaces) != 1:
                                    fail_usage("Network security group %s of network interface %s is used by multiple network interfaces. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))
                                else:
                                    fail_usage("Network security group %s of network interface %s is also used by a subnet. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))                        
                            else:
                                fail_usage("Network Security Group id %s could not be parsed. Contact support" % nic.network_security_group.id)
                        else:            
                            fail_usage("Network interface id %s does not have a network security group." % nic.id)
                    else:
                        fail_usage("Network interface id %s could not be parsed. Contact support" % nic.id)
                
                logging.info("Network fencing done. Deallocating VM %s in resource group %s" % (vmName, rgName))
                compute_client.virtual_machines.deallocate(rgName, vmName)            
              
            elif (options["--action"]=="on"):
                logging.info("Unfencing %s in resource group %s" % (vmName, rgName))
                
                while True:
                    powerState = "unknown"
                    provState = "unknown"
                    vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")
                    for status in vm.instance_view.statuses:
                        if status.code.startswith("PowerState"):
                            powerState = status.code.replace("PowerState/", "")
                        if status.code.startswith("ProvisioningState"):
                            provState = status.code.replace("ProvisioningState/", "")
                
                    logging.info("Testing VM state: ProvisioningState %s, PowerState %s" % (provState, powerState))
                    
                    if (provState.lower() == "succeeded" and (powerState.lower() == "deallocated" or powerState.lower() == "stopped")):
                        break
                    elif (provState.lower() == "succeeded" and not (powerState.lower() == "deallocated" or powerState.lower() == "stopped")):
                        fail_usage("Virtual machine %s needs to be deallocated or stopped to be unfenced" % (vm.id))                        
                    elif (provState.lower() == "failed" or provState.lower() == "canceled"):
                        fail_usage("Virtual machine operation %s failed or canceled. Virtual machine %s needs to be deallocated or stopped to be unfenced" % (vm.id))
                    else:
                        time.sleep(10)

                logging.info("Starting virtual machine %s in resource group %s" % (vmName, rgName))
                waitOp = compute_client.virtual_machines.start(rgName, vmName)
                logging.info("Virtual machine %s started. Waiting for until operation is completed." % (vmName))
                waitOp.wait()
                logging.info("Virtual machine %s in resource group %s started." % (vmName, rgName))

                for nic in vm.network_profile.network_interfaces:
                    match = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.id)
                    
                    if match:
                        logging.info("Getting network interface.")
                        nic = network_client.network_interfaces.get(match.group(3), match.group(6))
                        logging.info("Getting network interface done.")
                        if nic.network_security_group:
                            nsgmatch = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?', nic.network_security_group.id)
                            if nsgmatch:
                                logging.info("Getting NSG.")
                                nsg = network_client.network_security_groups.get(nsgmatch.group(3), nsgmatch.group(6))                                
                                logging.info("Getting NSG done.")

                                if len(nsg.network_interfaces) == 1 and ((not nsg.subnets) or len(nsg.subnets) == 0):
                                    inboundOk = False
                                    outboundOk = False
                                    inboundRule = None
                                    outboundRule = None
                                    for rule in nsg.security_rules:
                                        logging.info("Testing if security rule %s needs to be removed" % rule.name)   
                                        if rule.name == "FENCE_DENY_ALL_INBOUND":
                                            logging.info("Inbound rule found.")
                                            inboundOk = True
                                            inboundRule = rule
                                        elif  rule.name == "FENCE_DENY_ALL_OUTBOUND":
                                            logging.info("Outbound rule found.")
                                            outboundOk = True
                                            outboundRule = rule
                                    
                                    if (inboundRule):
                                        nsg.security_rules.remove(inboundRule)                                   
                                    if (outboundRule):
                                        nsg.security_rules.remove(outboundRule)                                   

                                    if (inboundOk or outboundOk):
                                        logging.info("Updating %s" % nsg.name)                               
                                        op = network_client.network_security_groups.create_or_update(nsgmatch.group(3), nsg.name, nsg)
                                        logging.info("Updating of %s started - waiting" % nsg.name)
                                        op.wait()
                                        logging.info("Updating of %s done" % nsg.name)

                                elif len(nsg.network_interfaces) != 1:
                                    fail_usage("Network security group %s of network interface %s is used by multiple network interfaces. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))
                                else:
                                    fail_usage("Network security group %s of network interface %s is also used by a subnet. Virtual Machine %s cannot be fenced" % (nic.network_security_group.id, nic.id, vm.id ))                        
                            else:
                                fail_usage("Network Security Group id %s could not be parsed. Contact support" % nic.network_security_group.id)
                        else:            
                            fail_usage("Network interface id %s does not have a network security group." % nic.id)
                    else:
                        fail_usage("Network interface id %s could not be parsed. Contact support" % nic.id)



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
        "help" : "--useMSI=[value]        Id of the Azure subscription",
        "shortdesc" : "Id of the Azure subscription.",
        "required" : "0",
        "order" : 5
    }
    all_opt["cloud"] = {
        "getopt" : ":",
        "longopt" : "cloud",
        "help" : "--cloud=[value]        Id of the Azure subscription",
        "shortdesc" : "Id of the Azure subscription.",
        "required" : "0",
        "order" : 6
    }

# Main agent method
def main():
    from sys import stdout
    logging.getLogger().setLevel(logging.INFO)
    # handler = logging.StreamHandler(stdout)
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
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.network import NetworkManagementClient        

        cloud_environment = None
        if "--cloud" in options:                
            cloud = options["--cloud"]
            logging.info("Cloud parameter %s provided." % (cloud))

                
            if (cloud.lower() == "china"):
                from msrestazure.azure_cloud import AZURE_CHINA_CLOUD
                cloud_environment = AZURE_CHINA_CLOUD
            elif (cloud.lower() == "german"):
                from msrestazure.azure_cloud import AZURE_GERMAN_CLOUD
                cloud_environment = AZURE_GERMAN_CLOUD
            elif (cloud.lower() == "usgov"):
                from msrestazure.azure_cloud import AZURE_US_GOV_CLOUD
                cloud_environment = AZURE_US_GOV_CLOUD

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
