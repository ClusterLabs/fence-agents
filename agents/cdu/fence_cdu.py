#!@PYTHON@ -tt
#    fence_cdu - fence agent for a Sentry Switch CDU.
#
#    Copyright (C) 2012 Canonical Ltd.
#    Copyright (C) 2021 SUSE Linux GmbH <trenn@suse.de>
#
#    Authors: Andres Rodriguez <andres.rodriguez@canonical.com>
#             Thomas Renninger <trenn@suse.de>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3 of the License.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

#####
##
## The Following Agent Has Been Tested On:
##
##  Model                Firmware
## +---------------------------------------------+
## Sentry Switched CDU   6a
## Sentry Switched CDU   7.1c <trenn@suse.de>
## Sentry Switched CDU   7.1f <trenn@suse.de>
## Sentry Switched PDU   8.0i <trenn@suse.de>
##
##
#####

import sys, re, pexpect, atexit, logging
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_TIMED_OUT, run_command, frun, EC_STATUS

def get_power_status(conn, options):
    exp_result = 0
    outlets = {}
    try:
        if options["api-version"] == "8":
            conn.send("STATUS ALL\r\n")
        else:
            conn.send("STATUS\r\n")
        conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
        lines = conn.before.split("\n")
        if options["api-version"] == "8":
            #  AA13  Arm-Console3                     Wake On        On     Normal
            #  AA14  Master_Outlet_14                 Wake On        On     Normal
            show_re = re.compile(r'(\w+)\s+(\S+)\s+(On|Idle On|Off|Wake On)\s+(On|Off)')
        else:
            #    .A12     TowerA_Outlet12           On         Idle On
            #    .A12     test-01                   On         Idle On
            show_re = re.compile(r'(\.\w+)\s+(\w+|\w+\W\w+)\s+(On|Off)\s+(On|Idle On|Off|Wake On)')
        for line in lines:
            res = show_re.search(line)
            if res != None:
                plug_id = res.group(1)
                plug_name = res.group(2)
                print(plug_name)
                plug_state = res.group(3)
                if options["api-version"] == "8":
                    plug_state = res.group(4)
                outlets[plug_name] = (plug_id, plug_state)
    except pexpect.EOF:
        fail(EC_CONNECTION_LOST)
    except pexpect.TIMEOUT:
        fail(EC_TIMED_OUT)
    try:
        (_, status) = outlets[options["--plug"]]
        return status.lower().strip()
    except KeyError:
        fail(EC_STATUS)

def set_power_status(conn, options):
        outlets = {}
        action = { 'on' : "on", 'off': "off" }[options["--action"]]
        try:
            conn.send("LIST OUTLETS\r\n")
            conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
            lines = conn.before.split("\n")
            # if options["api-version"] == "8":
            #    AA13  Arm-Console3
            #    AA14  Master_Outlet_14
            # else:
            #    .A12     TowerA_Outlet12
            #    .A12     test-01
            show_re = re.compile(r'(\S+)\s+(\w+|\w+\W\w+)\s+')
            for line in lines:
                res = show_re.search(line)
                if res != None:
                    outlets[res.group(2)] = (res.group(1))
            conn.send(action + " " + outlets[options["--plug"]] + "\r\n")
            conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
        except pexpect.EOF:
            fail(EC_CONNECTION_LOST)
        except pexpect.TIMEOUT:
            fail(EC_TIMED_OUT)

def disconnect(conn):
    conn.sendline("LOGOUT")
    conn.close()

def get_version(conn, options):
    api_ver = "6"
    sub = "a"
    minor = ""
    conn.send("VERSION\r\n")
    conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
    lines = conn.before.split("\n")
    show_re = re.compile(r'Sentry Switched [PC]DU Version (\d)(.\d|)(\w)\r')
    for line in lines:
        res = show_re.search(line)
        if res != None:
            api_ver = res.group(1)
            if res.group(2):
                sub  = res.group(2).lstrip(".")
            minor = res.group(3)
    return (api_ver, sub, minor)

def main():
    device_opt = [ "ipaddr", "login", "port", "switch", "passwd", "telnet" ]

    atexit.register(atexit_handler)

    options = check_input(device_opt, process_input(device_opt))

    ##
    ## Fence agent specific defaults
    #####
    options["--command-prompt"] = "Switched [PC]DU: "

    docs = { }
    docs["shortdesc"] = "Fence agent for a Sentry Switch CDU over telnet"
    docs["longdesc"] = "fence_cdu is a Power Fencing agent \
which can be used with the Sentry Switch CDU. It logs into the device \
via telnet and power's on/off an outlet."
    docs["vendorurl"] = "http://www.servertech.com"
    show_docs(options, docs)

    ## Support for --plug [switch]:[plug] notation that was used before
    opt_n = options.get("--plug")
    if opt_n and (-1 != opt_n.find(":")):
        (switch, plug) = opt_n.split(":", 1)
        options["--switch"] = switch;
        options["--plug"] = plug;

    ##
    ## Operate the fencing device
    ####
    conn = fence_login(options)
    (api_ver, sub, minor) = get_version(conn, options)
    options["api-version"] = api_ver
    logging.debug("Using API version: %s" % api_ver)
    if api_ver == "7":
        # disable output paging
        conn.sendline("set option more disabled")
        conn.log_expect(options["--command-prompt"], int(options["--login-timeout"]))
    result = fence_action(conn, options, set_power_status, get_power_status, get_power_status)
    ##
    ## Logout from system
    ##
    ## In some special unspecified cases it is possible that
    ## connection will be closed before we run close(). This is not
    ## a problem because everything is checked before.
    ######
    atexit.register(disconnect, conn)

    sys.exit(result)

if __name__ == "__main__":
    main()
