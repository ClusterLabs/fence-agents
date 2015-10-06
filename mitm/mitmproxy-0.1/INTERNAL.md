MITMPROXY LIBRARY INTERNALS
===========================


Introduction
------------
The `mitmproxy` library consists of 2 modules: `mitmproxy.py` and `sshdebug.py`.
Module `mitmproxy.py` contains implementation of proxy and replay servers
for supported network protocols. Module `sshdebug.py` serves for more human-friendly
debugging output of unencrypted SSH messages.

The library is built on the Python Twisted network framework - see the project homepage
at [twistedmatrix.com](http://twistedmatrix.com/).


Supported network protocols
---------------------------
* Telnet
* HTTP
* HTTPS/SSL
* SSH
* SNMP


MITM proxy server in general
----------------------------
```
                +----------------------MITM PROXY---------------------+
                | +--------------+     +-------+     +--------------+ |
                | |    (receive) | <<< | Queue | <<< | (transmit)   | |
+--------+      | |              |     +-------+     |              | |      +--------+
| Client | <--> | | Proxy Server |                   | Proxy Client | | <--> | Server |
+--------+      | |              |     +-------+     |              | |      +--------+
                | |   (transmit) | >>> | Queue | >>> | (receive)    | |
                | +--------------+     +-------+     +--------------+ |
                +-----------------------------------------------------+
```

As you can see in the above diagram, the MITM proxy has 2 componets - proxy server
and proxy client. These components communicate internally via deferred queues
and all of the communication is logged for later use by the replay server.
For details about deferred queues RTFM at [defer-intro](http://twistedmatrix.com/documents/current/core/howto/defer-intro.html).

More info about TCP/UDP clients/servers in Twisted is available on the Twisted core [doc pages](http://twistedmatrix.com/documents/current/core/howto/index.html).
Most of the proxies are quite similar - one exception is SSH because it has multiple layers.
MITM SSH proxy and replay servers are using implementation of SSHv2 protocol
from `twisted.conch.ssh` package. There are some examples of SSH clients and
servers on twisted conch documentation pages:
[conch doc](http://twistedmatrix.com/documents/current/conch/index.html).
Another `twisted.conch.ssh` howto can be found here:
[ticket-5474](http://twistedmatrix.com/trac/ticket/5474)
and
[ticket-6001](http://twistedmatrix.com/trac/ticket/6001).


Notes on SSH
------------
### SSH keypairs
SSH proxy/replay requires SSH keypairs even when they are not being used,
so you should generate them with either `mitmkeygen` or by hand (and specify
their location on command-line if you put them in non-default location).

### Communication
The communication between proxy components starts during authentication.
Proxy server first negotiates authentication method with the client
and then forwards it to the proxy client, which in turn tries authenticating
against the real server. Then the proxy client informs proxy server about
the authentication result. After SSH transport layer connection is established,
the proxy simply forwards (decrypts and re-encrypts) connection layer packets.
The forwarding is done by the `mitmproxy.ProxySSHConnection` class which is a
subclass of `ssh.connection.SSHConnection`. The `mitmproxy.ProxySSHConnection` class simply
overrides the `packetReceived` method which puts received packets into a queue and logs
the SSH channel data (`SSH_MSG_CHANNEL_DATA` message type), which is assumed to be
the interactive shell channel.

### Authentication
The client connects to proxy, the proxy in turn creates a connection
to real server and forwards the SSH banner to the client. The client then chooses
an authentication method to use and authenticates against the _proxy_.
In case of password auth the proxy simply forwards it to the real server.
With public key auth, however, the proxy needs to have the corresponding private
key to be able to authenticate client - so the proxy has its own keypair
to use for client connection. This also means that the proxy has to have the client's
keypair (or any other keypair that is accepted as valid for the given user on the real server).
Thus for the proxy to work with pubkey auth you need to add the public key of _proxy_ to
the list of allowed keys for the give user at the given real server (usually ~/.ssh/authorized_keys).


The proxy server uses Twisted's [Pluggable Authentication](http://twistedmatrix.com/documents/current/core/howto/cred.html) system.
Proxy authentication is implemented in these classes:
* ProxySSHUserAuthServer
* ProxySSHUserAuthClient
* SSHCredentialsChecker


Proxy server side is implemented mostly in the `SSHCredentialsChecker` class.
The `ProxySSHUserAuthServer` is a hack to be able to properly end the communication.
The authentication result is evaluted in callback method `SSHCredentialsChecker.is_auth_succes`.
There are three possible results:
* auth succeeded
* auth failed, more auth methods available - try another one
* auth failed, no more auth methods - disconnect


Proxy client auth is implemented in `ProxySSHUserAuthClient`.
It sends/receives information to/from proxy server through deferred queues.
After successful auth the ssh-connection service is started.


There are some issues with proxy auth:
* proxy and real client auth method attempt order must be the same
* real server might support less auth methods than proxy

First issue is solved by sending the name of current auth method used by client to proxy.
Second issue is solved by pretending method failure and waiting for another auth method.

The proxy tries to be as transparent as possible - everything depends only on server and client configuration
(eg. the number of allowed password auth attemps) - well, at least it *should*. ;)


### SSH Replay server
SSH replay server always successfully authenticates client on the first authentication method attempt.
The replay server is implemented in `mitmproxy.SSHReplayServerProtocol` and it is connected to the SSH service in
`mitmproxy.ReplayAvatar` class.

### SSH proxy drawbacks
The proxy only supports logging of SSH sessions with _only one_ open channel.
It does not support other SSH features like port forwarding.


Notes about SNMP proxy and replay server
----------------------------------------
SNMP proxy is ordinary UDP server that intercepts and forwards UDP packets.
Because of UDP protocol we do not know when the communication ends.
You can save the PID of SNMP proxy process and when the client ends you can terminate the proxy.
SNMP replay reads communication from log and compares received packets with expected packets.
It copes with different request IDs in packets.
There are functions for extracting and replacing the request-id from/in packets - `snmp_extract_request_id` and `snmp_replace_request_id`.
SNMP replay server works only with UDP.

