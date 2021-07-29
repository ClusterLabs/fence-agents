#!@PYTHON@ -tt

import sys
import logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, run_delay, EC_STATUS

try:
    from kubernetes.client.exceptions import ApiException
except ImportError:
    logging.error("Couldn\'t import kubernetes.client.exceptions.ApiException - not found or not accessible")

API_VERSION='kubevirt.io/v1'

def get_nodes_list(conn, options):
    logging.debug("Starting list/monitor operation")
    result = {}
    try:
        namespace = options.get("--namespace")
        include_uninitialized = True
        vm_api = conn.resources.get(api_version=API_VERSION, kind='VirtualMachine')
        vm_list = vm_api.get(namespace=namespace)
        for vm in vm_list.items:
            result[vm.metadata.name] = ("", None)
    except Exception as e:
        logging.error("Exception when calling VirtualMachine list: %s", e)
    return result

def get_power_status(conn, options):
    logging.debug("Starting get status operation")
    try:
        namespace = options.get("--namespace")
        name = options.get("--plug")
        vmi_api = conn.resources.get(api_version=API_VERSION,
                                              kind='VirtualMachineInstance')
        vmi = vmi_api.get(name=name, namespace=namespace)
        if vmi is not None:
            phase = vmi.status.phase
            if phase == "Running":
                return "on"
        return "off"
    except ApiException as e:
        if e.status == 404:
            return "off"
        logging.error("Failed to get power status, with API Exception: %s", e)
        fail(EC_STATUS)
    except Exception as e:
        logging.error("Failed to get power status, with Exception: %s", e)
        fail(EC_STATUS)

def set_power_status(conn, options):
    logging.debug("Starting set status operation")
    try:
        namespace = options.get("--namespace")
        name = options.get("--plug")
        action = 'start' if options["--action"] == "on" else 'stop'
        virtctl_vm_action(conn, action, namespace, name)
    except Exception as e:
        logging.error("Failed to set power status, with Exception: %s", e)
        fail(EC_STATUS)

def define_new_opts():
	all_opt["namespace"] = {
		"getopt" : ":",
		"longopt" : "namespace",
		"help" : "--namespace=[namespace]        Namespace of the KubeVirt machine",
		"shortdesc" : "Namespace of the KubeVirt machine.",
		"required" : "1",
		"order" : 2
	}
	all_opt["kubeconfig"] = {
		"getopt" : ":",
		"longopt" : "kubeconfig",
		"help" : "--kubeconfig=[kubeconfig]      Kubeconfig file path",
		"shortdesc": "Kubeconfig file path",
		"required": "0",
		"order": 4
	}

def virtctl_vm_action(conn, action, namespace, name):
    path = '/apis/subresources.{api_version}/namespaces/{namespace}/virtualmachines/{name}/{action}'
    path = path.format(api_version=API_VERSION, namespace=namespace, name=name, action=action)
    return conn.request('put', path, header_params={'accept': '*/*'})

def validate_options(required_options_list, options):
    for required_option in required_options_list:
        if required_option not in options:
            fail_usage("Failed: %s option must be provided" % required_option)

# Main agent method
def main():
    conn = None

    device_opt = ["port", "namespace", "kubeconfig", "ssl_insecure", "no_password"]
    define_new_opts()
    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence agent for KubeVirt"
    docs["longdesc"] = "fence_kubevirt is an I/O Fencing agent for KubeVirt."
    docs["vendorurl"] = "https://kubevirt.io/"
    show_docs(options, docs)

    run_delay(options)

    validate_options(['--namespace'], options)

    # Disable insecure-certificate-warning message
    if "--ssl-insecure" in options:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        from kubernetes import config
        from openshift.dynamic import DynamicClient
        kubeconfig = options.get('--kubeconfig')
        k8s_client = config.new_client_from_config(config_file=kubeconfig)
        conn = DynamicClient(k8s_client)
    except ImportError:
        logging.error("Couldn\'t import kubernetes.config or "
                      "openshift.dynamic.DynamicClient - not found or not accessible")

    # Operate the fencing device
    result = fence_action(conn, options, set_power_status, get_power_status, get_nodes_list)
    sys.exit(result)

if __name__ == "__main__":
	main()
