<p>This page describes how to implement a fencing agent, and how agents are
called from the cluster software.</p>
<p>Fencing, generally, is a way to prevent an ill-behaved cluster member
from accessing shared data in a way which would cause data or file
system corruption. The canonical case where fencing is required is
something like this: Node1 live-hangs with a lock on a GFS file system.
Node2 thinks node1 is dead, takes a lock, and begins accessing the same
data. Node1 wakes up and continues what it was doing. Because we can not
predict when node1 would wake up or prevent it from issuing I/Os
immediately after waking up, we need a way to prevent its I/Os from
completing even if it does wake up.</p>
<h2>Definitions</h2>
<ul>
<li><strong>I/O Fencing</strong> is, in short, the act of preventing a node from
    issuing I/Os (usually to shared storage). It is also known as
    <strong>STOMITH</strong> or <strong>STONITH</strong>.</li>
<li><strong>Fencing devices</strong> are hardware components used to prevent a node
    from issuing I/Os.</li>
<li><strong>Fencing agents</strong> are software components used to communicate with
    <strong>fencing devices</strong> in order to perform <strong>I/O Fencing</strong>. In the
    context of this project, they are standalone applications which are
    spawned by the cluster software (compared to, for example, Linux-HA
    which uses dynamically-loaded modules).</li>
<li><strong>Power fencing</strong> is when a node is power-cycled, reset, or turned
    off to prevent it from issuing I/Os</li>
<li><strong>Fabric fencing</strong> is when a node's access to the shared data is cut
    off at the device-level. Disabling a port on a fibre channel switch
    (zoning), revoking a SCSI3 group reservation, or disabling access at
    the SAN itself from a given initiator's GUID are all examples of
    <strong>fabric fencing</strong>.</li>
<li><strong>Manual fencing</strong> or <strong>meatware</strong> is when an administrator must
    manually power-cycle a machine (or unplug its storage cables) and
    follow up with the cluster, notifying the cluster that the machine
    has been fenced. This is never recommended.</li>
</ul>
<h2>What is given to fencing agents by fenced &amp; stonithd</h2>
<p>When the cluster decides a node must be fenced, a node is chosen to
perform the task. The fence daemon ("fenced") is responsible for
performing the request, and it spawns agents listed for a given node as
noted in cluster.conf. When called by other pieces of software (fenced,
fence_node), fencing agents take arguments from standard input (as
opposed to the command line) in the following format:</p>
<div class="codehilite"><pre>argument=value
#this line is ignored
argument2=value2
</pre></div>


<ul>
<li>Lines beginning with a <strong>#</strong> should be ignored</li>
<li>One line per argument</li>
<li>Argument and value are separated by an equals sign</li>
<li>If argument is specified several times only last value is used</li>
</ul>
<p>The following things are <em>not allowed</em> in this input:</p>
<ul>
<li>Spaces in the argument (or anything else which isn't allowed by XML
    standards for an attribute name)</li>
<li>Spaces between the argument and the equals sign (=)</li>
<li>Newlines in the value (or anything else which isn't allowed by XML
    standards for an attribute value)</li>
</ul>
<p>The following are guidelines for parsing the arguments:</p>
<ul>
<li>Quotation marks around the value is not necessary, and are not
    provided by the fencing system. Simply parse from the equals sign to
    the newline.</li>
<li>Equals signs are allowed in the argument, but it is not recommended.</li>
<li>Arguments which are not recognized <em>should be ignored</em> by the
    fencing agent.</li>
</ul>
<h3>Example cluster.conf</h3>
<div class="codehilite"><pre>&lt;clusternodes&gt;
    &lt;clusternode name="red.lab.boston.redhat.com" nodeid="1" votes="1"&gt;
        &lt;fence&gt;
            &lt;method name="1"&gt;
                &lt;device name="ips-rack9" port="1" action="reboot"/&gt;
            &lt;/method&gt;
        &lt;/fence&gt;
    &lt;/clusternode&gt;
    ...
&lt;/clusternodes&gt;
&lt;fencedevices&gt;
    &lt;fencedevice agent="fence_wti" name="ips-rack9" passwd="wti" ipaddr="ips-rack9"/&gt;
&lt;/fencedevices&gt;
</pre></div>


<h3>Example input given to a fence_agent</h3>
<p>Given the previous cluster.conf example, the following is sent to the
agent named <strong>fence_wti</strong> when the cluster decides to fence
red.lab.boston.redhat.com:</p>
<div class="codehilite"><pre>agent=fence_wti
name=ips-rack9
passwd=wti
ipaddr=ips-rack9
port=1
action=reboot
nodename=red.lab.boston.redhat.com
</pre></div>


<p>Note that fenced always passes the name of the node to be fenced via the
nodename argument.</p>
<h2>Agent Operations and Return Values</h2>
<ul>
<li><em>off</em> - fence / turn off / etc. <strong>This operation is required.</strong>
    Return values:<ul>
<li>0 if the operation was successful, or</li>
<li>1 if not successful or verification could not be performed. This
    includes inability to contact the fence device at any point.</li>
</ul>
</li>
<li><em>on</em> - un-fence / turn on / etc. Return values:<ul>
<li>0 if the operation was successful, or</li>
<li>1 if not successful or verification could not be performed. This
    includes inability to contact the fence device at any point.</li>
</ul>
</li>
<li><em>reboot</em> - this is normally an <em>off</em> followed by an <em>on</em>, but
    not always. It is important to note that in some cases, this
    operation is not verifiable. For example, if you use an integrated
    power management feature like iLO or IPMI to reset the node, there
    is no point at which the node has lost power. Return values:<ul>
<li>0 if the <em>off</em> portion was successful (the <em>on</em> portion failing
    is a don't-care case for the cluster, as it can recover safely)</li>
<li>1 if the <em>off</em> portion was unsuccessful (see above for reasons).</li>
</ul>
</li>
<li><em>status</em> - this is used by pacemaker to verify that the agent
    is working. It is not required by 'fenced'. Use is encouraged.
    Return values:<ul>
<li>0 if the fence device is reachable and the port is in the <em>on</em>
    state</li>
<li>1 if the fence device could not be contacted</li>
<li>2 if the fence device is reachable but is in the <em>off</em> state</li>
</ul>
</li>
<li><em>monitor</em> - Attempt to contact the fencing device. Typically,
    'status' for one-port hardware, and 'list' for multi-port hardware.
    Return values:<ul>
<li>0 if the fence device is reachable and working properly</li>
<li>1 if the fence device could not be contacted</li>
<li>2 if the fence device is reachable but is in the <em>off</em> state
    (single-port hardware only)</li>
</ul>
</li>
<li><em>list</em> - Multi-port fencing devices only. Prints a list of port
    names and assignments Return values:<ul>
<li>0 if the fence device is reachable and working properly</li>
<li>1 if the fence device could not be contacted</li>
</ul>
</li>
</ul>
<h2>Attribute Specifications</h2>
<p>These attributes <em>should</em> be used when implementing new agents, but this
is not an exhaustive list. Some agents may have other arguments which
are not covered here.</p>
<ul>
<li><strong>action</strong> - the operation (noted previously) to perform. This is
    one of the following (case insensitive): on, off, reboot, monitor,
    list, or status</li>
<li><strong>option</strong> - (DEPRECATED; use action) - same as <strong>action</strong></li>
<li><strong>ipaddr</strong> - for a hostname or IP address</li>
<li><strong>login</strong> - for a username or login name</li>
<li><strong>passwd</strong> - for a password</li>
<li><strong>passwd_script</strong> - if your agent supports storing passwords
    outside of cluster.conf, this is a script used to retrieve your
    password (details on how this works will be added later). Generally,
    this script simply echoes the password to standard output (and is
    read in by the agent at run-time).</li>
<li><strong>port</strong> - if you have to specify a plug or port (for example, on a
    network-enabled PDU with 8 ports)</li>
<li><strong>nodename</strong> - if the agent fences by node name, this is the
    parameter to use (e.g. instead of port). In the event that both
    <em>nodename</em> and <em>port</em> are specified, the preference is given to
    <em>port</em>.</li>
</ul>
<h2>Implementation Best-Practices</h2>
<p>Currently, this project has a number of requirements which should be
common to all agents (even if not currently):</p>
<ul>
<li><strong>Verifiable operation</strong> - When a node has been fenced by a
    particular device, the agent <em>should</em> query the device to ensure the
    new state has taken effect. For example, if you turn the a power
    plug "off", the agent should, after doing this, query the device and
    verify that the plug is in the "off" state. This is not necessary
    for the "on" case or when you "un-fence" a node.</li>
<li><strong>Timeout is a failure, not success</strong> - A timeout is an assumption,
    and we want a guarantee, which is why we generally verify operations
    from within the agents after performing them.</li>
<li><strong>Fabric fencing must never have a reboot operation</strong> - Don't waste
    time implementing one.</li>
<li><strong>There should be a command line mode, too</strong> - for debugging, your
    agent should be able to operate using arguments passed in via the
    command line as well. How the mapping is done between the command
    line arguments and stdin arguments is implementation dependent,
    i.e., it's up to you ;)</li>
<li><strong>Whitespace in stdin</strong> - existing agents tend to strip leading
    whitespace (before the argument) when processing arguments from
    standard input, but this is not a requirement. Whether whitespace is
    stripped between the equals sign and newline in the value is
    implementation dependent.</li>
<li>Output of <strong>fence_agent -o metadata</strong> should validate against
    RelaxNG schema available at <a href="https://raw.githubusercontent.com/ClusterLabs/fence-agents/master/lib/metadata.rng">lib/metadata.rng</a></li>
</ul>
