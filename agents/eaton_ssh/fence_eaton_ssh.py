#!@PYTHON@ -tt

"""
Plug numbering starts with 1! There were no tests performed so far with daisy chained PDUs.

Example usage:
    fence_eaton_ssh -v -a <IP> -l <USER> -p <PASSWORD> --login-timeout=60 --action status --plug 1
"""

#####
##
## The Following Agent Has Been Tested On:
##
##  Model       Firmware
## +---------------------------------------------+
##  EMAB04       04.02.0001
#####

import enum
import sys
import atexit

sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, EC_STATUS, EC_LOGIN_DENIED


class FenceEatonPowerActions(enum.Enum):
    """
    Status of the plug on the PDU.
    """
    ERROR = -1
    OFF = 0
    ON = 1
    PENDING_OFF = 2
    PENDING_ON = 3


def get_plug_names(conn, plug_ids, command_prompt, shell_timout):
    """
    Get the names of plugs via their ID.

    :param conn: The "fspawn" object.
    :param plug_ids: The list of plug IDs. Plugs start with the ID 1.
    :param command_prompt: The characters that make up the base prompt. This is important to detect a finished command.
    :param shell_timeout: The maximum time the shell should wait for a response.
    :returns: The name of the requested plugs.
    """
    # fspawn is subclassed from pexpect which is not correctly type annotated in all cases.
    result = {}
    full_node_mapping = {}
    conn.send_eol("get PDU.OutletSystem.Outlet[x].iName")
    conn.log_expect(command_prompt, shell_timout)
    result_plug_names = conn.before.split("\n")  # type: ignore
    if len(result_plug_names) != 3:
        fail(EC_STATUS)
    plug_names = result_plug_names.split("|")
    for counter in range(1, len(plug_names)):
        full_node_mapping[counter] = plug_names[counter]
    for plug_id in plug_ids:
        result[plug_id] = full_node_mapping[plug_id]
    return result


def get_plug_ids(conn, nodenames, command_prompt, shell_timout):
    """
    Get the IDs that map to the given nodenames. Non existing names are skipped.

    :param conn: The "fspawn" object.
    :param nodenames: The list of human readable names that should be converted to IDs.
    :param command_prompt: The characters that make up the base prompt. This is important to detect a finished command.
    :param shell_timeout: The maximum time the shell should wait for a response.
    :returns: A dictionary - possibly empty - where the keys are the node names and the values are the node IDs.
    """
    result = {}
    full_node_mapping = {}
    conn.send_eol("get PDU.OutletSystem.Outlet[x].iName")
    conn.log_expect(command_prompt, shell_timout)
    result_plug_names = conn.before.split("\n")  # type: ignore
    if len(result_plug_names) != 3:
        fail(EC_STATUS)
    plug_names = result_plug_names.split("|")
    for counter in range(1, len(plug_names)):
        full_node_mapping[plug_names[counter]] = counter
    for node in nodenames:
        if node in full_node_mapping:
            result[node] = full_node_mapping[node]
    return result


def get_plug_count(conn, command_prompt, shell_timout):
    """
    Get the number of plugs that the PDU has.
    
    In case the PDU is daisy chained this also contains the plugs of the other PDUs.

    :param conn: The "fspawn" object.
    :param command_prompt: The characters that make up the base prompt. This is important to detect a finished command.
    :param shell_timeout: The maximum time the shell should wait for a response.
    :returns: The number of plugs that the PDU has.
    """
    # fspawn is subclassed from pexpect which is not correctly type annotated in all cases.
    conn.send_eol("get PDU.OutletSystem.Outlet.Count")
    conn.log_expect(command_prompt, shell_timout)
    result_plug_count = conn.before.split("\n")  # type: ignore
    if len(result_plug_count) != 3:
        fail(EC_STATUS)
    return int(result_plug_count[1].strip())


def get_plug_status(conn, plug_id, command_prompt, shell_timout):
    """
    Get the current status of the plug. The return value of this doesn't account for operations that will act via
    schedules or a delay. As such the status is only valid at the time of retrieval.

    :param conn: The "fspawn" object.
    :param plug_id: The ID of the plug that should be powered off. Counting plugs starts at 1.
    :returns: The current status of the plug.
    """
    # fspawn is subclassed from pexpect which is not correctly type annotated in all cases.
    conn.send_eol(f"get PDU.OutletSystem.Outlet[{plug_id}].PresentStatus.SwitchOnOff")
    conn.log_expect(command_prompt, shell_timout)
    result_plug_status = conn.before.split("\n")  # type: ignore
    if len(result_plug_status) != 3:
        fail(EC_STATUS)
    if result_plug_status[1].strip() == "0":
        return FenceEatonPowerActions.OFF
    elif result_plug_status[1].strip() == "1":
        return FenceEatonPowerActions.ON
    else:
        return FenceEatonPowerActions.ERROR


def power_on_plug(conn, plug_id, command_prompt, shell_timout, delay=0):
    """
    Powers on a plug with an optional delay.

    :param conn: The "fspawn" object.
    :param plug_id: The ID of the plug that should be powered off. Counting plugs starts at 1.
    :param command_prompt: The characters that make up the base prompt. This is important to detect a finished command.
    :param shell_timeout: The maximum time the shell should wait for a response.
    :param delay: The delay in seconds. Passing "-1" aborts the power off action.
    """
    conn.send_eol(f"set PDU.OutletSystem.Outlet[{plug_id}].DelayBeforeStartup {delay}")
    conn.log_expect(command_prompt, shell_timout)


def power_off_plug(conn, plug_id, command_prompt, shell_timout, delay=0):
    """
    Powers off a plug with an optional delay.

    :param conn: The "fspawn" object.
    :param plug_id: The ID of the plug that should be powered off. Counting plugs starts at 1.
    :param command_prompt: The characters that make up the base prompt. This is important to detect a finished command.
    :param shell_timeout: The maximum time the shell should wait for a response.
    :param delay: The delay in seconds. Passing "-1" aborts the power off action.
    """
    conn.send_eol(f"set PDU.OutletSystem.Outlet[{plug_id}].DelayBeforeShutdown {delay}")
    conn.log_expect(command_prompt, shell_timout)


def get_power_status(conn, options):
    """
    Retrieve the power status for the requested plug. Since we have a serial like interface via SSH we need to parse the
    output of the SSH session manually.

    If abnormal behavior is detected the method will exit via "fail()".

    :param conn: The "fspawn" object.
    :param options: The option dictionary.
    :returns: In case there is an error this method does not return but instead calls "sys.exit". Otherwhise one of
    "off", "on" or "error" is returned.
    """
    if conn is None:
        fail(EC_LOGIN_DENIED)

    requested_plug = options.get("--plug", "")
    if not requested_plug:
        fail(EC_STATUS)
    plug_status = get_plug_status(
        conn,  # type: ignore
        int(requested_plug),
        options["--command-prompt"],
        int(options["--shell-timeout"])
    )
    if plug_status == FenceEatonPowerActions.OFF:
        return "off"
    elif plug_status == FenceEatonPowerActions.ON:
        return "on"
    else:
        return "error"


def set_power_status(conn, options):
    """
    Set the power status for the requested plug. Only resposible for powering on and off.

    If abnormal behavior is detected the method will exit via "fail()".

    :param conn: The "fspawn" object.
    :param options: The option dictionary.
    :returns: In case there is an error this method does not return but instead calls "sys.exit".
    """
    if conn is None:
        fail(EC_LOGIN_DENIED)

    requested_plug = options.get("--plug", "")
    if not requested_plug:
        fail(EC_STATUS)
    requested_action = options.get("--action", "")
    if not requested_action:
        fail(EC_STATUS)

    if requested_action == "off":
        power_off_plug(
            conn,  # type: ignore
            int(requested_plug),
            options["--command-prompt"],
            int(options["--shell-timeout"])
        )
    elif requested_action == "on":
        power_on_plug(
            conn,  # type: ignore
            int(requested_plug),
            options["--command-prompt"],
            int(options["--shell-timeout"])
        )
    else:
        fail(EC_STATUS)


def get_outlet_list(conn, options):
    """
    Retrieves the list of plugs with their correspondin status.

    :param conn: The "fspawn" object.
    :param options: The option dictionary.
    :returns: Keys are the Plug IDs which each have a Tuple with the alias for the plug and its status.
    """
    if conn is None:
        fail(EC_LOGIN_DENIED)

    result = {}
    plug_count = get_plug_count(conn, options["--command-prompt"], int(options["--shell-timeout"]))  # type: ignore
    for counter in range(1, plug_count):
        plug_names = get_plug_names(
            conn,  # type: ignore
            [counter],
            options["--command-prompt"],
            int(options["--shell-timeout"])
        )
        plug_status_enum = get_plug_status(
            conn,  # type: ignore
            counter,
            options["--command-prompt"],
            int(options["--shell-timeout"])
        )
        if plug_status_enum == FenceEatonPowerActions.OFF:
            plug_status = "OFF"
        elif plug_status_enum == FenceEatonPowerActions.ON:
            plug_status = "ON"
        else:
            plug_status = None
        result[str(counter)] = (plug_names[counter], plug_status)
    return result


def reboot_cycle(conn, options) -> None:
    """
    Responsible for power cycling a machine. Not responsible for singular on and off actions.

    :param conn: The "fspawn" object.
    :param options: The option dictionary.
    """
    requested_plug = options.get("--plug", "")
    if not requested_plug:
        fail(EC_STATUS)

    power_off_plug(
        conn,  # type: ignore
        int(requested_plug),
        options["--command-prompt"],
        int(options["--shell-timeout"])
    )
    power_on_plug(
        conn,  # type: ignore
        int(requested_plug),
        options["--command-prompt"],
        int(options["--shell-timeout"])
    )


def main():
    """
    Main entrypoint for the fence_agent.
    """
    device_opt = ["secure", "ipaddr", "login", "passwd", "port", "cmd_prompt"]
    atexit.register(atexit_handler)
    options = check_input(device_opt, process_input(device_opt))
    options["--ssh"] = None
    options["--ipport"] = 22
    options["--command-prompt"] = "pdu#0>"

    docs = {}
    docs["shortdesc"] = "Fence agent for Eaton ePDU G3 over SSH"
    docs["longdesc"] = "fence_eaton_ssh is a Power Fencing agent that connects to Eaton ePDU devices. It logs into \
device via ssh and reboot a specified outlet."
    docs["vendorurl"] = "https://www.eaton.com/"
    show_docs(options, docs)

    conn = fence_login(options)
    result = fence_action(conn, options, set_power_status, get_power_status, get_outlet_list, reboot_cycle)
    fence_logout(conn, "quit")
    sys.exit(result)


if __name__ == "__main__":
    main()
