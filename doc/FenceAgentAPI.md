This page describes how to implement a fencing agent, and how agents are
called from the cluster software.

Fencing, generally, is a way to prevent an ill-behaved cluster member
from accessing shared data in a way which would cause data or file
system corruption. The canonical case where fencing is required is
something like this: Node1 live-hangs with a lock on a GFS file system.
Node2 thinks node1 is dead, takes a lock, and begins accessing the same
data. Node1 wakes up and continues what it was doing. Because we can not
predict when node1 would wake up or prevent it from issuing I/Os
immediately after waking up, we need a way to prevent its I/Os from
completing even if it does wake up.

## Definitions

-   **I/O Fencing** is, in short, the act of preventing a node from
    issuing I/Os (usually to shared storage). It is also known as
    **STOMITH** or **STONITH**.
-   **Fencing devices** are hardware components used to prevent a node
    from issuing I/Os.
-   **Fencing agents** are software components used to communicate with
    **fencing devices** in order to perform **I/O Fencing**. In the
    context of this project, they are standalone applications which are
    spawned by the cluster software (compared to, for example, Linux-HA
    which uses dynamically-loaded modules).
-   **Power fencing** is when a node is power-cycled, reset, or turned
    off to prevent it from issuing I/Os
-   **Fabric fencing** is when a node's access to the shared data is cut
    off at the device-level. Disabling a port on a fibre channel switch
    (zoning), revoking a SCSI3 group reservation, or disabling access at
    the SAN itself from a given initiator's GUID are all examples of
    **fabric fencing**.
-   **Manual fencing** or **meatware** is when an administrator must
    manually power-cycle a machine (or unplug its storage cables) and
    follow up with the cluster, notifying the cluster that the machine
    has been fenced. This is never recommended.

## What is given to fencing agents by fenced & stonithd

When the cluster decides a node must be fenced, a node is chosen to
perform the task. The fence daemon ("fenced") is responsible for
performing the request, and it spawns agents listed for a given node as
noted in cluster.conf. When called by other pieces of software (fenced,
fence\_node), fencing agents take arguments from standard input (as
opposed to the command line) in the following format:

    argument=value
    #this line is ignored
    argument2=value2

-   Lines beginning with a **\#** should be ignored
-   One line per argument
-   Argument and value are separated by an equals sign
-   If argument is specified several times only last value is used

The following things are *not allowed* in this input:

-   Spaces in the argument (or anything else which isn't allowed by XML
    standards for an attribute name)
-   Spaces between the argument and the equals sign (=)
-   Newlines in the value (or anything else which isn't allowed by XML
    standards for an attribute value)

The following are guidelines for parsing the arguments:

-   Quotation marks around the value is not necessary, and are not
    provided by the fencing system. Simply parse from the equals sign to
    the newline.
-   Equals signs are allowed in the argument, but it is not recommended.
-   Arguments which are not recognized *should be ignored* by the
    fencing agent.

### Example cluster.conf

    <clusternodes>
        <clusternode name="red.lab.boston.redhat.com" nodeid="1" votes="1">
            <fence>
                <method name="1">
                    <device name="ips-rack9" port="1" action="reboot"/>
                </method>
            </fence>
        </clusternode>
        ...
    </clusternodes>
    <fencedevices>
        <fencedevice agent="fence_wti" name="ips-rack9" passwd="wti" ipaddr="ips-rack9"/>
    </fencedevices>

### Example input given to a fence\_agent

Given the previous cluster.conf example, the following is sent to the
agent named **fence\_wti** when the cluster decides to fence
red.lab.boston.redhat.com:

    agent=fence_wti
    name=ips-rack9
    passwd=wti
    ipaddr=ips-rack9
    port=1
    action=reboot
    nodename=red.lab.boston.redhat.com

Note that fenced always passes the name of the node to be fenced via the
nodename argument.

## Agent Operations and Return Values

-   *off* - fence / turn off / etc. **This operation is required.**
    Return values:
    -   0 if the operation was successful, or
    -   1 if not successful or verification could not be performed. This
        includes inability to contact the fence device at any point.
-   *on* - un-fence / turn on / etc. Return values:
    -   0 if the operation was successful, or
    -   1 if not successful or verification could not be performed. This
        includes inability to contact the fence device at any point.
-   *reboot* - this is normally an *off* followed by an *on*, but
    not always. It is important to note that in some cases, this
    operation is not verifiable. For example, if you use an integrated
    power management feature like iLO or IPMI to reset the node, there
    is no point at which the node has lost power. Return values:
    -   0 if the *off* portion was successful (the *on* portion failing
        is a don't-care case for the cluster, as it can recover safely)
    -   1 if the *off* portion was unsuccessful (see above for reasons).
-   *status* - this is used by pacemaker to verify that the agent
    is working. It is not required by 'fenced'. Use is encouraged.
    Return values:
    -   0 if the fence device is reachable and the port is in the *on*
        state
    -   1 if the fence device could not be contacted
    -   2 if the fence device is reachable but is in the *off* state
-   *monitor* - Attempt to contact the fencing device. Typically,
    'status' for one-port hardware, and 'list' for multi-port hardware.
    Return values:
    -   0 if the fence device is reachable and working properly
    -   1 if the fence device could not be contacted
    -   2 if the fence device is reachable but is in the *off* state
        (single-port hardware only)
-   *list* - Multi-port fencing devices only. Prints a list of port
    names and assignments Return values:
    -   0 if the fence device is reachable and working properly
    -   1 if the fence device could not be contacted

## Attribute Specifications

These attributes *should* be used when implementing new agents, but this
is not an exhaustive list. Some agents may have other arguments which
are not covered here.

-   **action** - the operation (noted previously) to perform. This is
    one of the following (case insensitive): on, off, reboot, monitor,
    list, or status
-   **option** - (DEPRECATED; use action) - same as **action**
-   **ipaddr** - for a hostname or IP address
-   **login** - for a username or login name
-   **passwd** - for a password
-   **passwd\_script** - if your agent supports storing passwords
    outside of cluster.conf, this is a script used to retrieve your
    password (details on how this works will be added later). Generally,
    this script simply echoes the password to standard output (and is
    read in by the agent at run-time).
-   **port** - if you have to specify a plug or port (for example, on a
    network-enabled PDU with 8 ports)
-   **nodename** - if the agent fences by node name, this is the
    parameter to use (e.g. instead of port). In the event that both
    *nodename* and *port* are specified, the preference is given to
    *port*.

## Implementation Best-Practices

Currently, this project has a number of requirements which should be
common to all agents (even if not currently):

-   **Verifiable operation** - When a node has been fenced by a
    particular device, the agent *should* query the device to ensure the
    new state has taken effect. For example, if you turn the a power
    plug "off", the agent should, after doing this, query the device and
    verify that the plug is in the "off" state. This is not necessary
    for the "on" case or when you "un-fence" a node.
-   **Timeout is a failure, not success** - A timeout is an assumption,
    and we want a guarantee, which is why we generally verify operations
    from within the agents after performing them.
-   **Fabric fencing must never have a reboot operation** - Don't waste
    time implementing one.
-   **There should be a command line mode, too** - for debugging, your
    agent should be able to operate using arguments passed in via the
    command line as well. How the mapping is done between the command
    line arguments and stdin arguments is implementation dependent,
    i.e., it's up to you ;)
-   **Whitespace in stdin** - existing agents tend to strip leading
    whitespace (before the argument) when processing arguments from
    standard input, but this is not a requirement. Whether whitespace is
    stripped between the equals sign and newline in the value is
    implementation dependent.
-   Output of **fence\_agent -o metadata** should validate against
    RelaxNG schema available at [lib/metadata.rng](https://raw.githubusercontent.com/ClusterLabs/fence-agents/master/lib/metadata.rng)
