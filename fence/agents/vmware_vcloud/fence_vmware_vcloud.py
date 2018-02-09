#!@PYTHON@ -tt

import sys
import pycurl, io
import logging
import atexit
import xml.etree.ElementTree as etree
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, run_delay, EC_LOGIN_DENIED, EC_STATUS

state = {"POWERED_ON": "on", 'POWERED_OFF': "off", 'SUSPENDED': "off"}

def get_power_status(conn, options):
        try:
                VM = send_command(conn, "vApp/vm-{}".format(options["--plug"]))
        except Exception as e:
                logging.debug("Failed: {}".format(e))
                fail(EC_STATUS)

        options["id"] = VM.attrib['href'].split('/vm-', 1)[1]

        if (VM.attrib['status'] == '3'):
                return state['SUSPENDED']
        elif (VM.attrib['status'] == '4'):
                return state['POWERED_ON']
        elif (VM.attrib['status'] == '8'):
                return state['POWERED_OFF']
        return EC_STATUS


def set_power_status(conn, options):
        action = {
                "on" : "powerOn",
                "off" : "powerOff",
                "shutdown": "shutdown",
                "suspend": "suspend",
                "reset": "reset"
                }[options["--action"]]
        try:
                VM = send_command(conn, "vApp/vm-{}/power/action/{}".format(options["--plug"], action), "POST")
        except Exception as e:
                logging.debug("Failed: {}".format(e))
                fail(EC_STATUS)

def get_list(conn, options):
        outlets = {}

        VMsResponse = send_command(conn, "vms/query")

        for VM in VMsResponse.iter('{http://www.vmware.com/vcloud/v1.5}VMRecord'):
                if '/vApp/' not in VM.attrib['href']:
                        continue
                uuid = (VM.attrib['href'].split('/vm-', 1))[1]
                outlets['['+ uuid + '] ' + VM.attrib['containerName'] + '\\' + VM.attrib['name']] = (VM.attrib['status'], state[VM.attrib['status']])

        return outlets

def connect(opt):
        conn = pycurl.Curl()

        ## setup correct URL
        if "--ssl" in opt or "--ssl-secure" in opt or "--ssl-insecure" in opt:
                conn.base_url = "https:"
        else:
                conn.base_url = "http:"

        conn.base_url += "//" + opt["--ip"] + ":" + str(opt["--ipport"]) + opt["--api-path"] + "/"

        ## send command through pycurl
        conn.setopt(pycurl.HTTPHEADER, [
                "Accept: application/*+xml;version=1.5",
        ])

        conn.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_BASIC)
        conn.setopt(pycurl.USERPWD, opt["--username"] + ":" + opt["--password"])

        conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
        if "--ssl" in opt or "--ssl-secure" in opt:
                conn.setopt(pycurl.SSL_VERIFYPEER, 1)
                conn.setopt(pycurl.SSL_VERIFYHOST, 2)
        elif "--ssl-insecure" in opt:
                conn.setopt(pycurl.SSL_VERIFYPEER, 0)
                conn.setopt(pycurl.SSL_VERIFYHOST, 0)

        headers = {}
        try:
                result = send_command(conn, "sessions", "POST", headers)
        except Exception as e:
                logging.debug("Failed: {}".format(e))
                fail(EC_LOGIN_DENIED)

        # set session id for later requests
        conn.setopt(pycurl.HTTPHEADER, [
               "Accept: application/*+xml;version=1.5",
               "x-vcloud-authorization: {}".format(headers['x-vcloud-authorization']),
        ])

        return conn

def disconnect(conn):
        send_command(conn, "session", "DELETE")
        conn.close()

def parse_headers(data):
        headers = {}
        data = data.split("\r\n")
        for header_line in data[1:]:
                if ':' not in header_line:
                        break
                name, value = header_line.split(':', 1)
                name = name.strip()
                value = value.strip()
                name = name.lower()
                headers[name] = value

        return headers

def send_command(conn, command, method="GET", headers={}):
        url = conn.base_url + command

        conn.setopt(pycurl.URL, url.encode("ascii"))

        web_buffer = io.BytesIO()
        headers_buffer = io.BytesIO()

        if method == "GET":
                conn.setopt(pycurl.POST, 0)
        elif method == "POST":
                conn.setopt(pycurl.POSTFIELDS, "")
        elif method == "DELETE":
                conn.setopt(pycurl.CUSTOMREQUEST, "DELETE")

        conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)
        conn.setopt(pycurl.HEADERFUNCTION, headers_buffer.write)

        try:
                conn.perform()
        except Exception as e:
                raise Exception(e[1])

        rc = conn.getinfo(pycurl.HTTP_CODE)
        result = web_buffer.getvalue().decode()
        headers.update(parse_headers(headers_buffer.getvalue().decode()))

        headers_buffer.close()
        web_buffer.close()

        if len(result) > 0:
                result = etree.fromstring(result)

        if rc != 200 and rc != 202 and rc != 204:
                raise Exception("{}: {}".format(rc, result["value"]["messages"][0]["default_message"]))

        logging.debug("url: {}".format(url))
        logging.debug("method: {}".format(method))
        logging.debug("response code: {}".format(rc))
        logging.debug("result: {}\n".format(result))

        return result

def define_new_opts():
        all_opt["api_path"] = {
                "getopt" : ":",
                "longopt" : "api-path",
                "help" : "--api-path=[path]              The path part of the API URL",
                "default" : "/api",
                "required" : "0",
                "shortdesc" : "The path part of the API URL",
                "order" : 2}

def main():
        device_opt = [
                "ipaddr",
                "api_path",
                "login",
                "passwd",
                "ssl",
                "notls",
                "web",
                "port",
        ]

        atexit.register(atexit_handler)
        define_new_opts()

        all_opt["shell_timeout"]["default"] = "5"
        all_opt["power_wait"]["default"] = "1"

        options = check_input(device_opt, process_input(device_opt))

        docs = {}
        docs["shortdesc"] = "Fence agent for VMware vCloud Director API"
        docs["longdesc"] = "fence_vmware_vcloud is an I/O Fencing agent which can be used with VMware vCloud Director API to fence virtual machines."
        docs["vendorurl"] = "https://www.vmware.com"
        show_docs(options, docs)

        ####
        ## Fence operations
        ####
        run_delay(options)

        conn = connect(options)
        atexit.register(disconnect, conn)

        result = fence_action(conn, options, set_power_status, get_power_status, get_list)

        sys.exit(result)

if __name__ == "__main__":
        main()
