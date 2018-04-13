import logging, re, time
from fencing import fail_usage

FENCE_SUBNET_NAME = "fence-subnet"
FENCE_INBOUND_RULE_NAME = "FENCE_DENY_ALL_INBOUND"
FENCE_INBOUND_RULE_DIRECTION = "Inbound"
FENCE_OUTBOUND_RULE_NAME = "FENCE_DENY_ALL_OUTBOUND"
FENCE_OUTBOUND_RULE_DIRECTION = "Outbound"
FENCE_STATE_OFF = "off"
FENCE_STATE_ON = "on"
FENCE_TAG_SUBNET_ID = "FENCE_TAG_SUBNET_ID"
FENCE_TAG_IP_TYPE = "FENCE_TAG_IP_TYPE"
FENCE_TAG_IP = "FENCE_TAG_IP"
IP_TYPE_DYNAMIC = "Dynamic"
MAX_RETRY = 10
RETRY_WAIT = 5

class AzureSubResource:
    Type = None
    Name = None

class AzureResource:
    Id = None
    SubscriptionId = None
    ResourceGroupName = None
    ResourceName = None
    SubResources = []

class AzureConfiguration:
    RGName = None
    VMName = None
    SubscriptionId = None
    Cloud = None
    UseMSI = None
    Tenantid = None
    ApplicationId = None
    ApplicationKey = None
    Verbose = None

def get_from_metadata(parameter):
    import requests
    try:
        r = requests.get('http://169.254.169.254/metadata/instance?api-version=2017-08-01', headers = {"Metadata":"true"})
        return str(r.json()["compute"][parameter])
    except:
        logging.warning("Not able to use metadata service. Am I running in Azure?")

    return None

def get_azure_resource(id):
    match = re.match('(/subscriptions/([^/]*)/resourceGroups/([^/]*))(/providers/([^/]*/[^/]*)/([^/]*))?((/([^/]*)/([^/]*))*)', id)
    if not match:
        fail_usage("{get_azure_resource} cannot parse resource id %s" % id)

    logging.debug("{get_azure_resource} found %s matches for %s" % (len(match.groups()), id))
    iGroup = 0
    while iGroup < len(match.groups()):
        logging.debug("{get_azure_resource} group %s: %s" %(iGroup, match.group(iGroup)))
        iGroup += 1

    resource = AzureResource()
    resource.Id = id
    resource.SubscriptionId = match.group(2)
    resource.SubResources = []

    if len(match.groups()) > 3:
        resource.ResourceGroupName = match.group(3)
        logging.debug("{get_azure_resource} resource group %s" % resource.ResourceGroupName)

    if len(match.groups()) > 6:
        resource.ResourceName = match.group(6)
        logging.debug("{get_azure_resource} resource name %s" % resource.ResourceName)

    if len(match.groups()) > 7 and match.group(7):
        splits = match.group(7).split("/")
        logging.debug("{get_azure_resource} splitting subtypes '%s' (%s)" % (match.group(7), len(splits)))
        i = 1 # the string starts with / so the first split is empty
        while i < len(splits) - 1:
            logging.debug("{get_azure_resource} creating subresource with type %s and name %s" % (splits[i], splits[i+1]))
            subRes = AzureSubResource()
            subRes.Type = splits[i]
            subRes.Name = splits[i+1]
            resource.SubResources.append(subRes)
            i += 2

    return resource

def get_fence_subnet_for_config(ipConfig, network_client):
    subnetResource = get_azure_resource(ipConfig.subnet.id)
    logging.debug("{get_fence_subnet_for_config} testing virtual network %s in resource group %s for a fence subnet" %(subnetResource.ResourceName, subnetResource.ResourceGroupName))
    vnet = network_client.virtual_networks.get(subnetResource.ResourceGroupName, subnetResource.ResourceName)
    return get_subnet(vnet, FENCE_SUBNET_NAME)

def get_subnet(vnet, subnetName):
    for avSubnet in vnet.subnets:
        logging.debug("{get_subnet} searching subnet %s testing subnet %s" % (subnetName, avSubnet.name))
        if (avSubnet.name.lower() == subnetName.lower()):
                logging.debug("{get_subnet} subnet found %s" % avSubnet)
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

def get_network_state(compute_client, network_client, rgName, vmName):
    result = FENCE_STATE_ON

    try:
        vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")

        allNICOK = True
        for nicRef in vm.network_profile.network_interfaces:
            nicresource = get_azure_resource(nicRef.id)
            nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)
            for ipConfig in nic.ip_configurations:
                logging.info("{get_network_state} Testing ip configuration %s" % ipConfig.name)
                fenceSubnet = get_fence_subnet_for_config(ipConfig, network_client)
                testOk = test_fence_subnet(fenceSubnet, nic, network_client)
                if not testOk:
                    allNICOK = False
                elif fenceSubnet.id.lower() != ipConfig.subnet.id.lower():
                    logging.info("{get_network_state} IP configuration %s is not in fence subnet (ip subnet: %s, fence subnet: %s)" % (ipConfig.name, ipConfig.subnet.id.lower(), fenceSubnet.id.lower()))
                    allNICOK = False
        if allNICOK:
            logging.info("{get_network_state} All IP configurations of all network interfaces are in the fence subnet. Declaring VM as off")
            result = FENCE_STATE_OFF
    except Exception as e:
        fail_usage("{get_network_state} Failed: %s" % e)

    return result

def set_network_state(compute_client, network_client, rgName, vmName, operation):
    import msrestazure.azure_exceptions
    logging.info("{set_network_state} Setting state %s for  %s in resource group %s" % (operation, vmName, rgName))

    vm = compute_client.virtual_machines.get(rgName, vmName, "instanceView")

    operations = []
    for nicRef in vm.network_profile.network_interfaces:
        for attempt in range(0, MAX_RETRY):
            try:
                nicresource = get_azure_resource(nicRef.id)
                nic = network_client.network_interfaces.get(nicresource.ResourceGroupName, nicresource.ResourceName)

                if not nic.tags and operation == "block":
                    nic.tags = {}

                logging.info("{set_network_state} Searching for tags required to unfence this virtual machine")
                for ipConfig in nic.ip_configurations:
                    if operation == "block":
                        fenceSubnet = get_fence_subnet_for_config(ipConfig, network_client)
                        testOk = test_fence_subnet(fenceSubnet, nic, network_client)
                        if testOk:
                            logging.info("{set_network_state} Changing subnet of ip config of nic %s" % nic.id)
                            nic.tags[("%s_%s" % (FENCE_TAG_SUBNET_ID, ipConfig.name))] = ipConfig.subnet.id
                            nic.tags[("%s_%s" % (FENCE_TAG_IP_TYPE, ipConfig.name))] = ipConfig.private_ip_allocation_method
                            nic.tags[("%s_%s" % (FENCE_TAG_IP, ipConfig.name))] = ipConfig.private_ip_address
                            ipConfig.subnet = fenceSubnet
                            ipConfig.private_ip_allocation_method = IP_TYPE_DYNAMIC
                        else:
                            fail_usage("{set_network_state} Network interface id %s does not have a network security group." % nic.id)
                    elif operation == "unblock":
                        if not nic.tags:
                            fail_usage("{set_network_state} IP configuration %s is missing the required resource tags (empty)" % ipConfig.name)

                        subnetId = nic.tags.pop("%s_%s" % (FENCE_TAG_SUBNET_ID, ipConfig.name))
                        ipType = nic.tags.pop("%s_%s" % (FENCE_TAG_IP_TYPE, ipConfig.name))
                        ipAddress = nic.tags.pop("%s_%s" % (FENCE_TAG_IP, ipConfig.name))

                        if (subnetId and ipType and (ipAddress or (ipType.lower() == IP_TYPE_DYNAMIC.lower()))):
                            logging.info("{set_network_state} tags found (subnetId: %s, ipType: %s, ipAddress: %s)" % (subnetId, ipType, ipAddress))

                            subnetResource = get_azure_resource(subnetId)
                            vnet = network_client.virtual_networks.get(subnetResource.ResourceGroupName, subnetResource.ResourceName)
                            logging.info("{set_network_state} looking for subnet %s" % len(subnetResource.SubResources))
                            oldSubnet = get_subnet(vnet, subnetResource.SubResources[0].Name)
                            if not oldSubnet:
                                fail_usage("{set_network_state} subnet %s not found" % subnetId)

                            ipConfig.subnet = oldSubnet
                            ipConfig.private_ip_allocation_method = ipType
                            if ipAddress:
                                ipConfig.private_ip_address = ipAddress
                        else:
                            fail_usage("{set_network_state} IP configuration %s is missing the required resource tags(subnetId: %s, ipType: %s, ipAddress: %s)" % (ipConfig.name, subnetId, ipType, ipAddress))

                logging.info("{set_network_state} updating nic %s" % (nic.id))
                op = network_client.network_interfaces.create_or_update(nicresource.ResourceGroupName, nicresource.ResourceName, nic)
                operations.append(op)
                break
            except msrestazure.azure_exceptions.CloudError as cex:
                logging.error("{set_network_state} CloudError in attempt %s '%s'" % (attempt, cex))
                if cex.error and cex.error.error and cex.error.error.lower() == "PrivateIPAddressIsBeingCleanedUp":
                    logging.error("{set_network_state} PrivateIPAddressIsBeingCleanedUp")
                time.sleep(RETRY_WAIT)

            except Exception as ex:
                logging.error("{set_network_state} Exception of type %s: %s" % (type(ex).__name__, ex))
                break

def get_azure_config(options):
    config = AzureConfiguration()

    config.RGName = options.get("--resourceGroup")
    config.VMName = options.get("--plug")
    config.SubscriptionId = options.get("--subscriptionId")
    config.Cloud = options.get("--cloud")
    config.UseMSI = "--msi" in options
    config.Tenantid = options.get("--tenantId")
    config.ApplicationId = options.get("--username")
    config.ApplicationKey = options.get("--password")
    config.Verbose = options.get("--verbose")

    if not config.RGName:
        logging.info("resourceGroup not provided. Using metadata service")
        config.RGName = get_from_metadata("resourceGroupName")

    if not config.SubscriptionId:
        logging.info("subscriptionId not provided. Using metadata service")
        config.SubscriptionId = get_from_metadata("subscriptionId")

    return config

def get_azure_cloud_environment(config):
    cloud_environment = None
    if config.Cloud:
        if (config.Cloud.lower() == "china"):
            from msrestazure.azure_cloud import AZURE_CHINA_CLOUD
            cloud_environment = AZURE_CHINA_CLOUD
        elif (config.Cloud.lower() == "germany"):
            from msrestazure.azure_cloud import AZURE_GERMAN_CLOUD
            cloud_environment = AZURE_GERMAN_CLOUD
        elif (config.Cloud.lower() == "usgov"):
            from msrestazure.azure_cloud import AZURE_US_GOV_CLOUD
            cloud_environment = AZURE_US_GOV_CLOUD

    return cloud_environment

def get_azure_credentials(config):
    credentials = None
    cloud_environment = get_azure_cloud_environment(config)
    if config.UseMSI and cloud_environment:
        from msrestazure.azure_active_directory import MSIAuthentication
        credentials = MSIAuthentication(cloud_environment=cloud_environment)
    elif config.UseMSI:
        from msrestazure.azure_active_directory import MSIAuthentication
        credentials = MSIAuthentication()
    elif cloud_environment:
        from azure.common.credentials import ServicePrincipalCredentials
        credentials = ServicePrincipalCredentials(
            client_id = config.ApplicationId,
            secret = config.ApplicationKey,
            tenant = config.Tenantid,
            cloud_environment=cloud_environment
        )
    else:
        from azure.common.credentials import ServicePrincipalCredentials
        credentials = ServicePrincipalCredentials(
            client_id = config.ApplicationId,
            secret = config.ApplicationKey,
            tenant = config.Tenantid
        )

    return credentials

def get_azure_compute_client(config):
    from azure.mgmt.compute import ComputeManagementClient

    cloud_environment = get_azure_cloud_environment(config)
    credentials = get_azure_credentials(config)

    if cloud_environment:
        compute_client = ComputeManagementClient(
            credentials,
            config.SubscriptionId,
            base_url=cloud_environment.endpoints.resource_manager
        )
    else:
        compute_client = ComputeManagementClient(
            credentials,
            config.SubscriptionId
        )
    return compute_client

def get_azure_network_client(config):
    from azure.mgmt.network import NetworkManagementClient

    cloud_environment = get_azure_cloud_environment(config)
    credentials = get_azure_credentials(config)

    if cloud_environment:
        network_client = NetworkManagementClient(
            credentials,
            config.SubscriptionId,
            base_url=cloud_environment.endpoints.resource_manager
        )
    else:
        network_client = NetworkManagementClient(
            credentials,
            config.SubscriptionId
        )
    return network_client
