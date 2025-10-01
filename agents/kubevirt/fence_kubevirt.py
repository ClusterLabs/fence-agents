#!@PYTHON@ -tt

import sys
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, run_delay, EC_STATUS, EC_FETCH_VM_UUID

try:
    from kubernetes.client.exceptions import ApiException
except ImportError:
    try:
        from kubernetes.client.rest import ApiException
    except ImportError:
        logging.error("Couldn\'t import kubernetes.client.exceptions.ApiException or kubernetes.client.rest.ApiException - not found or not accessible")

def _get_namespace(options):
    from kubernetes import config

    ns = options.get("--namespace")
    if ns is None:
        ns = config.kube_config.list_kube_config_contexts()[1]['context']['namespace']

    return ns

def get_nodes_list(conn, options):
    logging.debug("Starting list/monitor operation")
    result = {}
    try:
        apiversion = options.get("--apiversion")
        namespace = _get_namespace(options)
        include_uninitialized = True
        vm_api = conn.resources.get(api_version=apiversion, kind='VirtualMachine')
        vm_list = vm_api.get(namespace=namespace)
        for vm in vm_list.items:
            result[vm.metadata.name] = ("", None)
    except Exception as e:
        logging.error("Exception when calling VirtualMachine list: %s", e)
    return result

def get_power_status(conn, options):
    logging.debug("Starting get status operation")
    try:
        apiversion = options.get("--apiversion")
        namespace = _get_namespace(options)
        name = options.get("--plug")
        vmi_api = conn.resources.get(api_version=apiversion,
                                              kind='VirtualMachineInstance')
        vmi = vmi_api.get(name=name, namespace=namespace)
        return translate_status(vmi.status.phase)
    except ApiException as e:
        if e.status == 404:
            try:
                vm_api = conn.resources.get(api_version=apiversion, kind='VirtualMachine')
                vm = vm_api.get(name=name, namespace=namespace)
            except ApiException as e:
                logging.error("VM %s doesn't exist", name)
                fail(EC_FETCH_VM_UUID)
            return "off"
        logging.error("Failed to get power status, with API Exception: %s", e)
        fail(EC_STATUS)
    except Exception as e:
        logging.error("Failed to get power status, with Exception: %s", e)
        fail(EC_STATUS)

def translate_status(instance_status):
    if instance_status == "Running":
        return "on"
    return "unknown"

def set_power_status(conn, options):
    logging.debug("Starting set status operation")
    try:
        apiversion= options.get("--apiversion")
        namespace = _get_namespace(options)
        name = options.get("--plug")
        action = 'start' if options["--action"] == "on" else 'stop'
        virtctl_vm_action(conn, action, namespace, name, apiversion)
    except Exception as e:
        logging.error("Failed to set power status, with Exception: %s", e)
        fail(EC_STATUS)

def define_new_opts():
    all_opt["namespace"] = {
        "getopt" : ":",
        "longopt" : "namespace",
        "help" : "--namespace=[namespace]        Namespace of the KubeVirt machine",
        "shortdesc" : "Namespace of the KubeVirt machine.",
        "required" : "0",
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
    all_opt["apiversion"] = {
        "getopt" : ":",
        "longopt" : "apiversion",
        "help" : "--apiversion=[apiversion]      Version of the KubeVirt API",
        "shortdesc" : "Version of the KubeVirt API.",
        "required" : "0",
        "default" : "kubevirt.io/v1",
        "order" : 5
    }

def virtctl_vm_action(conn, action, namespace, name, apiversion):
    path = '/apis/subresources.{api_version}/namespaces/{namespace}/virtualmachines/{name}/{action}'
    path = path.format(api_version=apiversion, namespace=namespace, name=name, action=action)
    return conn.request('put', path, header_params={'accept': '*/*'}, body={'gracePeriod': 0} if action == 'stop' else None)

# Main agent method
def main():
    conn = None

    device_opt = ["port", "namespace", "kubeconfig", "ssl_insecure", "no_password", "apiversion"]

    atexit.register(atexit_handler)
    define_new_opts()

    all_opt["power_timeout"]["default"] = "40"

    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence agent for KubeVirt"
    docs["longdesc"] = "fence_kubevirt is a Power Fencing agent for KubeVirt."
    docs["vendorurl"] = "https://kubevirt.io/"
    show_docs(options, docs)

    run_delay(options)

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
