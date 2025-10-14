#!@PYTHON@ -tt

import sys
import pycurl, io, json
import logging
import atexit

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, run_delay, EC_LOGIN_DENIED, EC_STATUS

if sys.version_info[0] > 2:
    import urllib.parse as urllib
else:
    import urllib

FENCE_STATUS_MAP = {True: "on", False: "off"}

HETZNER_SERVER_ACTIONS = {"on": "poweron", "off": "poweroff"}

HETZNER_STATUSES_OFF = ["off"]


def connect(opt):
    conn = pycurl.Curl()
    conn.base_url = opt["--api-url"]
    conn.setopt(
        pycurl.HTTPHEADER, ["Authorization: Bearer {}".format(opt["--api-token"])]
    )
    conn.setopt(pycurl.TIMEOUT, int(opt["--shell-timeout"]))
    try:
        send_command(
            conn, "/server_types", "GET", query_string={"per_page": 1}, pages_max=1
        )
    except Exception as e:
        logging.error(e)
        fail(EC_LOGIN_DENIED)
    return conn


def disconnect(conn):
    conn.close()


def send_command(conn, path, method, query_string={}, pages_max=None):
    results = []
    result = {"meta": {"pagination": {"next_page": 1}}}
    while result["meta"]["pagination"]["next_page"] and (
        not pages_max or len(results) < pages_max
    ):
        query_string["page"] = result["meta"]["pagination"]["next_page"]
        result = send_request(conn, path, method, query_string)
        results.append(result)
        if method != "GET":
            break
    return results


def send_request(conn, path, method, query_string={}):
    url = conn.base_url + path
    if query_string:
        url += "?" + urllib.urlencode(query_string)
    logging.debug("REQUEST {} {}".format(method, url))
    conn.setopt(pycurl.URL, url.encode("ascii"))
    web_buffer = io.BytesIO()
    if method == "GET":
        conn.setopt(pycurl.POST, 0)
    elif method == "POST":
        conn.setopt(pycurl.POSTFIELDS, "")
    conn.setopt(pycurl.WRITEFUNCTION, web_buffer.write)
    try:
        conn.perform()
    except Exception as e:
        raise (e)
    result_status = conn.getinfo(pycurl.HTTP_CODE)
    result_body = web_buffer.getvalue().decode("UTF-8")
    web_buffer.close()
    if len(result_body) > 0:
        result_body = json.loads(result_body)
    if 200 <= result_status < 300:
        logging.debug("RESULT {} {}".format(result_status, result_body))
    else:
        raise Exception("RESULT {} {}".format(result_status, result_body))
    return result_body


def get_server(conn, options):
    try:
        results = send_command(
            conn,
            "/servers",
            "GET",
            query_string={"name": options["--plug"]},
            pages_max=1,
        )
    except Exception as e:
        logging.error(e)
        fail(EC_STATUS)
    if len(results) != 1:
        fail(EC_STATUS)
    if len(results[0]["servers"]) == 1:
        return results[0]["servers"][0]
    else:
        logging.warning(
            "SCANNING over all servers! For better performance, set Hetzner Cloud server name to Fencing Agent plug (i.e. Pacemaker node name)."
        )
        try:
            results = send_command(conn, "/servers", "GET")
        except Exception as e:
            logging.error(e)
            fail(EC_STATUS)
        for result in results:
            if "servers" not in result:
                fail(EC_STATUS)
            for server in result["servers"]:
                ips = [
                    server["public_net"]["ipv4"]["ip"],
                    server["public_net"]["ipv6"]["ip"],
                ] + list(map(lambda e: e["ip"], server["private_net"]))
                if options["--plug"] in ips:
                    return server
            fail(EC_STATUS)


def get_power_status(conn, options):
    server = get_server(conn, options)
    status = FENCE_STATUS_MAP[server["status"] not in HETZNER_STATUSES_OFF]
    logging.debug("{} {} -> {}".format(server["id"], server["status"], status))
    return status


def set_power_status(conn, options):
    server = get_server(conn, options)
    logging.debug(server)
    logging.debug(options)
    path = "/servers/{}/actions/{}".format(
        server["id"], HETZNER_SERVER_ACTIONS[options["--action"]]
    )
    try:
        send_command(conn, path, "POST")
    except Exception as e:
        logging.error(e)
        fail(EC_STATUS)


def get_list(conn, options):
    outlets = {}
    try:
        results = send_command(conn, "/servers", "GET")
    except Exception as e:
        logging.error(e)
        fail(EC_STATUS)
    for result in results:
        if "servers" not in result:
            fail(EC_STATUS)
        for server in result["servers"]:
            status = FENCE_STATUS_MAP[server["status"] not in HETZNER_STATUSES_OFF]
            logging.debug("{} {} -> {}".format(server["id"], server["status"], status))
            outlets[server["name"]] = ("", status)
    return outlets


def define_new_opts():
    all_opt["api_url"] = {
        "getopt": ":",
        "longopt": "api-url",
        "help": "--api-url=[url]                API URL",
        "default": "https://api.hetzner.cloud/v1",
        "required": "0",
        "shortdesc": "API URL",
        "order": 0,
    }
    all_opt["api_token"] = {
        "getopt": ":",
        "longopt": "api-token",
        "help": "--api-token=[token]            API token",
        "required": "1",
        "shortdesc": "API token",
        "order": 0,
    }


def main():
    device_opt = [
        "api_url",
        "api_token",
        "no_password",
        "port",
        "web",
    ]

    atexit.register(atexit_handler)
    define_new_opts()

    all_opt["shell_timeout"]["default"] = "5"
    all_opt["power_wait"]["default"] = "5"

    options = check_input(device_opt, process_input(device_opt))

    docs = {}
    docs["shortdesc"] = "Fence agent for Hetzner Cloud"
    docs["longdesc"] = """fence_hetzner_cloud is a Power Fencing agent which can be \
used with Hetzner Cloud via its API to fence cloud servers."""
    docs["vendorurl"] = "https://www.hetzner.com"
    show_docs(options, docs)

    run_delay(options)

    conn = connect(options)
    atexit.register(disconnect, conn)

    result = fence_action(conn, options, set_power_status, get_power_status, get_list)

    sys.exit(result)


if __name__ == "__main__":
    main()
