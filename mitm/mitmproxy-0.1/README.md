MITM Proxy
==========
A collection of multi-protocol logging proxy servers and replay utilities.

Supported protocols:
  * Telnet
  * HTTP
  * SSL
  * SSH
  * SNMP

License
-------
Distributed under the GNU General Public License version 2 (GPLv2).

Dependencies
------------
* Python 2.7
* Twisted Python library (python-twisted)

Install
-------

```
python2 setup.py build
sudo python2 setup.py install
```

Or however you like to build&install python packages.


Alternatively, you can also use the source RPM listed under Releases on Github.


Motivation
----------
Created as a debugging tool for various enterprise fencing agents that tend
to break with each fencing device firmware upgrade, and then again (after
fixing for the new FW) for older firmware versions. :)


How-to
======
NOTE: assuming fencing-specific usage

First, generate the required keypairs with `mitmkeygen` (needed for SSL and SSH). These will get saved in `~/.mitmkeys`.

Telnet
------
To capture traffic between fencing agent and device, use `mitmproxy_telnet`:

```
mitmproxy_telnet [-H REMOTE_HOST] [-P REMOTE_PORT] [-p LOCAL_PORT] [-o OUTPUT_FILE]
```

eg.: to proxy requests to device.example.com:123 with proxy running on local port 1234 and outputting the captured traffic to capture.log:

```
mitmproxy_telnet -H device.example.com -P 123 -p 1234 -o capture.log
```

Once the proxy server starts listening the fencing agent can be launched, eg. for APC:

```
fence_apc -a localhost -u 1234 -l username -p password [...ACTION...]
```

After the fencing agent finished, you'll find the specified conversation log file (`capture.log` in this example), or STDOUT if you haven't specified any output file. STDOUT redirects work, too - any warnings/errors get logged to STDERR.

Now you can view the log in more human-friendly format with `mitmlogview`. You can even make it faster or slower with the `-d` option (see `--help` for details).

```
mitmlogview -f capture.log
```

If you're satisfied with the captured log file, then you can use it with replay server:

```
mitmreplay_telnet -f LOG_FILE [-p LOCAL_PORT] 
```

When the replay server starts listening, launch the fencing agent again, with the same parameters as before. "It should work." ;)

Other protocols
---------------
...are not much different. For extra options see the corresponding `--help` outputs.

Useful tools
------------
The `mitmlogdiff` provides a nice interface for comparing two proxy logs in case something goes awry (uses vimdiff, strips timestamps from the logs for easy comparison). Usage:

```
mitmlogdiff frist.log second.log
```

The extra proof-of-concept `fencegenlog` tool facilitates capturing logs and their hierarchical storage for multiple fencing devices (along with multiple protocols, firmware versions, etc). For usage info see the script's source (pretty much self-documenting). The same goes for `fencetestlog` which tests fencing agent against multiple known-good logs in order to see what is broken - essentially regression testing. These two tools could require some level of adaptation for more specific tasks. Example usage:

```
# provide args either on commandline or interactively

fencegenlog [PROTOCOL] [DEVICE_NAME] [FW_VERSION] [OPERATION] [PROXY_ARGS]

# eg. use mitmproxy_ssh (ssh protocol), save log as "apc" device with
# firmware version "1.2" for action "reboot" (those 3 parameters can be whatever),
# with not extra args for mitmproxy

fencegenlog ssh apc 1.2 reboot

# this results in creating ~/.mitmlogs/ssh/apc/1.2/reboot/1.log file,
# which can be used for regression testing later on
# repeat the above for each protocol/device/firmware/operation combination you want to test
# now run the log tester; again, params can ge supplied either on command-line or interactively

fencetestlog [PROTOCOL] [DEVICE_NAME] [FW_VERSION] [OPERATION] [FENCE_CMD] [REPLAY_ARGS]

# eg. to test all the apc over ssh logs for rebooting we created:

fencetestlog ssh apc '*' reboot 'fence_apc blahblahblah'

# this will run `mitmreplay_ssh` and then `fence_apc blahblahblah`
# (point it to replay server host/port, with correct login credentials,
# give it some action to perform, etc - essentially the same as in the above telnet how-to)
# with each log for each fw version of apc's reboot action over ssh and report
# the success/fail counts, along with list of failed test files
# !! remember to properly quote all the params or enter them interactively if not sure
```


Protocol-specific notes
=======================

Telnet
------
Nothing fancy.

HTTP
----
* Best to run it as (eg. if used for web pages or something with multiple connections)

  ```
  while true; do mitmproxy_http [options]; done
  ```

  * That's because the proxy terminates after each connection close, which might be OK for some limited amount of tools, but completely unusable with full-blown browsers and such

* Support for relative links, not absolute
  * When the real client sees absolute link, it creates a new, direct connection to the real server (can be overriden via /etc/hosts for local clients; DNS spoofing otherwise)
  * The above also fixes the `Host` HTTP header
  * However, make sure you're using IP address as an argument to -H option when going the /etc/hosts way! (infinite recursion FTW!)

* Must bind to port 80 (or whatever the real server is running at) to be compatible with redirects and absolute/relative links
  * Either run proxy as root (dirty and insecure) or use authbind / iptables / selinux

SSL
---
* Need to have server keys generated (mitmkeygen)
* HTTP notes also apply to SSL
* Connect with SSL:

```
openssl s_client -connect localhost:4443
```

SSH
---
* Supports pubkey and password auth (not eg. keyboard-interactive)
* Requires generated keys (mitmkeygen)
* Make sure server accepts the generated pubkey if using pubkey auth (eg. with `ssh-copy-id -i ~/.mitmkeys/id_rsa user@host`)
* SSH password is neither saved in the log, nor shown on the screen (unless overriden by commandline option).
* Client's SSH pubkey is ignored, proxy replaces it by its own.
* Password is forwarded without problems.
* SSH client will see MITM warning if it connected to the real server before (cached server host key fingerprint). If it's connecting for the first time, then... ;)
* You can have separate keypairs for client/server, just use the -a/-A and -b/-B options (mnemonic: Alice is the client, Bob the server; pubkey is not a big deal, privkey is ;))


Example Usage
-------------
* Fencing-specific usage
  * Launch the logging proxy server and fence agent.

    ```
    $ mitmproxy_telnet -H apc.example.com -o fencing_apc.log &
    $ fence_apc -a localhost -u 2323 -l login -p password -n 1
    ```

    APC plug #1 will be powered off and on again and we'll have the session log.
  
  * Replay the log at twice the speed.

    ```
    $ mitmreplay_telnet -f fencing_apc.log -d 0.5 &
    $ fence_apc -a localhost -u 2323 -l user -p password -n 1
    [...]
    ERROR: Expected 6d6f67696e0d000a (login...), got 757365720d000a (user...).
    FAIL! Premature end: not all messages sent.
    Client disconected.

    Unable to connect/login to fencing device
    ```

    Oops, wrong username. ;)

* Log viewer usage
  * The log viewer displays the whole session in real time or with an optional time dilation.
  
  ```
  $ mitmlogview -f fencing_apc.log -d 10
  ```

* Log diff usage
  * Shows the diff of two logs in vimdiff without comparing the timestamps.

  ```
  $ mitmlogdiff fencing_apc.log other_fencing_apc.log
  ```
