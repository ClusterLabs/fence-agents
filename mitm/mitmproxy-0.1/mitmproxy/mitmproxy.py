'''
Common MITM proxy classes.
'''

from twisted.internet import protocol, reactor, defer

# Twisted imports for SSH.
from twisted.cred import checkers, credentials, portal
from twisted.conch import avatar, error, interfaces
from zope.interface import implements
from twisted.conch.ssh import common, connection, factory, keys, \
                              transport, userauth, session
from twisted.python import failure

import Queue
import optparse
import time
import sys
import string
import re
import os
import sshdebug
import pdb
import difflib
import logging


# "undefined" class members, attributes "defined" outside init
# pylint: disable=E1101, W0201
global exit_code
exit_code = list()
exit_code.append(0)

def terminate():
    '''
    Shutdown the twisted reactor.
    '''
    if reactor.running:
        # There is problem with UDP reactor. Exception ReactorNotRunning is
        # thrown.
        try:
            reactor.stop()
        except:
            pass


class MITMException(Exception):
    '''
    Custom exception class for MITM proxy
    '''
    pass


def proxy_option_parser(port, localport):
    '''
    Default option parser for MITM proxies
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-H', '--host', dest='host', type='string',
        metavar='HOST', default='localhost',
        help='Hostname/IP of real server (default: %default)')
    parser.add_option(
        '-P', '--port', dest='port', type='int',
        metavar='PORT', default=port,
        help='Port of real server (default: %default)')
    parser.add_option(
        '-p', '--local-port', dest='localport', type='int',
        metavar='PORT', default=localport,
        help='Local port to listen on (default: %default)')
    parser.add_option(
        '-o', '--output', dest='logfile', type='string',
        metavar='FILE', default=None,
        help='Save log to FILE instead of writing to stdout')
    opts, args = parser.parse_args()
    return (opts, args)


def ssh_proxy_option_parser(port, localport):
    '''
    Option parser for SSH proxy
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-H', '--host', dest='host', type='string',
        metavar='HOST', default='localhost',
        help='Hostname/IP of real server (default: %default)')
    parser.add_option(
        '-P', '--port', dest='port', type='int',
        metavar='PORT', default=port,
        help='Port of real server (default: %default)')
    parser.add_option(
        '-p', '--local-port', dest='localport', type='int',
        metavar='PORT', default=localport,
        help='Local port to listen on (default: %default)')
    parser.add_option(
        '-o', '--output', dest='logfile', type='string',
        metavar='FILE', default=None,
        help='Save log to FILE instead of writing to stdout')
    parser.add_option(
        '-a', '--client-pubkey', dest='clientpubkey', type='string',
        metavar='FILE', default=os.path.expanduser('~/.mitmkeys/id_rsa.pub'),
        help='Use FILE as the client pubkey (default: %default)')
    parser.add_option(
        '-A', '--client-privkey', dest='clientprivkey', type='string',
        metavar='FILE', default=os.path.expanduser('~/.mitmkeys/id_rsa'),
        help='Use FILE as the client privkey (default: %default)')
    parser.add_option(
        '-b', '--server-pubkey', dest='serverpubkey', type='string',
        metavar='FILE', default=os.path.expanduser('~/.mitmkeys/id_rsa.pub'),
        help='Use FILE as the server pubkey (default: %default)')
    parser.add_option(
        '-B', '--server-privkey', dest='serverprivkey', type='string',
        metavar='FILE', default=os.path.expanduser('~/.mitmkeys/id_rsa'),
        help='Use FILE as the server privkey (default: %default)')
    parser.add_option(
        '-s', '--show-password', dest='showpassword', action='store_true',
        default=False,
        help='Show SSH password on the screen (default: %default)')
    parser.add_option(
        '-D', '--debug', dest='debug', action='store_true',
        default=False,
        help='Enable SSH message logger with output into ssh.debug')
    opts, args = parser.parse_args()
    return (opts, args)


def replay_option_parser(localport):
    '''
    Default option parser for replay servers
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-p', '--local-port', dest='localport', type='int',
        metavar='PORT', default=localport,
        help='Local port to listen on (default: %default)')
    parser.add_option(
        '-f', '--from-file', dest='inputfile', type='string',
        metavar='FILE', default=None,
        help='Read session capture from FILE instead of STDIN')
    parser.add_option(
        '-o', '--output', dest='logfile', type='string',
        metavar='FILE', default=None,
        help='Log into FILE instead of STDOUT')
    parser.add_option(
        '-d', '--delay-modifier', dest='delaymod', type='float',
        metavar='FLOAT', default=1.0,
        help='Modify response delay (default: %default)')
    opts, args = parser.parse_args()
    return (opts, args)


def ssh_replay_option_parser(localport):
    '''
    Option parser for SSH replay server
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-p', '--local-port', dest='localport', type='int',
        metavar='PORT', default=localport,
        help='Local port to listen on (default: %default)')
    parser.add_option(
        '-f', '--from-file', dest='inputfile', type='string',
        metavar='FILE', default=None,
        help='Read session capture from FILE instead of STDIN')
    parser.add_option(
        '-o', '--output', dest='logfile', type='string',
        metavar='FILE', default=None,
        help='Log into FILE instead of STDOUT')
    parser.add_option(
        '-d', '--delay-modifier', dest='delaymod', type='float',
        metavar='FLOAT', default=1.0,
        help='Modify response delay (default: %default)')
    parser.add_option(
        '-b', '--server-pubkey', dest='serverpubkey', type='string',
        metavar='FILE', default=os.path.expanduser('~/.mitmkeys/id_rsa.pub'),
        help='Use FILE as the server pubkey (default: %default)')
    parser.add_option(
        '-B', '--server-privkey', dest='serverprivkey', type='string',
        metavar='FILE', default=os.path.expanduser('~/.mitmkeys/id_rsa'),
        help='Use FILE as the server privkey (default: %default)')
    parser.add_option(
        '-s', '--show-password', dest='showpassword', action='store_true',
        default=False,
        help='Show SSH password on the screen (default: %default)')
    parser.add_option(
        '-D', '--debug', dest='debug', action='store_true',
        default=False,
        help='Enable SSH message logger with output into ssh.debug')
    opts, args = parser.parse_args()
    return (opts, args)


def viewer_option_parser():
    '''
    Default option parser for log viewer
    '''
    parser = optparse.OptionParser()
    parser.add_option(
        '-f', '--from-file', dest='inputfile', type='string',
        metavar='FILE', default=None,
        help='Read session capture from FILE instead of STDIN')
    parser.add_option(
        '-d', '--delay-modifier', dest='delaymod', type='float',
        metavar='FLOAT', default=1.0,
        help='Modify response delay (default: %default)')
    opts, args = parser.parse_args()
    return (opts, args)


PRINTABLE_FILTER = ''.join(
    [['.', chr(x)][chr(x) in string.printable[:-5]] for x in xrange(256)])


def snmp_extract_request_id(packet):
    '''
    Extract some SNMP request-id information like indicies and value. If an
    error occure, raise MITMException.

    @param packet: Bytes of packet.
    @return Tuple of request-id start index, end index and value in bytes.
    (start index, end index, value in bytes)
    '''
    # Squence type 0x30 and SNMP PDU types Ax0*
    complex_types = [0x30, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7]
    req_id = None
    i = 0
    type_count = 0

    while i < len(packet):
        try:
            msg_type = ord(packet[i])
            msg_i = i
            type_count += 1
            i += 1

            length = ord(packet[i])
            if length & 0x80 == 0x80:
                # Get length specified by more than one byte.
                len_bytes = length & 0x7f
                i += 1
                length = int(packet[i:i+len_bytes].encode('hex'), base=16)
                i += len_bytes - 1

            logging.debug("Type (%X) at [%d], Length = %d, bytes ends at [%d]",
                    msg_type, msg_i, length, i)

            if type_count == 5:
                # Request-id is in 5th Type block.
                req_id = (i+1, i+1+length, packet[i+1:i+1+length])
        except IndexError:
            exit_code.append(1)
            raise MITMException("Get other than SNMP packet.")

        # Move to next Type byte.
        if msg_type in complex_types:
            i += 1
        else:
            i += 1 + length

    if req_id == None:
        exit_code.append(1)
        raise MITMException("Get other than SNMP packet.")

    logging.debug("Request-id (0x%s) at [%d:%d]", req_id[2].encode('hex'),
            req_id[0], req_id[1])
    logging.debug("")
    return req_id


def snmp_replace_request_id(packet, from_packet, value=None):
    '''
    Replace SNMP request-id by request-id from other SNMP packet or from
    the request-id value. If parameter value is specified, the parameter
    from_packet is ignored.

    @param packet: SNMP packet to replace.
    @param from_packet: SNMP packet for request-id extracting.
    @param value: Correct request-id value.
    @return: Packet with replaced request-id.
    '''
    try:
        i_start, i_end, _ = snmp_extract_request_id(packet)
        if value != None:
            return packet[0:i_start] + value + packet[i_end:]
        _, _, value = snmp_extract_request_id(from_packet)
        return packet[0:i_start] + value + packet[i_end:]
    except IndexError:
        exit_code.append(1)
        raise MITMException("Get other than SNMP packet.")
    except TypeError:
        exit_code.append(1)
        raise MITMException("Bad value parameter.")


def compare_strings(str_a, str_b, a="A", b="B"):
    '''
    Helper function for visualisation of differences between 2 strings. Prints
    output only when logging is enabled.

    @param str_a: First string.
    @param str_b: Second string.
    @param a: Description of first string.
    @param b: Description of second string.
    @return: None
    '''
    logging.debug("MATCHING BLOCKS:")
    seq_matcher = difflib.SequenceMatcher(a = str_a, b = str_b)
    for block in seq_matcher.get_matching_blocks():
        logging.debug("  a[%d] and b[%d] match for %d elements" % block)
    #for opcode in seq_matcher.get_opcodes():
    #    logging.debug("  %s\ta[%d:%d] b[%d:%d]" % opcode)
    differ = difflib.Differ()
    diff = differ.compare([str_a + '\n'], [str_b + '\n'])
    logging.debug("DIFF: %s <---> %s", a, b)
    for i in diff:
        logging.debug("%s", i)


class Logger(object):
    '''
    logs telnet traffic to STDOUT/file (TAB-delimited)
    format: "time_since_start client/server 0xHex_data #plaintext"
    eg. "0.0572540760 server 0x0a0d55736572204e616d65203a20 #plaintext"
        "0.1084461212 client 0x6170630a #plaintext"
    '''
    def __init__(self):
        self.starttime = None
        self.logfile = None

    def open_log(self, filename):
        '''
        Set up a file for writing a log into it.
        If not called, log is written to STDOUT.
        '''
        self.logfile = open(filename, 'w')

    def close_log(self):
        '''
        Try to close a possibly open log file.
        '''
        if self.logfile is not None:
            self.logfile.close()
            self.logfile = None

    def log(self, who, what):
        '''
        Add a new message to log.
        '''
        # translate non-printable chars to dots
        plain = what.decode('hex').translate(PRINTABLE_FILTER)

        if self.starttime is None:
            self.starttime = time.time()

        timestamp = time.time() - self.starttime

        if self.logfile is not None:
            # write to a file
            self.logfile.write(
                "%0.10f\t%s\t0x%s\t#%s\n"
                % (timestamp, who, what, plain))
        else:
            # STDOUT output
            sys.stdout.write(
                "%0.10f\t%s\t0x%s\t#%s\n"
                % (timestamp, who, what, plain))


class ProxyProtocol(protocol.Protocol):
    '''
    Protocol class common to both client and server.
    '''
    def __init__(self):
        # all needed attributes are defined dynamically
        pass

    def proxy_data_received(self, data):
        '''
        Callback function for both client and server side of the proxy.
        Each side specifies its input (receive) and output (transmit) queues.
        '''
        if data is False:
            # Special value indicating that one side of our proxy
            # no longer has an open connection. So we close the
            # other end.
            self.receive = None
            self.transport.loseConnection()
            # the reactor should be stopping just about now
        elif self.transmit is not None:
            # Transmit queue is defined => connection to
            # the other side is still open, we can send data to it.
            self.transport.write(data)
            self.receive.get().addCallback(self.proxy_data_received)
        else:
            # got some data to be sent, but we no longer
            # have a connection to the other side
            exit_code.append(1)
            sys.stderr.write(
                'Unable to send queued data: not connected to %s.\n'
                % (self.origin))
            # the other proxy instance should already be calling
            # reactor.stop(), so we can just take a nap

    def dataReceived(self, data):
        '''
        Received something from out input. Put it into the output queue.
        '''
        self.log.log(self.origin, data.encode('hex'))
        self.transmit.put(data)

    def connectionLost(self, reason=protocol.connectionDone):
        '''
        Either end of the proxy received a disconnect.
        '''
        if self.origin == 'server':
            sys.stderr.write('Disconnected from real server.\n')
        else:
            sys.stderr.write('Client disconnected.\n')
        self.log.close_log()
        # destroy the receive queue
        self.receive = None
        # put a special value into tx queue to indicate connecion loss
        self.transmit.put(False)
        # stop the program
        terminate()

class UDPProxyServer(protocol.DatagramProtocol):
    '''
    UDP proxy server.
    '''
    def __init__(self, log, ipaddr, port):
        '''
        Set logger, address for proxy client and address of origin client.
        '''
        self.origin = 'client'
        self.client_addr = None
        self.client_port = None
        self.log = log
        self.receive = defer.DeferredQueue()
        self.transmit = defer.DeferredQueue()

        # proxy client and proxy server has switched transmit and receive
        client = UDPProxyClient(log, ipaddr, port, (self.receive,
            self.transmit))
        reactor.listenUDP(0, client)

    def startProtocol(self):
        '''
        Start proxy client.
        '''
        self.receive.get().addCallback(self.proxy_data_received)

    def stopProtocol(self):
        '''
        Terminate reactor.
        '''
        sys.stderr.write("%s side - Stop protocol.\n" % self.origin)
        terminate()

    def connectionRefused(self):
        '''
        Connection was refused.
        '''
        exit_code.append(1)
        sys.stderr.write("%s side - Connection Refused.\n" % self.origin)
        terminate()

    def datagramReceived(self, datagram, (host, port)):
        '''
        Received a datagram for opposite origin side. Pass it between proxy
        components (proxy server/proxy client). Save address of origin client.
        '''
        self.client_addr = host
        self.client_port = port
        self.log.log(self.origin, datagram.encode('hex'))
        self.transmit.put(datagram)

    def proxy_data_received(self, data):
        '''
        Callback method for sending data to origin side.
        '''
        self.transport.write(data, (self.client_addr, self.client_port))
        self.receive.get().addCallback(self.proxy_data_received)

class UDPProxyClient(protocol.DatagramProtocol):
    '''
    UDP proxy client.
    '''
    def __init__(self, log, ipaddr, port, (transmit, receive)):
        '''
        Set client.
        '''
        self.origin = 'server'
        self.log = log
        self.ipaddr = ipaddr
        self.port = port
        self.transmit = transmit
        self.receive = receive

    def startProtocol(self):
        '''
        Set host for sending datagrams.
        '''
        self.transport.connect(self.ipaddr, self.port)
        sys.stderr.write("Sending to %s:%d.\n" % (self.ipaddr, self.port))
        self.receive.get().addCallback(self.proxy_data_received)

    def stopProtocol(self):
        '''
        Terminate reactor.
        '''
        sys.stderr.write("%s side - Stop protocol.\n" % self.origin)
        terminate()

    def connectionRefused(self):
        '''
        Connection was refused.
        '''
        exit_code.append(1)
        sys.stderr.write("%s side - Connection Refused.\n" % self.origin)
        terminate()

    def datagramReceived(self, datagram, (host, port)):
        '''
        Received a datagram for opposite origin side. Pass it between proxy
        components (proxy server/proxy client).
        '''
        self.log.log(self.origin, datagram.encode('hex'))
        self.transmit.put(datagram)

    def proxy_data_received(self, data):
        '''
        Callback method for sending data to origin side.
        '''
        self.transport.write(data)
        self.receive.get().addCallback(self.proxy_data_received)

class ProxyClient(ProxyProtocol):
    '''
    Client part of the MITM proxy
    '''
    def connectionMade(self):
        '''
        Successfully established a connection to the real server
        '''
        sys.stderr.write('Connected to real server.\n')
        self.origin = self.factory.origin
        # input - data from the real server
        self.receive = self.factory.serverq
        # output - data for the real client
        self.transmit = self.factory.clientq
        self.log = self.factory.log

        # callback for the receiver queue
        self.receive.get().addCallback(self.proxy_data_received)


class ProxyClientFactory(protocol.ClientFactory):
    '''
    Factory for proxy clients
    '''
    protocol = ProxyClient

    def __init__(self, serverq, clientq, log):
        # which side we're talking to?
        self.origin = 'server'
        self.serverq = serverq
        self.clientq = clientq
        self.log = log

    def clientConnectionFailed(self, connector, reason):
        exit_code.append(1)
        self.clientq.put(False)
        sys.stderr.write('Unable to connect! %s\n' % reason.getErrorMessage())


class ProxyServer(ProxyProtocol):
    '''
    Server part of the MITM proxy
    '''
    # pylint: disable=R0201
    def connect_to_server(self):
        '''
        Example:
            factory = mitmproxy.ProxyClientFactory(
                self.transmit, self.receive, self.log)
            reactor.connect[PROTOCOL](
                self.host, self.port, factory [, OTHER_OPTIONS])
        '''
        exit_code.append(1)
        raise MITMException('You should implement this method in your code.')
    # pylint: enable=R0201

    def connectionMade(self):
        '''
        Unsuspecting client connected to our fake server. *evil grin*
        '''
        # add callback for the receiver queue
        self.receive.get().addCallback(self.proxy_data_received)
        sys.stderr.write('Client connected.\n')
        # proxy server initialized, connect to real server
        sys.stderr.write(
            'Connecting to %s:%d...\n' % (self.host, self.port))
        self.connect_to_server()


class ProxyServerFactory(protocol.ServerFactory):
    '''
    Factory for proxy servers
    '''
    def __init__(self, proto, host, port, log):
        self.protocol = proto
        # which side we're talking to?
        self.protocol.origin = "client"
        self.protocol.host = host
        self.protocol.port = port
        self.protocol.log = log
        self.protocol.receive = defer.DeferredQueue()
        self.protocol.transmit = defer.DeferredQueue()


class ReplayServer(protocol.Protocol):
    '''
    Replay server class
    '''
    def __init__(self):
        pass

    def connectionMade(self):
        sys.stderr.write('Client connected.\n')
        self.send_next()

    def send_next(self):
        '''
        Called after the client connects.
        We shall send (with a delay) all the messages
        from our queue until encountering either None or
        an exception. In case a reply is not expected from
        us at this time, the head of queue will hold None
        (client is expected to send more messages before
        we're supposed to send a reply) - so we just "eat"
        the None from head of our queue (sq).
        '''
        while True:
            try:
                # gets either:
                #  * a message - continue while loop (send the message)
                #  * None - break from the loop (client talks next)
                #  * Empty exception - close the session
                reply = self.serverq.get(False)
                if reply is None:
                    break
            except Queue.Empty:
                # both cq and sq empty -> close the session
                assert self.serverq.empty()
                assert self.clientq.empty()
                sys.stderr.write('Success.\n')
                self.success = True
                self.log.close_log()
                self.transport.loseConnection()
                break

            (delay, what) = reply
            self.log.log('server', what)
            # sleep for a while (read from proxy log),
            # modified by delayMod
            time.sleep(delay * self.delaymod)
            self.transport.write(what.decode('hex'))

    def dataReceived(self, data):
        '''
        Called when client send us some data.
        Compare received data with expected message from
        the client message queue (cq), report mismatch (if any)
        try sending a reply (if available) by calling sendNext().
        '''
        try:
            expected = self.clientq.get(False)
        except Queue.Empty:
            exit_code.append(1)
            raise MITMException("Nothing more expected in this session.")

        exp_hex = expected[1]
        got_hex = data.encode('hex')

        if got_hex == exp_hex:
            self.log.log('client', expected[1])
            self.send_next()
        else:
            # received something else, terminate
            exit_code.append(1)
            sys.stderr.write(
                "ERROR: Expected %s (%s), got %s (%s).\n"
                % (exp_hex, exp_hex.decode('hex').translate(PRINTABLE_FILTER),
                   got_hex, got_hex.decode('hex').translate(PRINTABLE_FILTER)))
            self.log.close_log()
            terminate()

    def connectionLost(self, reason=protocol.connectionDone):
        '''
        Remote end closed the session.
        '''
        if not self.success:
            exit_code.append(1)
            sys.stderr.write('FAIL! Premature end: not all messages sent.\n')
        sys.stderr.write('Client disconnected.\n')
        self.log.close_log()
        terminate()


class SNMPReplayServer(protocol.DatagramProtocol):
    '''
    Replay server for UDP protocol.
    '''
    def __init__(self, log, (serverq, clientq), delaymod, clientfirst):
        self.log = log
        self.serverq = serverq
        self.clientq = clientq
        self.delaymod = delaymod
        self.clientfirst = clientfirst
        self.success = False
        self.client_addr = None
        self.respond_id = None

    def connectionRefused(self):
        '''
        Connection was refused.
        '''
        exit_code.append(1)
        self.error("Client refused connection.")

    def datagramReceived(self, data, (host, port)):
        '''
        Called when client send us some data.
        Compare received data with expected message from
        the client message queue (cq), report mismatch (if any)
        try sending a reply (if available) by calling sendNext().
        Different request-ids in SNMP packet are ignored during comparsion.
        '''
        # NOTE: this remove sync mark 'None' from serverq, look into logreader
        if self.respond_id == None:
            self.send_next()
        # address for respond
        self.client_addr = (host, port)
        try:
            expected = self.clientq.get(False)
            exp_hex = expected[1]
            got_hex = data.encode('hex')
            compare_strings(got_hex, exp_hex, a='Got packet',
                    b='Expected packet')
            # Save request-id for respond
            _, _, self.respond_id = snmp_extract_request_id(data)
            # Replace request-id in expected packet by id from got packet.
            exp_hex = snmp_replace_request_id(exp_hex.decode('hex'), None,
                    value=self.respond_id).encode('hex')
        except Queue.Empty:
            exit_code.append(1)
            self.error("Nothing more expected in this session.")
            return
        except MITMException as exception:
            exit_code.append(1)
            self.error(exception)
            return

        if got_hex == exp_hex:
            self.log.log('client', exp_hex)
            self.send_next()
        else:
            exit_code.append(1)
            self.error("Expected %s (%s), got %s (%s)." % (exp_hex,
                exp_hex.decode('hex').translate(PRINTABLE_FILTER), got_hex,
                got_hex.decode('hex').translate(PRINTABLE_FILTER)))

    def error(self, errmsg):
        '''
        Write error message on standard error output and exit SNMPReplayServer.
        '''
        exit_code.append(1)
        sys.stderr.write("ERROR: %s\n" % (errmsg))
        self.log.close_log()
        terminate()

    def send_next(self):
        '''
        Called after the client connects.
        We shall send (with a delay) all the messages
        from our queue until encountering either None or
        an exception. In case a reply is not expected from
        us at this time, the head of queue will hold None
        (client is expected to send more messages before
        we're supposed to send a reply) - so we just "eat"
        the None from head of our queue (sq).
        '''
        try:
            while True:
                # gets either:
                #  * a message - continue while loop (send the message)
                #  * None - break from the loop (client talks next)
                #  * Empty exception - close the session
                reply = self.serverq.get(False)
                if reply is None:
                    break
                (delay, what) = reply
                assert self.respond_id != None
                # Set proper request-id for SNMP respond packet.
                respond = snmp_replace_request_id(what.decode('hex'), None,
                        self.respond_id)
                compare_strings(what, respond.encode('hex'),
                        a="respond old_id", b="respond new_id")
                self.log.log('server', respond.encode('hex'))
                # sleep for a while (read from proxy log), modified by delayMod
                time.sleep(delay * self.delaymod)
                self.transport.write(respond, self.client_addr)
        except Queue.Empty:
            # both cq and sq empty -> close the session
            assert self.serverq.empty()
            assert self.clientq.empty()
            sys.stderr.write('Success.\n')
            self.success = True
            self.log.close_log()
            self.transport.stopListening()
            terminate()
        except MITMException as exception:
            exit_code.append(1)
            self.error(exception)


class ReplayServerFactory(protocol.ServerFactory):
    '''
    Factory for replay servers
    '''
    protocol = ReplayServer

    def __init__(self, log, (serverq, clientq), delaymod, clientfirst):
        self.protocol.log = log
        self.protocol.serverq = serverq
        self.protocol.clientq = clientq
        self.protocol.delaymod = delaymod
        self.protocol.clientfirst = clientfirst
        self.protocol.success = False


def logreader(inputfile, serverq=Queue.Queue(), clientq=Queue.Queue(),
              clientfirst=None):
    '''
    Read the whole proxy log into two separate queues,
    one with the expected client messages (cq) and the
    other containing the replies that should be sent
    to the client.
    '''
    with open(inputfile) as infile:
        lasttime = 0
        for line in infile:
            # optional fourth field contains comments,
            # usually an ASCII representation of the data
            (timestamp, who, what, _) = line.rstrip('\n').split('\t')

            # if this is the first line of log, determine who said it
            if clientfirst is None:
                if who == "client":
                    clientfirst = True
                else:
                    clientfirst = False

            # strip the pretty-print "0x" prefix from hex data
            what = what[2:]
            # compute the time between current and previous msg
            delay = float(timestamp) - lasttime
            lasttime = float(timestamp)

            if who == 'server':
                # server reply queue
                serverq.put([delay, what])
            elif who == 'client':
                # put a sync mark into server reply queue
                # to distinguish between cases of:
                #  * reply consists of a single packet
                #  * more packets
                serverq.put(None)  # sync mark
                # expected client messages
                clientq.put([delay, what])
            else:
                exit_code.append(1)
                raise MITMException('Malformed proxy log!')
    return (serverq, clientq, clientfirst)


def logviewer(inputfile, delaymod):
    '''
    Loads and simulates a given log file in either real-time
    or dilated by a factor of delayMod.
    '''
    with open(inputfile) as infile:
        lasttime = 0
        for line in infile:
            # optional fourth field contains comments,
            # usually an ASCII representation of the data
            (timestamp, who, what, _) = line.rstrip('\n').split('\t')
            # strip the pretty-print "0x" prefix from hex data
            what = what[2:]
            # strip telnet IAC sequences
            what = re.sub('[fF][fF]....', '', what)
            # compute the time between current and previous msg
            delay = float(timestamp) - lasttime
            lasttime = float(timestamp)

            # wait for it...
            time.sleep(delay * delaymod)

            if who == 'server':
                sys.stdout.write(what.decode('hex'))
                sys.stdout.flush()


#####################
# SSH related stuff #
#####################

################################################################################
# SSH Transport Layer Classes
#   * SSHFactory
#   * SSHServerFactory
#   * ReplaySSHServerFactory
#   * SSHClientFactory
#   * SSHServerTransport
#   * SSHClientTransport
#   * ReplaySSHServerTransport
################################################################################
class SSHFactory(factory.SSHFactory):
    '''
    Base factory class for mitmproxy ssh servers. Set defualt ssh protocol and
    object attributes. Create and set your authentication checker or subclass
    and override defaults: protocol, services, portal, checker and attributes.

    @ivar spub: A path to server public key.
    @type spub: C{str}
    @ivar spriv: A path to server private key.
    @type spriv: C{str}
    '''
    def __init__(self, opts):
        '''
        SSHFactory construcotr.

        @param opts: Class created by some ssh option parser with atributes
        opts.logfile (path to logfile), opts.serverpubkey (path to server
        public key), opts.serverprivkey (path to server private key)
        '''
        # Default ssh protocol, realm and services.
        self.protocol = transport.SSHServerTransport
        self.services = {
            'ssh-userauth':userauth.SSHUserAuthServer,
            'ssh-connection':connection.SSHConnection,
        }
        self.portal = portal.Portal(Realm())

        # Defaut attributes.
        self.log = Logger()
        if opts.logfile is not None:
            self.log.open_log(opts.logfile)
        self.spub = opts.serverpubkey
        self.spriv = opts.serverprivkey
        self.sshdebug = sshdebug.SSHDebug(opts.showpassword)

    def set_authentication_checker(self, checker):
        '''
        Set portal's credentials checker.
        '''
        self.portal.checkers = {}
        self.portal.registerChecker(checker)

    def getPublicKeys(self):
        '''
        Provide public keys for proxy server.
        '''
        keypath = self.spub
        if not os.path.exists(keypath):
            exit_code.append(1)
            raise MITMException(
                "Private/public keypair not generated in the keys directory.")

        return {'ssh-rsa': keys.Key.fromFile(keypath)}

    def getPrivateKeys(self):
        '''
        Provide private keys for proxy server.
        '''
        keypath = self.spriv
        if not os.path.exists(keypath):
            exit_code.append(1)
            raise MITMException(
                "Private/public keypair not generated in the keys directory.")
        return {'ssh-rsa': keys.Key.fromFile(keypath)}


class SSHServerFactory(SSHFactory):
    '''
    Factory class for proxy SSH server.
    '''
    # ignore 'too-many-instance-attributes', 'too-many-arguments'
    # pylint: disable=R0902,R0913
    def __init__(self, opts):
        '''
        Initialize base class and override defualt protocol, services and set
        attributes and credentials checker.
        '''
        SSHFactory.__init__(self, opts)

        # Override default protocol and services
        self.protocol = SSHServerTransport
        self.services = {
            'ssh-userauth':ProxySSHUserAuthServer,
            'ssh-connection':ProxySSHConnection,
        }

        # Our attribute settings
        self.host = opts.host
        self.port = opts.port
        self.cpub = opts.clientpubkey
        self.cpriv = opts.clientprivkey
        self.showpass = opts.showpassword
        self.origin = 'client'
        self.serverq = defer.DeferredQueue()
        self.clientq = defer.DeferredQueue()
        # Aliases transmit and receive for the queues.
        #   serverq - data for server
        #   clientq - data for client
        # Proxy server receive data from client and transmit to server.
        self.receive = self.clientq
        self.transmit = self.serverq

        # Set our credentials checker.
        self.set_authentication_checker(SSHCredentialsChecker(self))
    # pylint: enable=R0913
    # pylint: enable=R0902


class ReplaySSHServerFactory(SSHFactory):
    '''
    Factory class for SSH replay server.
    '''
    def __init__(self, opts):
        '''
        Initialize base class and override protocol, portal and credentials
        checker.
        '''
        SSHFactory.__init__(self, opts)
        self.origin = 'client'
        self.protocol = ReplaySSHServerTransport

        # Create our service ReplayAvatar for portal.
        (serverq, clientq, clientfirst) = logreader(opts.inputfile)
        replay_factory = ReplayServerFactory(self.log, (serverq, clientq),
                opts.delaymod, clientfirst)
        replay_factory.protocol = SSHReplayServerProtocol
        self.avatar = ReplayAvatar(replay_factory.protocol())

        # Override default protal and credentials checker.
        self.portal = portal.Portal(Realm(self.avatar))
        self.set_authentication_checker(ReplaySSHCredentialsChecker())


# ignore 'too-many-instance-attributes'
# pylint: disable=R0902
class SSHClientFactory(protocol.ClientFactory):
    '''
    Factory class for proxy SSH client.
    '''
    def __init__(self, proto, proxy_factory, username, password):
        # which side we're talking to?
        self.origin = 'server'
        self.protocol = proto
        self.serverq = proxy_factory.serverq
        self.clientq = proxy_factory.clientq
        self.log = proxy_factory.log
        self.username = username
        self.password = password
        self.showpass = proxy_factory.showpass
        self.cpub = proxy_factory.cpub
        self.cpriv = proxy_factory.cpriv
        # Aliases transmit and receive for the queues.
        #   serverq - data for server
        #   clientq - data for client
        # Proxy client receive data from server and transmit to client.
        self.receive = self.serverq
        self.transmit = self.clientq
        self.sshdebug = proxy_factory.sshdebug

    def clientConnectionFailed(self, connector, reason):
        exit_code.append(1)
        self.clientq.put(False)
        sys.stderr.write('Unable to connect! %s\n' % reason.getErrorMessage())


# ignore 'too-many-public-methods'
# pylint: disable=R0904,R0902


class SSHServerTransport(transport.SSHServerTransport):
    '''
    SSH proxy server protocol. Subclass of SSH transport protocol layer
    representation for servers.
    '''
    # ignore 'too-many-public-methods'
    # pylint: disable=R0904
    def __init__(self):
        '''
        Nothing to do.
        '''
        pass

    def connectionMade(self):
        '''
        Calls parent method after establishing connection
        and sets some attributes.
        '''
        transport.SSHServerTransport.connectionMade(self)
        sys.stderr.write("Original client connected to proxy server.\n")

    def connectionLost(self, reason):
        '''
        Either end of the proxy received a disconnect.
        '''
        if self.factory.origin == 'server':
            sys.stderr.write('Disconnected from real server.\n')
        else:
            sys.stderr.write('Client disconnected.\n')
        self.factory.log.close_log()
        # destroy the receive queue
        self.factory.receive = None
        # put a special value into tx queue to indicate connecion loss
        self.factory.transmit.put(False)
        # stop the program
        terminate()

    def dispatchMessage(self, messageNum, payload):
        '''
        In parent method packets are distinguished and dispatched to message
        processing methods. Added extended logging.
        '''
        self.factory.sshdebug.log_packet(self.factory.origin, 'in', messageNum,
                payload)
        transport.SSHServerTransport.dispatchMessage(self, messageNum, payload)

    def sendPacket(self, messageType, payload):
        '''
        Extending internal logging and set message dispatching between proxy
        components if client successfully authenticated.
        '''
        self.factory.sshdebug.log_packet(self.factory.origin, 'out',
                messageType, payload)
        transport.SSHServerTransport.sendPacket(self, messageType, payload)

        if messageType == 52:
            # SSH_MSG_USERAUTH_SUCCESS
            self.factory.receive.get().addCallback(self.proxy_data_received)

    def proxy_data_received(self, data):
        '''
        Callback function for both client and server side of the proxy.
        Each side specifies its input (receive) and output (transmit) queues.
        '''
        if data is False:
            # Special value indicating that one side of our proxy
            # no longer has an open connection. So we close the
            # other end.
            self.factory.receive = None
            self.transport.loseConnection()
            # the reactor should be stopping just about now
        elif self.factory.transmit is not None:
            msgnum = ord(data[0])
            payload = data[1:]
            # Forward packet to it's intended destination
            self.sendPacket(msgnum, payload)
            # In case of disconnect packet we lose connection,
            # otherwise callback for data processing is set up
            if msgnum == 1:
                self.transport.loseConnection()
            else:
                self.factory.receive.get().addCallback(self.proxy_data_received)
        else:
            # got some data to be sent, but we no longer
            # have a connection to the other side
            exit_code.append(1)
            sys.stderr.write(
                'Unable to send queued data: not connected to %s.\n'
                % (self.factory.origin))
            # the other proxy instance should already be calling
            # reactor.stop(), so we can just take a nap

    # pylint: enable=R0904


class SSHClientTransport(transport.SSHClientTransport):
    '''
    SSH proxy client protocol. Subclass of SSH transport protocol layer
    representation for clients.
    '''
    def __init__(self):
        '''
        Set flag for ssh_DISCONNECT method.
        '''
        self.auth_layer = True

    def connectionMade(self):
        '''
        Call parent method after enstablishing connection and make some
        initialization.
        '''
        transport.SSHClientTransport.connectionMade(self)
        sys.stderr.write('Connected to real server.\n')

    def ssh_DISCONNECT(self, packet):
        '''
        Call parent method and inform proxy server about disconnect recieved
        from original server. This information depends on ssh layer.
        '''
        if self.auth_layer:
            self.factory.transmit.put(-1)
        else:
            self.factory.transmit.put(packet)
        transport.SSHClientTransport.ssh_DISCONNECT(self, packet)

    def connectionLost(self, reason):
        '''
        Either end of the proxy received a disconnect.
        '''
        sys.stderr.write('Disconnected from real server.\n')
        # put a special value into tx queue to indicate connecion loss
        self.factory.transmit.put(False)
        # destroy the receive queue
        self.factory.receive = None
        self.factory.log.close_log()
        terminate()

    def dispatchMessage(self, messageNum, payload):
        '''
        Add internal logging of incoming packets.
        '''
        self.factory.sshdebug.log_packet(self.factory.origin, 'in', messageNum,
                payload)
        transport.SSHClientTransport.dispatchMessage(self, messageNum, payload)

    def sendPacket(self, messageType, payload):
        '''
        Add internal logging of outgoing packets.
        '''
        self.factory.sshdebug.log_packet(self.factory.origin, 'out',
                messageType, payload)
        transport.SSHClientTransport.sendPacket(self, messageType, payload)

    def verifyHostKey(self, pubKey, fingerprint):
        '''
        Required implementation of server host key verification.
        As we're acting as a passthrogh, we can safely leave this
        up to the client.
        '''
        # ignore 'unused-argument' warning
        # pylint: disable=W0613
        return defer.succeed(1)
        # pylint: enable=W0613

    def connectionSecure(self):
        '''
        Required implementation of a call to run another service.
        '''
        self.requestService(
            ProxySSHUserAuthClient(
                self.factory.username, ProxySSHConnection()))

    def proxy_data_received(self, data):
        '''
        Callback function for both client and server side of the proxy.
        Each side specifies its input (receive) and output (transmit) queues.
        '''
        if data is False:
            # Special value indicating that one side of our proxy
            # no longer has an open connection. So we close the
            # other end.
            self.factory.receive = None
            self.transport.loseConnection()
            # the reactor should be stopping just about now
        elif self.factory.transmit is not None:
            # Transmit queue is defined => connection to
            # the other side is still open, we can send data to it.
            self.sendPacket(ord(data[0]), data[1:])
            self.factory.receive.get().addCallback(self.proxy_data_received)
        else:
            # got some data to be sent, but we no longer
            # have a connection to the other side
            exit_code.append(1)
            sys.stderr.write(
                'Unable to send queued data: not connected to %s.\n'
                % (self.factory.origin))
            # the other proxy instance should already be calling
            # reactor.stop(), so we can just take a nap

# pylint: enable=R0904


# pylint: disable=R0904
class ReplaySSHServerTransport(transport.SSHServerTransport):
    '''
    Provides SSH replay server service.
    '''
    def __init__(self):
        '''
        Nothing to do. Parent class doesn't have constructor.
        '''
        pass

    def connectionMade(self):
        '''
        Print info on stderr and call parent method after
        establishing connection.
        '''
        transport.SSHServerTransport.connectionMade(self)

    def dispatchMessage(self, messageNum, payload):
        '''
        Added extended logging.
        '''
        self.factory.sshdebug.log_packet(self.factory.origin, 'in', messageNum,
                payload)
        transport.SSHServerTransport.dispatchMessage(self, messageNum, payload)

    def sendPacket(self, messageType, payload):
        '''
        Added extended logging.
        '''
        self.factory.sshdebug.log_packet(self.factory.origin, 'out',
                messageType, payload)
        transport.SSHServerTransport.sendPacket(self, messageType, payload)
# pylint: enable=R0904


################################################################################
# SSH Authentication Layer Classes
#   * ProxySSHUserAuthServer
#   * ProxySSHUserAuthClient
#   * SSHCredentialsChecker
#   * ReplaySSHCredentialsChecker
#   * Realm
################################################################################
class ProxySSHUserAuthServer(userauth.SSHUserAuthServer):
    '''
    Implements server side of 'ssh-userauth'. Subclass is needed for
    implementation of transparent authentication trough proxy,
    concretely for sending disconnect messages.
    '''
    def __init__(self):
        '''
        Set password delay.
        '''
        self.passwordDelay = 0

    def _ebBadAuth(self, reason):
        '''
        A little proxy authentication hack.
        Send disconnect if real server send one.
        Override this class because we don't have access to transport object
        in Credentials checker object, so raised exception is caught here
        and disconnect msg is sent.
        '''
        if reason.check(MITMException):
            exit_code.append(1)
            self.transport.sendDisconnect(
                    transport.DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE,
                    'too many bad auths')
            return
        userauth.SSHUserAuthServer._ebBadAuth(self, reason)


class ProxySSHUserAuthClient(userauth.SSHUserAuthClient):
    '''
    Implements client side of 'ssh-userauth'.
    Supported authentication methods are publickey and password.
    '''
    def __init__(self, user, instance):
        '''
        Call parent constructor.
        '''
        userauth.SSHUserAuthClient.__init__(self, user, instance)

    def ssh_USERAUTH_FAILURE(self, packet):
        '''
        Inform the proxy server about auth-method failure and attempt to
        authenticate with method according to original client.
        '''
        if self.lastAuth is not "none":
            self.transport.factory.transmit.put(0)
        # Supported server methods.
        can_continue, _ = common.getNS(packet)
        # Get method name trought Deffered object.
        deferred_method = self.transport.factory.receive.get()
        deferred_method.addCallback(self.try_method, can_continue)
        return deferred_method

    def try_method(self, method, can_continue):
        '''
        Try authentication method received from proxy server and return boolean
        result.
        '''
        assert method in ['publickey', 'password', False]
        # False means no more authentication methods or client disconnected.
        # Proxy server may terminate reactor before proxy client send
        # DISCONNECT_MSG, but it doesn't matter.
        if method == False:
            exit_code.append(1)
            can_continue = []
        else:
            # Server supports less auth methods than proxy server. We pretend
            # that auth methods failed and wait for another auth method.
            if method not in can_continue:
                self.transport.factory.transmit.put(0)
                deferred_method = self.transport.factory.receive.get()
                deferred_method.addCallback(self.try_method, can_continue)
                return deferred_method
            else:
                can_continue = [method]

        # fix for python-twisted version 8.2.0 (RHEL 6.x)
        try:
            return self._cbUserauthFailure(None, iter(can_continue))
        except AttributeError:
            # old twisted 8.2.0
            if self.tryAuth(method):
                return
            exit_code.append(1)
            self.transport.sendDisconnect(
                    transport.DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE,
                    'no more authentication methods available')


    def ssh_USERAUTH_SUCCESS(self, packet):
        '''
        Add new callback for processing data from proxy server, inform proxy
        server about authentication method success and call parent method.
        '''
        self.transport.factory.receive.get().addCallback(
                self.transport.proxy_data_received)
        self.transport.auth_layer = False
        self.transport.factory.transmit.put(1)
        userauth.SSHUserAuthClient.ssh_USERAUTH_SUCCESS(self, packet)


    def show_password(self, password):
        '''
        Show password on proxy output if option was true.
        '''
        #if self.transport.factory.showpass:
        if self.transport.factory.showpass:
            sys.stderr.write("SSH 'password' for user '%s' is: '%s'\n" %
                    (self.transport.factory.username, password))
        return password


    def getPassword(self, prompt = None):
        '''
        Return deffered with password from ssh proxy server and add callback
        for showing password.
        '''
        tmp_deferred = self.transport.factory.password.get()
        tmp_deferred.addCallback(self.show_password)
        return tmp_deferred

    def getPublicKey(self):
        '''
        Create PublicKey blob and return it or raise exception.
        '''
        keypath = self.transport.factory.cpub
        if not (os.path.exists(keypath)):
            exit_code.append(1)
            raise MITMException(
                "Public/private keypair not generated in the keys directory.")
        return keys.Key.fromFile(keypath).blob()

    def getPrivateKey(self):
        '''
        Create PrivateKey object and return it or raise exception.
        '''
        keypath = self.transport.factory.cpriv
        if not (os.path.exists(keypath)):
            exit_code.append(1)
            raise MITMException(
                "Public/private keypair not generated in the keys directory.")
        return defer.succeed(keys.Key.fromFile(keypath).keyObject)


class SSHCredentialsChecker(object):
    '''
    Implement publickey and password authentication method on proxy server
    side.
    '''
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.ISSHPrivateKey,
                            credentials.IUsernamePassword,)

    def __init__(self, proxy_factory):
        self.proxy_factory = proxy_factory
        self.receive = self.proxy_factory.clientq
        self.transmit = self.proxy_factory.serverq
        self.password = defer.DeferredQueue()
        self.connected = False
    # ignore 'invalid-method-name'
    # pylint: disable=C0103
    # ignore 'nonstandard-exception'
    # pylint: disable=W0710
    def requestAvatarId(self, creds):
        '''
        Set a callback for user auth success
        '''
        assert hasattr(creds, "username")
        # set username for connect_to_server() method
        self.username = creds.username
        # set callback for evaluation of authentication result
        deferred = self.proxy_factory.receive.get().addCallback(
                self.is_auth_success)
        # inform proxy client about authentication method
        if hasattr(creds, 'password'):
            # password for proxy client
            self.password.put(creds.password)
            self.proxy_factory.transmit.put('password')
        else:
            self.proxy_factory.transmit.put('publickey')
        if not self.connected:
            self.connect_to_server()
            self.connected = True
        return deferred

    # pylint: enable=C0103

    def is_auth_success(self, result):
        '''
        Check authentication result from proxy client and raise exception,
        or return username for service.
        '''
        assert result in [-1, 0, 1]
        if result == 1:
            # Auth success
            return self.username
        elif result == 0:
            # Authentication Failure, so initiate another authentication
            # attempt with this exception.
            raise failure.Failure(error.UnauthorizedLogin)
        elif result == -1:
            # Received disconnect from server.
            exit_code.append(1)
            raise failure.Failure(
                    MITMException("No more authentication methods"))

    # pylint: enable=W0710

    def connect_to_server(self):
        '''
        Start mitm proxy client.
        '''
        # now connect to the real server and begin proxying...
        client_factory = SSHClientFactory(SSHClientTransport,
                                          self.proxy_factory,
                                          self.username,
                                          self.password)
        reactor.connectTCP(self.proxy_factory.host, self.proxy_factory.port,
                           client_factory)


class ReplaySSHCredentialsChecker(object):
    '''
    Allow access on reply server with publickey or password authentication
    method. This class do nothing useful, but it must be implemented because of
    twisted authentication framework.
    '''
    # ignore 'too-few-public-methods'
    # pylint: disable=R0903
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.ISSHPrivateKey,
                            credentials.IUsernamePassword,)
    def __init__(self):
        '''
        Nothing to do.
        '''
        pass

    # pylint: disable=C0103,W0613,R0201
    def requestAvatarId(self, creds):
        '''
        Return avatar id for any authentication method.
        '''
        return "ANONYMOUS"

    # pylint: enable=C0103,R0903,R0201,W0613


class Realm(object):
    '''
    The realm connects application-specific objects to the authentication
    system.

    Realm connects our service and authentication methods.
    '''
    # ignore 'too-few-public-methods'
    # pylint: disable=R0903
    implements(portal.IRealm)

    def __init__(self, avatar=avatar.ConchUser()):
        '''
        Set the default avatar object.
        '''
        self.avatar = avatar

    # ignore 'invalid-name', 'no-self-use'
    # pylint: disable=C0103,R0201
    def requestAvatar(self, avatarId, mind, *interfaces):
        '''
        Return object which provides one of the given interfaces of service.

        Our object provides no service interface and even won't be used, but
        this is needed for proper twisted ssh authentication mechanism.
        '''
        # ignore 'unused-argument' warning
        # pylint: disable=W0613
        return interfaces[0], self.avatar, lambda: None
        # pylint: enable=W0613

    # pylint: enable=C0103,R0201,R0903


################################################################################
# SSH Connection Layer Classes
#   * ProxySSHConnection
#   * ReplayAvatar
#   * SSHReplayServerProtocol
################################################################################
# ignore 'too-many-public-methods'
# pylint: disable=R0904
class ProxySSHConnection(connection.SSHConnection):
    '''
    Overrides regular SSH connection protocol layer.

    Dispatches packets between proxy componets (server/client part) instead of
    message processing and performs channel communication logging.
    '''
    def packetReceived(self, messageNum, packet):
        '''
        Log data and send received packet to the proxy server side.
        '''
        self.log_channel_communication(chr(messageNum) + packet)
        self.transport.factory.transmit.put(chr(messageNum) + packet)

    def log_channel_communication(self, payload):
        '''
        Logs channel communication.

        @param payload: The payload of the message at SSH connection layer.
        @type payload: C{str}
        '''
        # NOTE: does not distinguish channels,
        #       could be a problem if multiple channels are used
        #       (the problem: channel numbers are assigned "randomly")

        # match SSH_MSG_CHANNEL_DATA messages
        if ord(payload[0]) == 94:
            # Payload:
            # byte      SSH_MSG_CHANNEL_DATA (94)
            # uint32    recipient channel
            # string    data    (string = uint32 + string)

            # ssh message type
            msg = payload[0:1]

            # "pseudo-randomly" assigned channel number,
            # (almost) always 0x00000000 for shell
            channel = payload[1:5]

            # length of shell channel data in bytes,
            # undefined for other channel types
            datalen = payload[5:9]

            # channel data
            data = payload[9:]

            #sys.stderr.write("packet: %s %s %s %s\n"
            #    % (msg.encode('hex'), channel.encode('hex'),
            #    datalen.encode('hex'), data.encode('hex')))

            self.transport.factory.log.log(self.transport.factory.origin,
                    data.encode('hex'))

# pylint: enable=R0904


class ReplayAvatarSession(session.SSHSession):
    '''
    This fix some problems with client exit codes. Some of them request exit
    status after closing the session.
    '''
    def __init__(self, *args, **kw):
        session.SSHSession.__init__(self, *args, **kw)

    def loseConnection(self):
        '''
        Send ssh message with exit-status for ssh client after before session
        is closed. Also send SSH_MSG_CHANNEL_EOF before SSH_MSG_CHANNEL_CLOSE.
        '''
        self.conn.sendRequest(self, 'exit-status', "\x00"*4)
        session.SSHSession.loseConnection(self)


class ReplayAvatar(avatar.ConchUser):
    '''
    SSH replay service spawning shell
    '''
    implements(interfaces.ISession)

    def __init__(self, service_protocol):
        avatar.ConchUser.__init__(self)
        self.channelLookup.update({'session':ReplayAvatarSession})
        self.service_protocol = service_protocol
    def openShell(self, protocol):
        self.service_protocol.makeConnection(protocol)
        protocol.makeConnection(session.wrapProtocol(self.service_protocol))
    def getPty(self, terminal, windowSize, attrs):
        return None
    def execCommand(self, protocol, cmd):
        raise NotImplementedError
    def windowChanged(self, newWindowSize):
        pass
    def eofReceived(self):
        pass
    def closed(self):
        '''
        Stop reactor after SSH session is closed.
        '''
        terminate()


class SSHReplayServerProtocol(ReplayServer):
    '''
    Override ReplayServer protocol, because we can't stop reactor before client
    sends all messages.
    '''
    def __init__(self):
        ReplayServer.__init__(self)

    def connectionLost(self, reason=protocol.connectionDone):
        '''
        Don't terminate reactor like in parent method. It will be terminated
        at ssh layer.
        '''
        if not self.success:
            exit_code.append(1)
            sys.stderr.write('FAIL! Premature end: not all messages sent.\n')
        self.log.close_log()

