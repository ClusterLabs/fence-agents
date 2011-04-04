#!/usr/bin/python

import sys, re, pexpect, exceptions
sys.path.append("@FENCEAGENTSLIBDIR@")

from suds.client import Client
from suds import WebFault
from suds.sudsobject import Property
from fencing import *

#BEGIN_VERSION_GENERATION
RELEASE_VERSION="New VMWare Agent - test release on steroids"
REDHAT_COPYRIGHT=""
BUILD_DATE="April, 2011"
#END_VERSION_GENERATION

def soap_login(options):
	if options.has_key("-z"):
		url = "https://"
	else:
		url = "http://"
	
	url += options["-a"] + ":" + str(options["-u"]) + "/sdk"
	conn = Client(url + "/vimService.wsdl")
	conn.set_options(location = url)

	mo_ServiceInstance = Property('ServiceInstance')
	mo_ServiceInstance._type = 'ServiceInstance'
	ServiceContent = conn.service.RetrieveServiceContent(mo_ServiceInstance)
	mo_SessionManager = Property(ServiceContent.sessionManager.value)
	mo_SessionManager._type = 'SessionManager'
	
	try:
		SessionManager = conn.service.Login(mo_SessionManager, options["-l"], options["-p"])
	except Exception, ex:
		fail(EC_LOGIN_DENIED)	

	options["ServiceContent"] = ServiceContent
	options["mo_SessionManager"] = mo_SessionManager
	return conn

def get_power_status(conn, options):
	mo_ViewManager = Property(options["ServiceContent"].viewManager.value)
	mo_ViewManager._type = "ViewManager"

	mo_RootFolder = Property(options["ServiceContent"].rootFolder.value)
	mo_RootFolder._type = "Folder"

	mo_PropertyCollector = Property(options["ServiceContent"].propertyCollector.value)
	mo_PropertyCollector._type = 'PropertyCollector'

	ContainerView = conn.service.CreateContainerView(mo_ViewManager, recursive = 1, container = mo_RootFolder, type = ['VirtualMachine'])
	mo_ContainerView = Property(ContainerView.value)
	mo_ContainerView._type = "ContainerView"

	FolderTraversalSpec = conn.factory.create('ns0:TraversalSpec')
	FolderTraversalSpec.name = "traverseEntities"
	FolderTraversalSpec.path = "view"
	FolderTraversalSpec.skip = False
	FolderTraversalSpec.type = "ContainerView"

	objSpec = conn.factory.create('ns0:ObjectSpec')
	objSpec.obj = mo_ContainerView
	objSpec.selectSet = [ FolderTraversalSpec ]
	objSpec.skip = True

	propSpec = conn.factory.create('ns0:PropertySpec')
	propSpec.all = False
	propSpec.pathSet = ["name", "summary.runtime.powerState", "config.uuid", "summary", "config", "capability", "network"]
	propSpec.type = "VirtualMachine"

	propFilterSpec = conn.factory.create('ns0:PropertyFilterSpec')
	propFilterSpec.propSet = [ propSpec ]
	propFilterSpec.objectSet = [ objSpec ]

	try:
		raw_machines = conn.service.RetrievePropertiesEx(mo_PropertyCollector, propFilterSpec)
	except Exception, ex:
		fail(EC_STATUS)

	machines = { }
	uuid = { }
	mappingToUUID = { }

	for m in raw_machines.objects:
		info = {}
		for i in m.propSet:
			info[i.name] = i.val
		machines[info["name"]] = (info["config.uuid"], info["summary.runtime.powerState"])
		uuid[info["config.uuid"]] = info["summary.runtime.powerState"]
		mappingToUUID[m.obj.value] = info["config.uuid"]
	
	if ["list", "monitor"].count(options["-o"]) == 1:
		return machines
	else:
		if options.has_key("-U") == False:
			## Transform InventoryPath to UUID
			mo_SearchIndex = Property(options["ServiceContent"].searchIndex.value)
			mo_SearchIndex._type = "SearchIndex"
			
			vm = conn.service.FindByInventoryPath(mo_SearchIndex, options["-n"])
			
			try:
				options["-U"] = mappingToUUID[vm.value]
			except KeyError, ex:
				fail(EC_STATUS)
			except AttributeError, ex:
				fail(EC_STATUS)

		try:
			if uuid[options["-U"]] == "poweredOn":
				return "on"
			else:
				return "off"
			return status
		except KeyError, ex:
			fail(EC_STATUS)

def set_power_status(conn, options):
	mo_SearchIndex = Property(options["ServiceContent"].searchIndex.value)
	mo_SearchIndex._type = "SearchIndex"
	vm = conn.service.FindByUuid(mo_SearchIndex, vmSearch = 1, uuid = options["-U"])

	mo_machine = Property(vm.value)
	mo_machine._type = "VirtualMachine"
	
	if options["-o"] == "on":
		conn.service.PowerOnVM_Task(mo_machine)
	else:
		conn.service.PowerOffVM_Task(mo_machine)	

def main():
	device_opt = [  "help", "version", "agent", "quiet", "verbose", "debug",
			"action", "ipaddr", "login", "passwd", "passwd_script",
			"ssl", "port", "uuid", "separator", "ipport",
			"power_timeout", "shell_timeout", "login_timeout", "power_wait" ]

	atexit.register(atexit_handler)

	options = check_input(device_opt, process_input(device_opt))

	## 
	## Fence agent specific defaults
	#####
	docs = { }
	docs["shortdesc"] = "Fence agent for VMWare over SOAP API"
	docs["longdesc"] = "fence_vmware_soap is an I/O Fencing agent \
which can be used with the virtual machines managed by VMWare products \
that have SOAP API v4.1+. \
\n.P\n\
Name of virtual machine (-n / port) has to be used in inventory path \
format (e.g. /datacenter/vm/Discovered virtual machine/myMachine). Alternatively \
you can use UUID (-U / uuid) to access virtual machine."
	docs["vendorurl"] = "http://www.vmware.com"
	show_docs(options, docs)

	##
	## Operate the fencing device
	####
	conn = soap_login(options)
		
	result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)

	##
	## Logout from system
	#####
	try:
		conn.service.Logout(options["mo_SessionManager"])
	except Exception, ex:
		pass

	sys.exit(result)

if __name__ == "__main__":
	main()
