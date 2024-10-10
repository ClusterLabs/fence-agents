#!@PYTHON@ -tt
# -*- coding: utf-8 -*-

import sys
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS, EC_LOGIN_DENIED, EC_INVALID_PRIVILEGES, run_delay
import requests
import ast
import urllib3
import json
import logging

from requests.exceptions import ConnectionError


###################################################################################
# Inner functions


def authorize_and_get_cookie(skala_ip, login, password, options):
    URL0 = proto + str(skala_ip) + '/api/0/auth'
    cred = {
        "login" : str(login),
        "password" : str(password)
    }
    
    try:
        with requests.Session() as session:
            session.post(url=URL0, data=cred, verify=ssl_verify)
            cookie = session.cookies.get_dict()
    except:
        logging.exception('Exception occured.')
        fail(EC_LOGIN_DENIED)
    if 'api_token' in cookie:
        return cookie
    else:
        fail(EC_LOGIN_DENIED)


def logout(skala_ip):
    URL1 = proto + str(skala_ip) + '/api/0/logout'
    
    try:
        with requests.Session() as session:
            session.post(url=URL1, verify=ssl_verify, cookies=cookie)
    except:
        ## Logout; we do not care about result as we will end in any case
        pass


def get_vm_id(skala_ip, uuid, options, cookie):
    URL2 = proto + str(skala_ip) + '/api/0/vm'
    parameters = {
        "uuid": str(uuid)
    }
    
    vm_info = requests.get(url=URL2, verify=ssl_verify, params=parameters, cookies=cookie)
    jvm_info = vm_info.json()
    if jvm_info["vm_list"]["items"] == []:
        raise NameError('Can not find VM by uuid.')
    logging.debug("VM_INFO:\n{}".format(json.dumps(vm_info.json(), indent=4, sort_keys=True)))
    return jvm_info["vm_list"]["items"][0]["vm_id"]


def vm_task(skala_ip, vm_id, command, options, cookie):

    # command(str) – Command for vm: ‘vm_start’, ‘vm_stop’, ‘vm_restart’,
    # ‘vm_suspend’, ‘vm_resume’, ‘vm_pause’, ‘vm_reset’
    # main_request_id(TaskId) – Parent task id
    # graceful(bool) – vm_stop command parameter, graceful or not, default
    # false - *args[0]
    # force(bool) – vm_stop command parameter, force stop or not, default
    # false - *args[1]
    
    if "--graceful" in options:
        graceful = True
    else:
        graceful = False
    if "--force" in options:
        force = True
    else:
        force = False

    URL3 = proto + str(skala_ip) + '/api/0/vm/' + str(vm_id) + '/task'

    logging.debug("vm_task skala_ip: " + str(skala_ip))
    logging.debug("vm_task vm_id: " + str(vm_id))
    logging.debug("vm_task command: " + str(command))
    logging.debug("vm_task cookie: " + str(cookie))


    def checking(vm_id, command, graceful, force):
        firstcondition = type(vm_id) is int
        secondcondition = command in ['vm_start', 'vm_stop', 'vm_restart', 'vm_suspend', 'vm_resume', 'vm_pause', 'vm_reset']
        thirdcondition = type(graceful) is bool
        fourthcondition = type(force) is bool
        return firstcondition * secondcondition * thirdcondition * fourthcondition

    if not checking(vm_id, command, graceful, force):
        print('Wrong parameters! \n'
              'command(str) – Command for vm: ‘vm_start’, ‘vm_stop’, \n'
              '‘vm_restart’,‘vm_suspend’, ‘vm_resume’, ‘vm_pause’, ‘vm_reset’ \n'
              'graceful(bool) – vm_stop command parameter, graceful or not, default false \n'
              'force(bool) – vm_stop command parameter, force stop or not, default false \n'
              )
    else:
        parameters = {
            "command": command,
            "graceful": graceful,
            "force": force
        }

    with requests.Session() as session:
        response = session.post(url=URL3, params=parameters, verify=ssl_verify, cookies=cookie)
    if response.status_code != 200:
        raise Exception('Invalid response code from server: {}.'.format(response.status_code))
    return

######################################################################################

def get_power_status(conn, options):
    state = {"RUNNING": "on", "PAUSED": "on", "STOPPED": "off", "SUSPENDED": "off", "ERROR": "off", "DELETED": "off",
             "CREATING": "off", "FAILED_TO_CREATE": "off", "NODE_OFFLINE": "off", "STARTING": "off", "STOPPING": "on"}

    URL4 = proto + options["--ip"] + '/api/0/vm/'
    parameters = {
        "uuid": str(options["--plug"])
    }

    vm_info = requests.get(url=URL4, params=parameters, verify=ssl_verify, cookies=cookie)
    jvm_info = vm_info.json()
    if jvm_info["vm_list"]["items"] == []:
        raise NameError('Can not find VM by uuid.')
    logging.debug("VM_INFO:\n{}".format(json.dumps(vm_info.json(), indent=4, sort_keys=True)))
    status_v = jvm_info["vm_list"]["items"][0]["status"]
    if status_v not in state:
        raise Exception('Unknown VM state: {}.'.format(status_v))
    return state[status_v]


def set_power_status(conn, options):
    action = {
        "on" : "vm_start",
        "reboot": "vm_restart",
        "off" : "vm_stop"
        }

    vm_id_v = get_vm_id(options["--ip"], options["--plug"], options, cookie)
    vm_task(options["--ip"], vm_id_v, action[options["--action"]], options, cookie)
    return


def get_list(conn, options):
    outlets = {}
    URL5 = proto + options["--ip"] + '/api/0/vm'
    
    vm_info = requests.get(url=URL5, verify=ssl_verify, cookies=cookie)
    jvm_info = vm_info.json()
    list_jvm = jvm_info["vm_list"]["items"]
    for elem in list_jvm:
        outlets[elem["name"]] = (elem["uuid"], None)
    return outlets


def define_new_opts():
    all_opt["graceful"] = {
            "getopt" : "",
            "longopt" : "graceful",
            "help" : "--graceful                     vm_stop command parameter, graceful stop or not, default false", 
            "required" : "0",
            "shortdesc" : "vm_stop command parameter, graceful stop or not, default false",
            "order" : 1}

    all_opt["force"] = {
            "getopt" : "",
            "longopt" : "force",
            "help" : "--force                        vm_stop command parameter, force stop or not, default false",
            "required" : "0",
            "shortdesc" : "vm_stop command parameter, force stop or not, default false", 
            "order" : 1}


def main():
    global cookie, proto, ssl_verify
    define_new_opts()
    device_opt = ["ipaddr", "login", "passwd", "port", "web", "ssl", "verbose", "graceful", "force"]
    
    atexit.register(atexit_handler)
    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Skala-R Fence agent"
    docs["longdesc"] = "fence_skalar is a Power Fencing agent for Skala-R."
    docs["vendorurl"] = "https://www.skala-r.ru/"
    show_docs(options, docs)
    options["eol"] = "\r"
    
    run_delay(options)
    
    proto = "https://"
    if "--ssl-secure" in options:
        ssl_verify = True
    elif "--ssl-insecure" in options:
        ssl_verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    else:
        proto = "http://"
        ssl_verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    cookie = authorize_and_get_cookie(options["--ip"], options["--username"], options["--password"], options)
    atexit.register(logout, options["--ip"])
    
    logging.debug("OPTIONS: " + str(options) + "\n")
    
    try:
        result = fence_action(None, options, set_power_status, get_power_status, get_list)
        sys.exit(result)
    except Exception:
        logging.exception('Exception occured.')
        fail(EC_STATUS)

if __name__ == "__main__":
    main()
