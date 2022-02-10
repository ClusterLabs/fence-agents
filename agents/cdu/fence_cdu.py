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
##
##
#####

import sys, re, pexpect, atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_TIMED_OUT, run_command, frun, EC_STATUS

def get_power_status(conn, options):
    exp_result = 0
    outlets = {}
    try:
        conn.send("STATUS\r\n")
        conn.log_expect(options["--command-prompt"], int(options["--shell-timeout"]))
        lines = conn.before.split("\n")
        #    .A12     TowerA_Outlet12           On         Idle On  
        #    .A12     test-01                   On         Idle On  
        show_re = re.compile('(\.\w+)\s+(\w+|\w+\W\w+)\s+(On|Off)\s+(On|Idle On|Off|Wake On)')
        for line in lines:
            res = show_re.search(line)
            if res != None:
                outlets[res.group(2)] = (res.group(1), res.group(3))
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
            #    .A12     TowerA_Outlet12
            #    .A12     test-01
            show_re = re.compile('(\.\w+)\s+(\w+|\w+\W\w+)\s+')
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

def main():
    device_opt = [  "ipaddr", "login", "port", "switch", "passwd", "telnet" ]

    atexit.register(atexit_handler)

    options = check_input(device_opt, process_input(device_opt))

    ##
    ## Fence agent specific defaults
    #####
    options["--command-prompt"] = "Switched CDU:"

    docs = { }
    docs["shortdesc"] = "Fence agent for a Sentry Switch CDU over telnet"
    docs["longdesc"] = "fence_cdu is an I/O Fencing agent \
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
