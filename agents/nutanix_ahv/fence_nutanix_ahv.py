#!@PYTHON@ -tt

# AHV Fence agent
# Compatible with Nutanix v4 API


import atexit
import logging
import sys
import time
import uuid
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_LOGIN_DENIED, EC_GENERIC_ERROR, EC_TIMED_OUT, run_delay, EC_BAD_ARGS


V4_VERSION = '4.0'
MIN_TIMEOUT = 60
PC_PORT = 9440
POWER_STATES = {"ON": "on", "OFF": "off", "PAUSED": "off", "UNKNOWN": "unknown"}
MAX_RETRIES = 5


class NutanixClientException(Exception):
    pass


class AHVFenceAgentException(Exception):
    pass


class TaskTimedOutException(Exception):
    pass


class InvalidArgsException(Exception):
    pass


class NutanixClient:
    def __init__(self, username, password, disable_warnings=False):
        self.username = username
        self.password = password
        self.valid_status_codes = [200, 202]
        self.disable_warnings = disable_warnings
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)

        retry_strategy = Retry(total=MAX_RETRIES,
                               backoff_factor=1,
                               status_forcelist=[429, 500, 503])

        self.session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

    def request(self, url, method='GET', headers=None, **kwargs):

        if self.disable_warnings:
            requests.packages.urllib3.disable_warnings()

        if headers:
            self.session.headers.update(headers)

        response = None

        try:
            logging.debug("Sending %s request to %s", method, url)
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
        except requests.exceptions.SSLError as err:
            logging.error("Secure connection failed, verify SSL certificate")
            logging.error("Error message: %s", err)
            raise NutanixClientException("Secure connection failed") from err
        except requests.exceptions.RequestException as err:
            logging.error("API call failed: %s", response.text)
            logging.error("Error message: %s", err)
            raise NutanixClientException(f"API call failed: {err}") from err
        except Exception as err:
            logging.error("API call failed: %s", response.text)
            logging.error("Unknown error %s", err)
            raise NutanixClientException(f"API call failed: {err}") from err

        if response.status_code not in self.valid_status_codes:
            logging.error("API call returned status code %s", response.status_code)
            raise NutanixClientException(f"API call failed: {response}")

        return response


class NutanixV4Client(NutanixClient):
    def __init__(self, host=None, username=None, password=None,
                 verify=True, disable_warnings=False):
        self.host = host
        self.username = username
        self.password = password
        self.verify = verify
        self.base_url = f"https://{self.host}:{PC_PORT}/api"
        self.vm_url = f"{self.base_url}/vmm/v{V4_VERSION}/ahv/config/vms"
        self.task_url = f"{self.base_url}/prism/v{V4_VERSION}/config/tasks"
        super().__init__(username, password, disable_warnings)

    def _get_headers(self, vm_uuid=None):
        resp = None
        headers = {'Accept':'application/json',
                   'Content-Type': 'application/json'}

        if vm_uuid:
            try:
                resp = self._get_vm(vm_uuid)
            except AHVFenceAgentException as err:
                logging.error("Unable to retrieve etag")
                raise AHVFenceAgentException from err

            etag_str = resp.headers['Etag']
            request_id = str(uuid.uuid1())
            headers['If-Match'] = etag_str
            headers['Ntnx-Request-Id'] = request_id

        return headers

    def _get_all_vms(self, filter_str=None, limit=None):
        vm_url = self.vm_url

        if filter_str and limit:
            vm_url = f"{vm_url}?$filter={filter_str}&$limit={limit}"
        elif filter_str and not limit:
            vm_url = f"{vm_url}?$filter={filter_str}"
        elif limit and not filter_str:
            vm_url = f"{vm_url}?$limit={limit}"

        logging.debug("Getting info for all VMs, %s", vm_url)
        header_str = self._get_headers()

        try:
            resp = self.request(url=vm_url, method='GET',
                                headers=header_str, verify=self.verify)
        except NutanixClientException as err:
            logging.error("Unable to retrieve VM info")
            raise AHVFenceAgentException from err

        vms = resp.json()
        return vms

    def _get_vm_uuid(self, vm_name):
        vm_uuid = None
        resp = None

        if not vm_name:
            logging.error("VM name was not provided")
            raise AHVFenceAgentException("VM name not provided")

        try:
            filter_str = f"name eq '{vm_name}'"
            resp = self._get_all_vms(filter_str=filter_str)
        except AHVFenceAgentException as err:
            logging.error("Failed to get VM info for VM %s", vm_name)
            raise AHVFenceAgentException from err

        if not resp or not isinstance(resp, dict):
            logging.error("Failed to retrieve VM UUID for VM %s", vm_name)
            raise AHVFenceAgentException(f"Failed to get VM UUID for {vm_name}")

        if 'data' not in resp:
            err = f"Error: Unsuccessful match for VM name: {vm_name}"
            logging.error("Failed to retrieve VM UUID for VM %s", vm_name)
            raise AHVFenceAgentException(err)

        for vm in resp['data']:
            if vm['name'] == vm_name:
                vm_uuid = vm['extId']
                break

        return vm_uuid

    def _get_vm(self, vm_uuid):
        if not vm_uuid:
            logging.error("VM UUID was not provided")
            raise AHVFenceAgentException("VM UUID not provided")

        vm_url = self.vm_url + f"/{vm_uuid}"
        logging.debug("Getting config information for VM, %s", vm_uuid)

        try:
            header_str = self._get_headers()
            resp = self.request(url=vm_url, method='GET',
                                headers=header_str, verify=self.verify)
        except NutanixClientException as err:
            logging.error("Failed to retrieve VM details "
                          "for VM UUID: %s", vm_uuid)
            raise AHVFenceAgentException from err
        except AHVFenceAgentException as err:
            logging.error("Failed to retrieve etag from headers")
            raise AHVFenceAgentException from err

        return resp

    def _power_on_off_vm(self, power_state=None, vm_uuid=None):
        resp = None
        vm_url = None

        if not vm_uuid:
            logging.error("VM UUID was not provided")
            raise AHVFenceAgentException("VM UUID not provided")
        if not power_state:
            logging.error("Requested VM power state is None")
            raise InvalidArgsException

        power_state = power_state.lower()

        if power_state == 'on':
            vm_url = self.vm_url + f"/{vm_uuid}/$actions/power-on"
            logging.debug("Sending request to power on VM, %s", vm_uuid)
        elif power_state == 'off':
            vm_url = self.vm_url + f"/{vm_uuid}/$actions/power-off"
            logging.debug("Sending request to power off VM, %s", vm_uuid)
        else:
            logging.error("Invalid power state specified: %s", power_state)
            raise InvalidArgsException

        try:
            headers_str = self._get_headers(vm_uuid)
            resp = self.request(url=vm_url, method='POST',
                                headers=headers_str, verify=self.verify)
        except NutanixClientException as err:
            logging.error("Failed to power off VM %s", vm_uuid)
            raise AHVFenceAgentException from err
        except AHVFenceAgentException as err:
            logging.error("Failed to retrieve etag from headers")
            raise AHVFenceAgentException from err

        return resp

    def _power_cycle_vm(self, vm_uuid):
        if not vm_uuid:
            logging.error("VM UUID was not provided")
            raise AHVFenceAgentException("VM UUID not provided")

        resp = None
        vm_url = self.vm_url + f"/{vm_uuid}/$actions/power-cycle"
        logging.debug("Sending request to power cycle VM, %s", vm_uuid)

        try:
            header_str = self._get_headers(vm_uuid)
            resp = self.request(url=vm_url, method='POST',
                                headers=header_str, verify=self.verify)
        except NutanixClientException as err:
            logging.error("Failed to power on VM %s", vm_uuid)
            raise AHVFenceAgentException from err
        except AHVFenceAgentException as err:
            logging.error("Failed to retrieve etag from headers")
            raise AHVFenceAgentException from err

        return resp

    def _wait_for_task(self, task_uuid, timeout=None):
        if not task_uuid:
            logging.error("Task UUID was not provided")
            raise AHVFenceAgentException("Task UUID not provided")

        task_url = f"{self.task_url}/{task_uuid}"
        header_str = self._get_headers()
        task_resp = None
        interval = 5
        task_status = None

        if not timeout:
            timeout = MIN_TIMEOUT
        else:
            try:
                timeout = int(timeout)
            except ValueError:
                timeout = MIN_TIMEOUT

        while task_status != 'SUCCEEDED':
            if timeout <= 0:
                raise TaskTimedOutException(f"Task timed out: {task_uuid}")

            time.sleep(interval)
            timeout = timeout - interval

            try:
                task_resp = self.request(url=task_url, method='GET',
                                         headers=header_str, verify=self.verify)
                task_status = task_resp.json()['data']['status']
            except NutanixClientException as err:
                logging.error("Unable to retrieve task status")
                raise AHVFenceAgentException from err
            except Exception as err:
                logging.error("Unknown error")
                raise AHVFenceAgentException from err

            if task_status == 'FAILED':
                raise AHVFenceAgentException(f"Task failed, task uuid: {task_uuid}")

    def list_vms(self, filter_str=None, limit=None):
        vms = None
        vm_list = {}

        try:
            vms = self._get_all_vms(filter_str, limit)
        except NutanixClientException as err:
            logging.error("Failed to retrieve VM list")
            raise AHVFenceAgentException from err

        if not vms or not isinstance(vms, dict):
            logging.error("Failed to retrieve VM list")
            raise AHVFenceAgentException("Unable to get VM list")

        if 'data' not in vms:
            err = "Got invalid or empty VM list"
            logging.debug(err)
        else:
            for vm in vms['data']:
                vm_name = vm['name']
                ext_id = vm['extId']
                power_state = vm['powerState']
                vm_list[vm_name] = (ext_id, power_state)

        return vm_list

    def get_power_state(self, vm_name=None, vm_uuid=None):
        resp = None
        power_state = None

        if not vm_name and not vm_uuid:
            logging.error("Require at least one of VM name or VM UUID")
            raise InvalidArgsException("No arguments provided")

        if not vm_uuid:
            try:
                vm_uuid = self._get_vm_uuid(vm_name)
            except AHVFenceAgentException as err:
                logging.error("Unable to retrieve UUID of VM, %s", vm_name)
                raise AHVFenceAgentException from err

        try:
            resp = self._get_vm(vm_uuid)
        except AHVFenceAgentException as err:
            logging.error("Unable to retrieve power state of VM %s", vm_uuid)
            raise AHVFenceAgentException from err

        try:
            power_state = resp.json()['data']['powerState']
        except AHVFenceAgentException as err:
            logging.error("Failed to retrieve power state of VM %s", vm_uuid)
            raise AHVFenceAgentException from err

        return POWER_STATES[power_state]

    def set_power_state(self, vm_name=None, vm_uuid=None,
                        power_state='off', timeout=None):
        resp = None
        current_power_state = None
        power_state = power_state.lower()

        if not timeout:
            timeout = MIN_TIMEOUT

        if not vm_name and not vm_uuid:
            logging.error("Require at least one of VM name or VM UUID")
            raise InvalidArgsException("No arguments provided")

        if not vm_uuid:
            vm_uuid = self._get_vm_uuid(vm_name)

        try:
            current_power_state = self.get_power_state(vm_uuid=vm_uuid)
        except AHVFenceAgentException as err:
            raise AHVFenceAgentException from err

        if current_power_state.lower() == power_state.lower():
            logging.debug("VM already powered %s", power_state.lower())
            return

        if power_state.lower() == 'on':
            resp = self._power_on_off_vm(power_state, vm_uuid)
        elif power_state.lower() == 'off':
            resp = self._power_on_off_vm(power_state, vm_uuid)

        task_id = resp.json()['data']['extId']

        try:
            self._wait_for_task(task_id, timeout)
        except AHVFenceAgentException as err:
            logging.error("Failed to power %s VM", power_state.lower())
            logging.error("VM power %s task failed", power_state.lower())
            raise AHVFenceAgentException from err
        except TaskTimedOutException as err:
            logging.error("Timed out powering %s VM %s",
                          power_state.lower(), vm_uuid)
            raise TaskTimedOutException from err

        logging.debug("Powered %s VM, %s successfully",
                     power_state.lower(), vm_uuid)

    def power_cycle_vm(self, vm_name=None, vm_uuid=None, timeout=None):
        resp = None
        status = None

        if not timeout:
            timeout = MIN_TIMEOUT

        if not vm_name and not vm_uuid:
            logging.error("Require at least one of VM name or VM UUID")
            raise InvalidArgsException("No arguments provided")

        if not vm_uuid:
            vm_uuid = self._get_vm_uuid(vm_name)

        resp = self._power_cycle_vm(vm_uuid)
        task_id = resp.json()['data']['extId']

        try:
            self._wait_for_task(task_id, timeout)
        except AHVFenceAgentException as err:
            logging.error("Failed to power-cycle VM %s", vm_uuid)
            logging.error("VM power-cycle task failed with status, %s", status)
            raise AHVFenceAgentException from err
        except TaskTimedOutException as err:
            logging.error("Timed out power-cycling VM %s", vm_uuid)
            raise TaskTimedOutException from err


        logging.debug("Power-cycled VM, %s", vm_uuid)


def connect(options):
    host = options["--ip"]
    username = options["--username"]
    password = options["--password"]
    verify_ssl = True
    disable_warnings = False

    if "--ssl-insecure" in options:
        verify_ssl = False
        disable_warnings = True

    client = NutanixV4Client(host, username, password,
                             verify_ssl, disable_warnings)

    try:
        client.list_vms(limit=1)
    except AHVFenceAgentException as err:
        logging.error("Connection to Prism Central Failed")
        logging.error(err)
        fail(EC_LOGIN_DENIED)

    return client

def get_list(client, options):
    vm_list = None

    filter_str = options.get("--filter", None)
    limit = options.get("--limit", None)

    try:
        vm_list = client.list_vms(filter_str, limit)
    except AHVFenceAgentException as err:
        logging.error("Failed to list VMs")
        logging.error(err)
        fail(EC_GENERIC_ERROR)

    return vm_list

def get_power_status(client, options):
    vmid = None
    name = None
    power_state = None

    vmid = options.get("--uuid", None)
    name = options.get("--plug", None)

    if not vmid and not name:
        logging.error("Need VM name or VM UUID for power op")
        fail(EC_BAD_ARGS)
    try:
        power_state = client.get_power_state(vm_name=name, vm_uuid=vmid)
    except AHVFenceAgentException:
        fail(EC_GENERIC_ERROR)
    except InvalidArgsException:
        fail(EC_BAD_ARGS)

    return power_state

def set_power_status(client, options):
    action = options["--action"].lower()
    timeout = options.get("--power-timeout", None)
    vmid = options.get("--uuid", None)
    name = options.get("--plug", None)

    if not name and not vmid:
        logging.error("Need VM name or VM UUID to set power state of a VM")
        fail(EC_BAD_ARGS)

    try:
        client.set_power_state(vm_name=name, vm_uuid=vmid,
                               power_state=action, timeout=timeout)
    except AHVFenceAgentException as err:
        logging.error(err)
        fail(EC_GENERIC_ERROR)
    except TaskTimedOutException as err:
        logging.error(err)
        fail(EC_TIMED_OUT)
    except InvalidArgsException:
        fail(EC_BAD_ARGS)

def power_cycle(client, options):
    timeout = options.get("--power-timeout", None)
    vmid = options.get("--uuid", None)
    name = options.get("--plug", None)

    if not name and not vmid:
        logging.error("Need VM name or VM UUID to set power cycling a VM")
        fail(EC_BAD_ARGS)

    try:
        client.power_cycle_vm(vm_name=name, vm_uuid=vmid, timeout=timeout)
    except AHVFenceAgentException as err:
        logging.error(err)
        fail(EC_GENERIC_ERROR)
    except TaskTimedOutException as err:
        logging.error(err)
        fail(EC_TIMED_OUT)
    except InvalidArgsException:
        fail(EC_BAD_ARGS)

def define_new_opts():
    all_opt["filter"] = {
            "getopt": ":",
            "longopt": "filter",
            "help": """
            --filter=[filter]	Filter list, list VMs actions.
            --filter=\"name eq 'node1-vm'\"
            --filter=\"startswith(name,'node')\"
            --filter=\"name in ('node1-vm','node-3-vm')\" """,
            "required": "0",
            "shortdesc": "Filter list, get_list"
            "e.g: \"name eq 'node1-vm'\"",
            "order": 2
            }

def main():
    device_opt = [
            "ipaddr",
            "login",
            "passwd",
            "ssl",
            "notls",
            "web",
            "port",
            "filter",
            "method",
            "disable_timeout",
            "power_timeout"
            ]

    atexit.register(atexit_handler)
    define_new_opts()

    all_opt["power_timeout"]["default"] = str(MIN_TIMEOUT)
    options = check_input(device_opt, process_input(device_opt))
    docs = {}
    docs["shortdesc"] = "Fence agent for Nutanix AHV Cluster VMs."
    docs["longdesc"] = """fence_nutanix_ahv is a Power Fencing agent for \
virtual machines deployed on Nutanix AHV cluster with the AHV cluster \
being managed by Prism Central."""
    docs["vendorurl"] = "https://www.nutanix.com"
    show_docs(options, docs)
    run_delay(options)
    client = connect(options)

    result = fence_action(client, options, set_power_status, get_power_status,
                          get_list, reboot_cycle_fn=power_cycle
                         )

    sys.exit(result)


if __name__ == "__main__":
    main()
