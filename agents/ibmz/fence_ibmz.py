#!@PYTHON@ -tt

# Copyright (c) 2020 IBM Corp.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see
# <http://www.gnu.org/licenses/>.

import atexit
import logging
import time
import sys

import requests
from requests.packages import urllib3

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail_usage, run_delay, EC_GENERIC_ERROR

DEFAULT_POWER_TIMEOUT = '300'
ERROR_NOT_FOUND = ("{obj_type} {obj_name} not found in this HMC. "
                   "Attention: names are case-sensitive.")

class ApiClientError(Exception):
    """
    Base exception for all API Client related errors.
    """

class ApiClientRequestError(ApiClientError):
    """
    Raised when an API request ends in error
    """

    def __init__(self, req_method, req_uri, status, reason, message):
        self.req_method = req_method
        self.req_uri = req_uri
        self.status = status
        self.reason = reason
        self.message = message
        super(ApiClientRequestError, self).__init__()

    def __str__(self):
        return (
            "API request failed, details:\n"
            "HTTP Request : {req_method} {req_uri}\n"
            "HTTP Response status: {status}\n"
            "Error reason: {reason}\n"
            "Error message: {message}\n".format(
                req_method=self.req_method, req_uri=self.req_uri,
                status=self.status, reason=self.reason, message=self.message)
        )

class APIClient(object):
    DEFAULT_CONFIG = {
        # how many connection-related errors to retry on
        'connect_retries': 3,
        # how many times to retry on read errors (after request was sent to the
        # server)
        'read_retries': 3,
        # http methods that should be retried
        'method_whitelist': ['HEAD', 'GET', 'OPTIONS'],
        # limit of redirects to perform to avoid loops
        'redirect': 5,
        # how long to wait while establishing a connection
        'connect_timeout': 30,
        # how long to wait for asynchronous operations (jobs) to complete
        'operation_timeout': 900,
        # how long to wait between bytes sent by the remote side
        'read_timeout': 300,
        # default API port
        'port': 6794,
        # validate ssl certificates
        'ssl_verify': False,
        # load on activate is set in the HMC activation profile and therefore
        # no additional load is executed by the fence agent
        'load_on_activate': False
    }
    LABEL_BY_OP_MODE = {
        'classic': {
            'nodes': 'logical-partitions',
            'state-on': 'operating',
            'start': 'load',
            'stop': 'deactivate'
        },
        'dpm': {
            'nodes': 'partitions',
            'state-on': 'active',
            'start': 'start',
            'stop': 'stop'
        }
    }
    def __init__(self, host, user, passwd, config=None):
        self.host = host
        if not passwd:
            raise ValueError('Password cannot be empty')
        self.passwd = passwd
        if not user:
            raise ValueError('Username cannot be empty')
        self.user = user
        self._cpc_cache = {}
        self._session = None
        self._config = self.DEFAULT_CONFIG.copy()
        # apply user defined values
        if config:
            self._config.update(config)

    def _create_session(self):
        """
        Create a new requests session and apply config values
        """
        session = requests.Session()
        retry_obj = urllib3.Retry(
            # setting a total is necessary to cover SSL related errors
            total=max(self._config['connect_retries'],
                      self._config['read_retries']),
            connect=self._config['connect_retries'],
            read=self._config['read_retries'],
            method_whitelist=self._config['method_whitelist'],
            redirect=self._config['redirect']
        )
        session.mount('http://', requests.adapters.HTTPAdapter(
            max_retries=retry_obj))
        session.mount('https://', requests.adapters.HTTPAdapter(
            max_retries=retry_obj))
        return session

    def _get_mode_labels(self, cpc):
        """
        Return the map of labels that corresponds to the cpc operation mode
        """
        if self.is_dpm_enabled(cpc):
            return self.LABEL_BY_OP_MODE['dpm']
        return self.LABEL_BY_OP_MODE['classic']

    def _get_partition(self, cpc, partition):
        """
        Return the properties of the specified partition. Raises ValueError if
        it cannot be found.
        """
        # HMC API's documentation says it'll return an empty array when no
        # matches are found but for a CPC in classic mode it returns in fact
        # 404, so we handle this accordingly. Remove the extra handling below
        # once this behavior has been fixed on the API's side.
        label_map = self._get_mode_labels(cpc)
        resp = self._request('get', '{}/{}?name={}'.format(
            self._cpc_cache[cpc]['object-uri'], label_map['nodes'], partition),
                             valid_codes=[200, 404])

        if label_map['nodes'] not in resp or not resp[label_map['nodes']]:
            raise ValueError(ERROR_NOT_FOUND.format(
                obj_type='LPAR/Partition', obj_name=partition))
        return resp[label_map['nodes']][0]

    def _partition_switch_power(self, cpc, partition, action):
        """
        Perform the API request to start (power on) or stop (power off) the
        target partition and wait for the job to finish.
        """
        # retrieve partition's uri
        part_uri = self._get_partition(cpc, partition)['object-uri']
        label_map = self._get_mode_labels(cpc)

        # in dpm mode the request must have empty body
        if self.is_dpm_enabled(cpc):
            body = None
        # in classic mode we make sure the operation is executed
        # even if the partition is already on
        else:
            body = {'force': True}
            # when powering on the partition must be activated first
            if action == 'start':
                op_uri = '{}/operations/activate'.format(part_uri)
                job_resp = self._request(
                    'post', op_uri, body=body, valid_codes=[202])
                # always wait for activate otherwise the load (start)
                # operation will fail
                if self._config['operation_timeout'] == 0:
                    timeout = self.DEFAULT_CONFIG['operation_timeout']
                else:
                    timeout = self._config['operation_timeout']
                logging.debug(
                    'waiting for activate (timeout %s secs)', timeout)
                self._wait_for_job('post', op_uri, job_resp['job-uri'],
                                   timeout=timeout)
                if self._config['load_on_activate']:
                    return

        # trigger the start job
        op_uri = '{}/operations/{}'.format(part_uri, label_map[action])
        job_resp = self._request('post', op_uri, body=body, valid_codes=[202])
        if self._config['operation_timeout'] == 0:
            return
        logging.debug('waiting for %s (timeout %s secs)',
                      label_map[action], self._config['operation_timeout'])
        self._wait_for_job('post', op_uri, job_resp['job-uri'],
                           timeout=self._config['operation_timeout'])

    def _request(self, method, uri, body=None, headers=None, valid_codes=None):
        """
        Perform a request to the HMC API
        """
        assert method in ('delete', 'head', 'get', 'post', 'put')

        url = 'https://{host}:{port}{uri}'.format(
            host=self.host, port=self._config['port'], uri=uri)
        if not headers:
            headers = {}

        if self._session is None:
            raise ValueError('You need to log on first')
        method = getattr(self._session, method)
        timeout = (
            self._config['connect_timeout'], self._config['read_timeout'])
        response = method(url, json=body, headers=headers,
                          verify=self._config['ssl_verify'], timeout=timeout)

        if valid_codes and response.status_code not in valid_codes:
            reason = '(no reason)'
            message = '(no message)'
            if response.headers.get('content-type') == 'application/json':
                try:
                    json_resp = response.json()
                except ValueError:
                    pass
                else:
                    reason = json_resp.get('reason', reason)
                    message = json_resp.get('message', message)
            else:
                message = '{}...'.format(response.text[:500])
            raise ApiClientRequestError(
                response.request.method, response.request.url,
                response.status_code, reason, message)

        if response.status_code == 204:
            return dict()
        try:
            json_resp = response.json()
        except ValueError:
            raise ApiClientRequestError(
                response.request.method, response.request.url,
                response.status_code, '(no reason)',
                'Invalid JSON content in response')

        return json_resp

    def _update_cpc_cache(self, cpc_props):
        self._cpc_cache[cpc_props['name']] = {
            'object-uri': cpc_props['object-uri'],
            'dpm-enabled': cpc_props.get('dpm-enabled', False)
        }

    def _wait_for_job(self, req_method, req_uri, job_uri, timeout):
        """
        Perform API requests to check for job status until it has completed
        or the specified timeout is reached
        """
        op_timeout = time.time() + timeout
        while time.time() < op_timeout:
            job_resp = self._request("get", job_uri)
            if job_resp['status'] == 'complete':
                if job_resp['job-status-code'] in (200, 201, 204):
                    return
                raise ApiClientRequestError(
                    req_method, req_uri,
                    job_resp.get('job-status-code', '(no status)'),
                    job_resp.get('job-reason-code', '(no reason)'),
                    job_resp.get('job-results', {}).get(
                        'message', '(no message)')
                )
            time.sleep(1)
        raise ApiClientError('Timed out while waiting for job completion')

    def cpc_list(self):
        """
        Return a list of CPCs in the format {'name': 'cpc-name', 'status':
        'operating'}
        """
        list_resp = self._request("get", "/api/cpcs", valid_codes=[200])
        ret = []
        for cpc_props in list_resp['cpcs']:
            self._update_cpc_cache(cpc_props)
            ret.append({
                'name': cpc_props['name'], 'status': cpc_props['status']})
        return ret

    def is_dpm_enabled(self, cpc):
        """
        Return True if CPC is in DPM mode, False for classic mode
        """
        if cpc in self._cpc_cache:
            return self._cpc_cache[cpc]['dpm-enabled']
        list_resp = self._request("get", "/api/cpcs?name={}".format(cpc),
                                  valid_codes=[200])
        if not list_resp['cpcs']:
            raise ValueError(ERROR_NOT_FOUND.format(
                obj_type='CPC', obj_name=cpc))
        self._update_cpc_cache(list_resp['cpcs'][0])
        return self._cpc_cache[cpc]['dpm-enabled']

    def logon(self):
        """
        Open a session with the HMC API and store its ID
        """
        self._session = self._create_session()
        logon_body = {"userid": self.user, "password": self.passwd}
        logon_resp = self._request("post", "/api/sessions", body=logon_body,
                                   valid_codes=[200, 201])
        self._session.headers["X-API-Session"] = logon_resp['api-session']

    def logoff(self):
        """
        Close/delete the HMC API session
        """
        if self._session is None:
            return
        self._request("delete", "/api/sessions/this-session",
                      valid_codes=[204])
        self._cpc_cache = {}
        self._session = None

    def partition_list(self, cpc):
        """
        Return a list of partitions in the format {'name': 'part-name',
        'status': 'on'}
        """
        label_map = self._get_mode_labels(cpc)
        list_resp = self._request(
            'get', '{}/{}'.format(
                self._cpc_cache[cpc]['object-uri'], label_map['nodes']),
            valid_codes=[200])
        status_map = {label_map['state-on']: 'on'}
        return [{'name': part['name'],
                 'status': status_map.get(part['status'].lower(), 'off')}
                for part in list_resp[label_map['nodes']]]

    def partition_start(self, cpc, partition):
        """
        Power on a partition
        """
        self._partition_switch_power(cpc, partition, 'start')

    def partition_status(self, cpc, partition):
        """
        Return the current status of a partition (on or off)
        """
        label_map = self._get_mode_labels(cpc)

        part_props = self._get_partition(cpc, partition)
        if part_props['status'].lower() == label_map['state-on']:
            return 'on'
        return 'off'

    def partition_stop(self, cpc, partition):
        """
        Power off a partition
        """
        self._partition_switch_power(cpc, partition, 'stop')

def parse_plug(options):
    """
    Extract cpc and partition from specified plug value
    """
    try:
        cpc, partition = options['--plug'].strip().split('/', 1)
    except ValueError:
        fail_usage('Please specify nodename in format cpc/partition')
    cpc = cpc.strip()
    if not cpc or not partition:
        fail_usage('Please specify nodename in format cpc/partition')
    return cpc, partition

def get_power_status(conn, options):
    logging.debug('executing get_power_status')
    status = conn.partition_status(*parse_plug(options))
    return status

def set_power_status(conn, options):
    logging.debug('executing set_power_status')
    if options['--action'] == 'on':
        conn.partition_start(*parse_plug(options))
    elif options['--action'] == 'off':
        conn.partition_stop(*parse_plug(options))
    else:
        fail_usage('Invalid action {}'.format(options['--action']))

def get_outlet_list(conn, options):
    logging.debug('executing get_outlet_list')
    result = {}
    for cpc in conn.cpc_list():
        for part in conn.partition_list(cpc['name']):
            result['{}/{}'.format(cpc['name'], part['name'])] = (
                part['name'], part['status'])
    return result

def disconnect(conn):
    """
    Close the API session
    """
    try:
        conn.logoff()
    except Exception as exc:
        logging.exception('Logoff failed: ')
        sys.exit(str(exc))

def set_opts():
    """
    Define the options supported by this agent
    """
    device_opt = [
        "ipaddr",
        "ipport",
        "login",
        "passwd",
        "port",
        "connect_retries",
        "connect_timeout",
        "operation_timeout",
        "read_retries",
        "read_timeout",
        "ssl_secure",
        "load_on_activate",
    ]

    all_opt["ipport"]["default"] = APIClient.DEFAULT_CONFIG['port']
    all_opt["power_timeout"]["default"] = DEFAULT_POWER_TIMEOUT
    port_desc = ("Physical plug id in the format cpc-name/partition-name "
                 "(case-sensitive)")
    all_opt["port"]["shortdesc"] = port_desc
    all_opt["port"]["help"] = (
        "-n, --plug=[id]                {}".format(port_desc))
    all_opt["connect_retries"] = {
        "getopt" : ":",
        "longopt" : "connect-retries",
        "help" : "--connect-retries=[number]     How many times to "
                 "retry on connection errors",
        "default" : APIClient.DEFAULT_CONFIG['connect_retries'],
        "type" : "integer",
        "required" : "0",
        "shortdesc" : "How many times to retry on connection errors",
        "order" : 2
    }
    all_opt["read_retries"] = {
        "getopt" : ":",
        "longopt" : "read-retries",
        "help" : "--read-retries=[number]        How many times to "
                 "retry on errors related to reading from server",
        "default" : APIClient.DEFAULT_CONFIG['read_retries'],
        "type" : "integer",
        "required" : "0",
        "shortdesc" : "How many times to retry on read errors",
        "order" : 2
    }
    all_opt["connect_timeout"] = {
        "getopt" : ":",
        "longopt" : "connect-timeout",
        "help" : "--connect-timeout=[seconds]    How long to wait to "
                 "establish a connection",
        "default" : APIClient.DEFAULT_CONFIG['connect_timeout'],
        "type" : "second",
        "required" : "0",
        "shortdesc" : "How long to wait to establish a connection",
        "order" : 2
    }
    all_opt["operation_timeout"] = {
        "getopt" : ":",
        "longopt" : "operation-timeout",
        "help" : "--operation-timeout=[seconds]  How long to wait for "
                 "power operation to complete (0 = do not wait)",
        "default" : APIClient.DEFAULT_CONFIG['operation_timeout'],
        "type" : "second",
        "required" : "0",
        "shortdesc" : "How long to wait for power operation to complete",
        "order" : 2
    }
    all_opt["read_timeout"] = {
        "getopt" : ":",
        "longopt" : "read-timeout",
        "help" : "--read-timeout=[seconds]       How long to wait "
                 "to read data from server",
        "default" : APIClient.DEFAULT_CONFIG['read_timeout'],
        "type" : "second",
        "required" : "0",
        "shortdesc" : "How long to wait for server data",
        "order" : 2
    }
    all_opt["load_on_activate"] = {
        "getopt" : "",
        "longopt" : "load-on-activate",
        "help" : "--load-on-activate             Rely on the HMC to perform "
                 "a load operation on activation",
        "required" : "0",
        "order" : 3
    }
    return device_opt

def main():
    """
    Agent entry point
    """
    # register exit handler used by pacemaker
    atexit.register(atexit_handler)

    # prepare accepted options
    device_opt = set_opts()

    # parse options provided on input
    options = check_input(device_opt, process_input(device_opt))

    docs = {
        "shortdesc": "Fence agent for IBM z LPARs",
        "longdesc": (
            "fence_ibmz is a Power Fencing agent which uses the HMC Web "
            "Services API to fence IBM z LPARs."),
        "vendorurl": "http://www.ibm.com"
    }
    show_docs(options, docs)

    run_delay(options)

    # set underlying library's logging and ssl config according to specified
    # options
    requests_log = logging.getLogger("urllib3")
    requests_log.propagate = True
    if "--verbose" in options:
        requests_log.setLevel(logging.DEBUG)
    if "--ssl-insecure" in options:
        urllib3.disable_warnings(
            category=urllib3.exceptions.InsecureRequestWarning)

    hmc_address = options["--ip"]
    hmc_userid = options["--username"]
    hmc_password = options["--password"]
    config = {
        'connect_retries': int(options['--connect-retries']),
        'read_retries': int(options['--read-retries']),
        'operation_timeout': int(options['--operation-timeout']),
        'connect_timeout': int(options['--connect-timeout']),
        'read_timeout': int(options['--read-timeout']),
        'port': int(options['--ipport']),
        'ssl_verify': bool('--ssl-insecure' not in options),
        'load_on_activate': bool('--load-on-activate' in options),
    }
    try:
        conn = APIClient(hmc_address, hmc_userid, hmc_password, config)
        conn.logon()
        atexit.register(disconnect, conn)
        result = fence_action(conn, options, set_power_status,
                              get_power_status, get_outlet_list)
    except Exception:
        logging.exception('Exception occurred: ')
        result = EC_GENERIC_ERROR
    sys.exit(result)

if __name__ == "__main__":
    main()
