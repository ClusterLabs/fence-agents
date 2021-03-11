#!@PYTHON@ -tt

#
# Fence agent for Intel AMT (WS) based on code from the openstack/ironic project:
# https://github.com/openstack/ironic/blob/master/ironic/drivers/modules/amt/power.py
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#

import sys
import atexit
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import run_delay, fail_usage, fail, EC_STATUS

from xml.etree import ElementTree

try:
	import pywsman
except ImportError:
	pass

POWER_ON='2'
POWER_OFF='8'
POWER_CYCLE='10'

RET_SUCCESS = '0'

CIM_PowerManagementService           = ('http://schemas.dmtf.org/wbem/wscim/1/'
                                        'cim-schema/2/CIM_PowerManagementService')
CIM_ComputerSystem                   = ('http://schemas.dmtf.org/wbem/wscim/'
                                        '1/cim-schema/2/CIM_ComputerSystem')
CIM_AssociatedPowerManagementService = ('http://schemas.dmtf.org/wbem/wscim/'
                                        '1/cim-schema/2/'
                                        'CIM_AssociatedPowerManagementService')

CIM_BootConfigSetting                = ('http://schemas.dmtf.org/wbem/wscim/'
                                        '1/cim-schema/2/CIM_BootConfigSetting')
CIM_BootSourceSetting                = ('http://schemas.dmtf.org/wbem/wscim/'
                                        '1/cim-schema/2/CIM_BootSourceSetting')


def xml_find(doc, namespace, item):
    if doc is None:
        return
    tree = ElementTree.fromstring(doc.root().string())
    query = ('.//{%(namespace)s}%(item)s' % {'namespace': namespace,
                                             'item': item})
    return tree.find(query)

def _generate_power_action_input(action):
    method_input = "RequestPowerStateChange_INPUT"
    address = 'http://schemas.xmlsoap.org/ws/2004/08/addressing'
    anonymous = ('http://schemas.xmlsoap.org/ws/2004/08/addressing/'
                 'role/anonymous')
    wsman = 'http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd'
    namespace = CIM_PowerManagementService

    doc = pywsman.XmlDoc(method_input)
    root = doc.root()
    root.set_ns(namespace)
    root.add(namespace, 'PowerState', action)

    child = root.add(namespace, 'ManagedElement', None)
    child.add(address, 'Address', anonymous)

    grand_child = child.add(address, 'ReferenceParameters', None)
    grand_child.add(wsman, 'ResourceURI', CIM_ComputerSystem)

    g_grand_child = grand_child.add(wsman, 'SelectorSet', None)
    g_g_grand_child = g_grand_child.add(wsman, 'Selector', 'ManagedSystem')
    g_g_grand_child.attr_add(wsman, 'Name', 'Name')
    return doc

def get_power_status(_, options):
    client = pywsman.Client(options["--ip"], int(options["--ipport"]), \
                            '/wsman', 'http', 'admin', options["--password"])
    namespace = CIM_AssociatedPowerManagementService
    client_options = pywsman.ClientOptions()
    doc = client.get(client_options, namespace)
    _SOAP_ENVELOPE = 'http://www.w3.org/2003/05/soap-envelope'
    item = 'Fault'
    fault = xml_find(doc, _SOAP_ENVELOPE, item)
    if fault is not None:
        logging.error("Failed to get power state for: %s port:%s", \
                      options["--ip"], options["--ipport"])
        fail(EC_STATUS)

    item = "PowerState"
    try: power_state = xml_find(doc, namespace, item).text
    except AttributeError:
        logging.error("Failed to get power state for: %s port:%s", \
                      options["--ip"], options["--ipport"])
        fail(EC_STATUS)
    if power_state == POWER_ON:
        return "on"
    elif power_state == POWER_OFF:
        return "off"
    else:
        fail(EC_STATUS)

def set_power_status(_, options):
    client = pywsman.Client(options["--ip"], int(options["--ipport"]), \
                            '/wsman', 'http', 'admin', options["--password"])

    method = 'RequestPowerStateChange'
    client_options = pywsman.ClientOptions()
    client_options.add_selector('Name', 'Intel(r) AMT Power Management Service')

    if options["--action"] == "on":
        target_state = POWER_ON
    elif options["--action"] == "off":
        target_state = POWER_OFF
    elif options["--action"] == "reboot":
        target_state = POWER_CYCLE
    if options["--action"] in ["on", "off", "reboot"] \
       and "--boot-option" in options:
        set_boot_order(_, client, options)

    doc = _generate_power_action_input(target_state)
    client_doc = client.invoke(client_options, CIM_PowerManagementService, \
                               method, doc)
    item = "ReturnValue"
    return_value = xml_find(client_doc, CIM_PowerManagementService, item).text
    if return_value != RET_SUCCESS:
        logging.error("Failed to set power state: %s for: %s", \
                      options["--action"], options["--ip"])
        fail(EC_STATUS)

def set_boot_order(_, client, options):
    method_input = "ChangeBootOrder_INPUT"
    address = 'http://schemas.xmlsoap.org/ws/2004/08/addressing'
    anonymous = ('http://schemas.xmlsoap.org/ws/2004/08/addressing/'
                 'role/anonymous')
    wsman = 'http://schemas.dmtf.org/wbem/wsman/1/wsman.xsd'
    namespace = CIM_BootConfigSetting

    if options["--boot-option"] == "pxe":
        device = "Intel(r) AMT: Force PXE Boot"
    elif options["--boot-option"] == "hd" or "hdsafe":
        device = "Intel(r) AMT: Force Hard-drive Boot"
    elif options["--boot-option"] == "cd":
        device = "Intel(r) AMT: Force CD/DVD Boot"
    elif options["--boot-option"] == "diag":
        device = "Intel(r) AMT: Force Diagnostic Boot"
    else:
        logging.error('Boot device: %s not supported.', \
                      options["--boot-option"])
        return

    method = 'ChangeBootOrder'
    client_options = pywsman.ClientOptions()
    client_options.add_selector('InstanceID', \
                                'Intel(r) AMT: Boot Configuration 0')

    doc = pywsman.XmlDoc(method_input)
    root = doc.root()
    root.set_ns(namespace)

    child = root.add(namespace, 'Source', None)
    child.add(address, 'Address', anonymous)

    grand_child = child.add(address, 'ReferenceParameters', None)
    grand_child.add(wsman, 'ResourceURI', CIM_BootSourceSetting)

    g_grand_child = grand_child.add(wsman, 'SelectorSet', None)
    g_g_grand_child = g_grand_child.add(wsman, 'Selector', device)
    g_g_grand_child.attr_add(wsman, 'Name', 'InstanceID')
    if options["--boot-option"] == "hdsafe":
        g_g_grand_child = g_grand_child.add(wsman, 'Selector', 'True')
        g_g_grand_child.attr_add(wsman, 'Name', 'UseSafeMode')

    client_doc = client.invoke(client_options, CIM_BootConfigSetting, \
                               method, doc)
    item = "ReturnValue"
    return_value = xml_find(client_doc, CIM_BootConfigSetting, item).text
    if return_value != RET_SUCCESS:
        logging.error("Failed to set boot device to: %s for: %s", \
                      options["--boot-option"], options["--ip"])
        fail(EC_STATUS)

def reboot_cycle(_, options):
    status = set_power_status(_, options)
    return not bool(status)

def define_new_opts():
    all_opt["boot_option"] = {
        "getopt" : "b:",
        "longopt" : "boot-option",
        "help" : "-b, --boot-option=[option]     "
                "Change the default boot behavior of the\n"
                "                                  machine."
                " (pxe|hd|hdsafe|cd|diag)",
        "required" : "0",
        "shortdesc" : "Change the default boot behavior of the machine.",
        "choices" : ["pxe", "hd", "hdsafe", "cd", "diag"],
        "order" : 1
    }

def main():
    atexit.register(atexit_handler)

    device_opt = ["ipaddr", "no_login", "passwd", "boot_option", "no_port",
                  "method"]

    define_new_opts()

    all_opt["ipport"]["default"] = "16992"

    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence agent for AMT (WS)"
    docs["longdesc"] = "fence_amt_ws is an I/O Fencing agent \
which can be used with Intel AMT (WS). This agent requires \
the pywsman Python library which is included in OpenWSMAN. \
(http://openwsman.github.io/)."
    docs["vendorurl"] = "http://www.intel.com/"
    show_docs(options, docs)

    run_delay(options)

    result = fence_action(None, options, set_power_status, get_power_status, \
                          None, reboot_cycle)

    sys.exit(result)

if __name__ == "__main__":
    main()
