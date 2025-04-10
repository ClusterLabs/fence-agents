#!@PYTHON@ -tt

import sys, stat
import logging
import os
import atexit
import re
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import fail_usage, run_commands, fence_action, all_opt
from fencing import atexit_handler, check_input, process_input, show_docs
from fencing import run_delay
import itertools

DEVICE_INIT = 1
DEVICE_NOT_INIT = -3
PATH_NOT_EXISTS = -1
PATH_NOT_BLOCK = -2
SBD_PID_FILE = "@SBDPID_PATH@"

def is_block_device(filename):
    """Checks if a given path is a valid block device

    Key arguments:
    filename -- the file to check

    Return codes:
    True if it's a valid block device
    False, otherwise
    """

    try:
        mode = os.lstat(filename).st_mode
    except OSError:
        return False
    else:
        return stat.S_ISBLK(mode)

def is_link(filename):
    """Checks if a given path is a link.

    Key arguments:
    filename -- the file to check

    Return codes:
    True if it's a link
    False, otherwise
    """

    try:
        mode = os.lstat(filename).st_mode
    except OSError:
        return False
    else:
        return stat.S_ISLNK(mode)

def check_sbd_device(options, device_path):
    """checks that a given sbd device exists and is initialized

    Key arguments:
    options -- options dictionary
    device_path -- device path to check

    Return Codes:
    1 / DEVICE_INIT if the device exists and is initialized
    -1 / PATH_NOT_EXISTS if the path does not exists
    -2 / PATH_NOT_BLOCK if the path exists but is not a valid block device
    -3 / DEVICE_NOT_INIT if the sbd device is not initialized
    """

    # First of all we need to check if the device is valid
    if not os.path.exists(device_path):
        return PATH_NOT_EXISTS

    # We need to check if device path is a symbolic link. If so we resolve that
    # link.
    if is_link(device_path):
        link_target = os.readlink(device_path)
        device_path = os.path.join(os.path.dirname(device_path), link_target)

    # As second step we make sure it's a valid block device
    if not is_block_device(device_path):
        return PATH_NOT_BLOCK

    cmd = "%s -d %s dump" % (options["--sbd-path"], device_path)

    (return_code, out, err) = run_commands(options, [ cmd ])

    for line in itertools.chain(out.split("\n"), err.split("\n")):
        if len(line) == 0:
            continue

        # If we read "NOT dumped" something went wrong, e.g. the device is not
        # initialized.
        if "NOT dumped" in line:
            return DEVICE_NOT_INIT

    return DEVICE_INIT


def generate_sbd_command(options, command, arguments=None):
    """Generates a sbd command based on given arguments.

    Return Value:
    generated list of sbd commands (strings) depending
    on command multiple commands with a device each
    or a single command with multiple devices
    """
    cmds = []

    if not command in ["list", "dump"]:
        cmd = options["--sbd-path"]

        # add "-d" for each sbd device
        for device in parse_sbd_devices(options):
            cmd += " -d %s" % device

        cmd += " %s %s" % (command, arguments)
        cmds.append(cmd)

    else:
        for device in parse_sbd_devices(options):
            cmd = options["--sbd-path"]
            cmd += " -d %s" % device
            cmd += " %s %s" % (command, arguments)
            cmds.append(cmd)

    return cmds

def send_sbd_message(conn, options, plug, message):
    """Sends a message to all sbd devices.

    Key arguments:
    conn -- connection structure
    options -- options dictionary
    plug -- plug to sent the message to
    message -- message to send

    Return Value:
    (return_code, out, err) Tuple containing the error code,
    """

    del conn

    arguments = "%s %s" % (plug, message)
    cmd = generate_sbd_command(options, "message", arguments)

    (return_code, out, err) = run_commands(options, cmd)

    return (return_code, out, err)

def get_sbd_header_timeout(options):
    """Reads the configured sbd message timeout from each device.

    Key arguments:
    options -- options dictionary

    Return Value:
    (msg_timeout, watchdog_timeout)
    """

    # get the defined msg_timeout
    msg_timeout = -1 # default sbd msg timeout
    watchdog_timeout = -1 # default sbd watchdog timeout

    cmd = generate_sbd_command(options, "dump")

    (return_code, out, err) = run_commands(options, cmd)

    for line in itertools.chain(out.split("\n"), err.split("\n")):
        if len(line) == 0:
            continue

        if "msgwait" in line:
            tmp_msg_timeout = int(line.split(':')[1])
            if -1 != msg_timeout and tmp_msg_timeout != msg_timeout:
                logging.warning(\
                        "sbd message timeouts differ in different devices")
            # we only save the highest timeout
            msg_timeout = max(msg_timeout, tmp_msg_timeout)
        elif "watchdog" in line:
            tmp_watchdog_timeout = int(line.split(':')[1])
            if -1 != watchdog_timeout and tmp_watchdog_timeout != watchdog_timeout:
                logging.warning(\
                        "sbd watchdog timeouts differ in different devices")
            # we only save the highest timeout
            watchdog_timeout = max(watchdog_timeout, tmp_watchdog_timeout)

    return msg_timeout, watchdog_timeout

def get_crashdump_timeout():
    crashdump_timeout = -1
    sbd_opts = os.getenv("SBD_OPTS", None)
    if sbd_opts:
        # parse '-C N'
        match = re.search(r'-C\s+(\d+)', sbd_opts)
        if match:
            crashdump_timeout = int(match.group(1))
    return crashdump_timeout

def set_power_status(conn, options):
    """send status to sbd device (poison pill)

    Key arguments:
    conn -- connection structure
    options -- options dictionary

    Return Value:
    return_code -- action result (bool)
    """

    target_status = options["--action"]
    plug = options["--plug"]
    enable_crashdump = "--crashdump" in options
    return_code = 99
    out = ""
    err = ""

    # Map fencing actions to sbd messages
    if "on" == target_status:
        (return_code, out, err) = send_sbd_message(conn, options, plug, "clear")
    elif "off" == target_status:
        msg = "crashdump" if enable_crashdump else "off"
        (return_code, out, err) = send_sbd_message(conn, options, plug, msg)
    elif "reboot" == target_status:
        msg = "crashdump" if enable_crashdump else "reset"
        (return_code, out, err) = send_sbd_message(conn, options, plug, msg)

    if 0 != return_code:
        logging.error("sending message to sbd device(s) \
                failed with return code %d", return_code)
        logging.error("DETAIL: output on stdout was \"%s\"", out)
        logging.error("DETAIL: output on stderr was \"%s\"", err)

    return not bool(return_code)

def reboot_cycle(conn, options):
    """" trigger reboot by sbd messages

    Key arguments:
    conn -- connection structure
    options -- options dictionary

    Return Value:
    return_code -- action result (bool)
    """

    plug = options["--plug"]
    return_code = 99
    enable_crashdump = "--crashdump" in options
    out = ""
    err = ""

    msg = "crashdump" if enable_crashdump else "reset"
    (return_code, out, err) = send_sbd_message(conn, options, plug, msg)
    return not bool(return_code)

def get_power_status(conn, options):
    """Returns the status of a specific node.

    Key arguments:
    conn -- connection structure
    options -- option dictionary

    Return Value:
    status -- status code (string)
    """

    status = "UNKWNOWN"
    plug = options["--plug"]

    nodelist = get_node_list(conn, options)

    # We need to check if the specified plug / node a already a allocated slot
    # on the device.
    if plug not in nodelist:
        logging.error("node \"%s\" not found in node list", plug)
    else:
        status = nodelist[plug][1]


    return status

def translate_status(sbd_status):
    """Translates the sbd status to fencing status.

    Key arguments:
    sbd_status -- status to translate (string)

    Return Value:
    status -- fencing status (string)
    """

    status = "UNKNOWN"


    # Currently we only accept "clear" to be marked as online. Eventually we
    # should also check against "test"
    online_status = ["clear"]

    offline_status = ["reset", "off"]

    if any(online_status_element in sbd_status \
            for online_status_element in online_status):
        status = "on"

    if any(offline_status_element in sbd_status \
            for offline_status_element in offline_status):
        status = "off"

    return status

def get_node_list(conn, options):
    """Returns a list of hostnames, registerd on the sbd device.

    Key arguments:
    conn -- connection options
    options -- options

    Return Value:
    nodelist -- dictionary wich contains all node names and there status
    """

    del conn

    nodelist = {}

    cmd = generate_sbd_command(options, "list")

    (return_code, out, err) = run_commands(options, cmd)

    for line in out.split("\n"):
        if len(line) == 0:
            continue

        # if we read "unreadable" something went wrong
        if "NOT dumped" in line:
            return nodelist

        words = line.split()
        port = words[1]
        sbd_status = words[2]
        nodelist[port] = (port, translate_status(sbd_status))

    return nodelist

def parse_sbd_devices(options):
    """Returns an array of all sbd devices.

    Key arguments:
    options -- options dictionary

    Return Value:
    devices -- array of device paths
    """

    devices = [str.strip(dev) \
            for dev in str.split(options["--devices"], ",")]

    return devices

def define_new_opts():
    """Defines the all opt list
    """
    all_opt["devices"] = {
        "getopt" : ":",
        "longopt" : "devices",
        "help":"--devices=[device_a,device_b] \
Comma separated list of sbd devices",
        "required" : "0",
        "shortdesc" : "SBD Device",
        "order": 1
        }

    all_opt["sbd_path"] = {
        "getopt" : ":",
        "longopt" : "sbd-path",
        "help" : "--sbd-path=[path]              Path to SBD binary",
        "required" : "0",
        "default" : "@SBD_PATH@",
        "order": 200
        }

    all_opt["crashdump"] = {
        "getopt" : "",
        "longopt" : "crashdump",
        "help" : "--crashdump                    Enable crashdump, default is disabled",
        "required" : "0",
        "shortdesc" : "Crashdump instead of regular fence",
        "longdesc" : "If SBD is given a fence command, this option will perform a \
kernel crash instead of a reboot or power-off, which on a properly configured \
system can lead to a crashdump for analysis. \
\nWARNING:\n \
This is unsafe for production environments. Please use with caution \
and for debugging purposes only.",
        "order": 201
        }


def sbd_daemon_is_running():
    """Check if the sbd daemon is running
    """
    if not os.path.exists(SBD_PID_FILE):
        logging.info("SBD PID file %s does not exist", SBD_PID_FILE)
        return False

    try:
        with open(SBD_PID_FILE, "r") as pid_file:
            pid = int(pid_file.read().strip())
    except Exception as e:
        logging.error("Failed to read PID file %s: %s", SBD_PID_FILE, e)
        return False

    try:
        # send signal 0 to check if the process is running
        os.kill(pid, 0)
    except ProcessLookupError:
        logging.info("SBD daemon is not running")
        return False
    except Exception as e:
        logging.error("Failed to send signal 0 to PID %d: %s", pid, e)
        return False

    return True

def main():
    """Main function
    """
    # We need to define "no_password" otherwise we will be ask about it if
    # we don't provide any password.
    device_opt = ["no_password", "devices", "port", "method", "sbd_path", "crashdump"]

    # close stdout if we get interrupted
    atexit.register(atexit_handler)

    define_new_opts()

    all_opt["method"]["default"] = "cycle"
    all_opt["method"]["help"] = "-m, --method=[method]          Method to fence (onoff|cycle) (Default: cycle)"
    all_opt["power_timeout"]["default"] = "30"

    options = check_input(device_opt, process_input(device_opt))

    # fill the needed variables to generate metadata and help text output
    docs = {}
    docs["shortdesc"] = "Fence agent for sbd"
    docs["longdesc"] = "fence_sbd is an I/O Fencing agent \
which can be used in environments where sbd can be used (shared storage)."
    docs["vendorurl"] = ""
    show_docs(options, docs)

    # If not specified then read SBD_DEVICE from environment
    if "--devices" not in options:
        dev_list = os.getenv("SBD_DEVICE")
        if dev_list and sbd_daemon_is_running():
            options["--devices"] = ",".join(dev_list.split(";"))
        else:
            fail_usage("No SBD devices specified. \
                    At least one SBD device is required.")

    run_delay(options)

    # We need to check if the provided sbd_devices exists. We need to do
    # that for every given device.
    # Just for the case we are really rebooting / powering off a device
    # (pacemaker as well uses the list command to generate a dynamic list)
    # we leave it to sbd to try and decide if it was successful
    if not options["--action"] in ["reboot", "off", "list"]:
        for device_path in parse_sbd_devices(options):
            logging.debug("check device \"%s\"", device_path)

            return_code = check_sbd_device(options, device_path)
            if PATH_NOT_EXISTS == return_code:
                logging.error("\"%s\" does not exist", device_path)
            elif PATH_NOT_BLOCK == return_code:
                logging.error("\"%s\" is not a valid block device", device_path)
            elif DEVICE_NOT_INIT == return_code:
                logging.error("\"%s\" is not initialized", device_path)
            elif DEVICE_INIT != return_code:
                logging.error("UNKNOWN error while checking \"%s\"", device_path)

            # If we get any error while checking the device we need to exit at this
            # point.
            if DEVICE_INIT != return_code:
                exit(return_code)

    # we check against the defined timeouts. If the pacemaker timeout is smaller
    # then that defined within sbd we should report this.
    power_timeout = int(options["--power-timeout"])
    sbd_msg_timeout, sbd_watchdog_timeout = get_sbd_header_timeout(options)
    if 0 < power_timeout <= sbd_msg_timeout:
        logging.warning("power timeout needs to be \
                greater then sbd message timeout")

    action = options.get("--action", None)
    if "--crashdump" in options and action in ("reboot", "off"):
        target_node = options.get("--plug", "UNKNOWN")
        crashdump_timeout = get_crashdump_timeout()
        logging.warning("crashdump option is enabled while doing action %s on node %s", action, target_node)
        logging.warning(
                "sbd watchdog timeout: %d, crashdump timeout(compare to setting on target-node %s): %d",
                sbd_watchdog_timeout, target_node, crashdump_timeout
        )

    result = fence_action(\
                None, \
                options, \
                set_power_status, \
                get_power_status, \
                get_node_list, \
                reboot_cycle)

    sys.exit(result)

if __name__ == "__main__":
    main()
