'''
SSH message logger.

Log unencrypted ssh messages in human readable form.
'''

import logging
import struct
import textwrap
import sys

try:
    from Crypto import Util
except ImportError:
    sys.stderr.write("PyCrypto not installed! Install or disable ssh debug.")
    sys.exit(1)


class SSHDebug(object):
    '''
    Logger for unencrypted SSH messages.
    '''
    ssh_messages = {
        1: 'SSH_MSG_DISCONNECT',
        2: 'SSH_MSG_IGNORE',
        3: 'SSH_MSG_UNIMPLEMENTED',
        4: 'SSH_MSG_DEBUG',
        5: 'SSH_MSG_SERVICE_REQUEST',
        6: 'SSH_MSG_SERVICE_ACCEPT',
        20: 'SSH_MSG_KEXINIT',
        30: 'SSH_MSG_KEXDH_INIT',
        31: 'SSH_MSG_KEXDH_REPLY',
        21: 'SSH_MSG_NEWKEYS',
        50: 'SSH_MSG_USERAUTH_REQUEST',
        51: 'SSH_MSG_USERAUTH_FAILURE',
        52: 'SSH_MSG_USERAUTH_SUCCESS',
        53: 'SSH_MSG_USERAUTH_BANNER',
        60: 'SSH_MSG_USERAUTH_PK_OK',
        80: 'SSH_MSG_GLOBAL_REQUEST',
        81: 'SSH_MSG_REQUEST_SUCCESS',
        82: 'SSH_MSG_REQUEST_FAILURE',
        90: 'SSH_MSG_CHANNEL_OPEN',
        91: 'SSH_MSG_CHANNEL_OPEN_CONFIRMATION',
        92: 'SSH_MSG_CHANNEL_OPEN_FAILURE',
        93: 'SSH_MSG_CHANNEL_WINDOW_ADJUST',
        94: 'SSH_MSG_CHANNEL_DATA',
        95: 'SSH_MSG_CHANNEL_EXTENDED_DATA',
        96: 'SSH_MSG_CHANNEL_EOF',
        97: 'SSH_MSG_CHANNEL_CLOSE',
        98: 'SSH_MSG_CHANNEL_REQUEST',
        99: 'SSH_MSG_CHANNEL_SUCCESS',
        100: 'SSH_MSG_CHANNEL_FAILURE'}

    def __init__(self, showpass=False):
        super(SSHDebug, self).__init__()
        self.output = ''
        self.showpass = showpass

    def log_packet(self, who, where, msg_num, payload):
        self.output = self.get_direction(who, where)
        self.output += "="*70 + "\n"

        if self.ssh_messages.has_key(msg_num):
            msg_name = self.ssh_messages[msg_num]
        else:
            msg_name = "Unknown message name"
        self.output += "MSG_TYPE (byte):\n    %s (%s)\n" % (msg_num, msg_name)

        func = getattr(self, 'msg_%s' % msg_name[8:].lower(), None)
        if func:
            self.output += func(payload)
        else:
            self.output += self.ssh_payload(payload)

        self.output += "="*70 + "\n"
        logging.debug(self.output)

    def get_direction(self, who, where):
        assert who in ['client', 'server']
        assert where in ['in', 'out']

        if who == 'client' and where == 'out':
            return "        SERVER ... PROXY >>> CLIENT\n"
        elif who == 'client' and where == 'in':
            return "        SERVER ... PROXY <<< CLIENT\n"
        elif who == 'server' and where == 'out':
            return "        SERVER <<< PROXY ... CLIENT\n"
        elif who == 'server' and where == 'in':
            return "        SERVER >>> PROXY ... CLIENT\n"

    def indent_break(self, longstr):
        result = ''
        wrapped = textwrap.fill(longstr.encode('string_escape'), 60)
        for line in wrapped.split('\n'):
            if not line == "":
                result += "    " + line + "\n"
        return result

    def ssh_payload(self, payload):
        '''
        Print indented payload of packet.

        This is used when method for packet parsing don't exists.
        '''
        result = "PAYLOAD:\n"
        result += self.indent_break(payload)
        return result

    def msg_disconnect(self, payload):
        '''
        Process SSH_MSG_DISCONNECT

        uint32    reason code
        string    description in ISO-10646 UTF-8 encoding [RFC3629]
        string    language tag [RFC3066]
        '''
        def decode_code(key):
            '''
            Decode simple map from code to string.
            '''
            codes = {
                1: "SSH_DISCONNECT_HOST_NOT_ALLOWED_TO_CONNECT",
                2: "SSH_DISCONNECT_PROTOCOL_ERROR",
                3: "SSH_DISCONNECT_KEY_EXCHANGE_FAILED",
                4: "SSH_DISCONNECT_RESERVED",
                5: "SSH_DISCONNECT_MAC_ERROR",
                6: "SSH_DISCONNECT_COMPRESSION_ERROR",
                7: "SSH_DISCONNECT_SERVICE_NOT_AVAILABLE",
                8: "SSH_DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED",
                9: "SSH_DISCONNECT_HOST_KEY_NOT_VERIFIABLE",
                10: "SSH_DISCONNECT_CONNECTION_LOST",
                11: "SSH_DISCONNECT_BY_APPLICATION",
                12: "SSH_DISCONNECT_TOO_MANY_CONNECTIONS",
                13: "SSH_DISCONNECT_AUTH_CANCELLED_BY_USER",
                14: "SSH_DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE",
                15: "SSH_DISCONNECT_ILLEGAL_USER_NAME"
            }
            if key in codes.keys():
                return codes[key]
            else:
                return "UNKNOWN_CODE"

        uints, payload = get_uint32(payload)
        result = "REASON_CODE (uint32):\n    %s (%s)\n" % (uints[0],
            decode_code(uints[0]))
        strings, payload = get_net_string(payload, 1)
        result += "DESCRIPTION (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        # some ssh implementations don't send this part of packet
        # don't use next 2 lines
        #result += "LANGUAGE_TAG (string %s):\n" % len(strings[1])
        #result += self.indent_break(strings[1])
        return result

    def msg_ignore(self, payload):
        '''
        Process SSH_MSG_IGNORE 2

        string  data
        '''
        strings, payload = get_net_string(payload)
        result = "DATA (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        return result

    def msg_debug(self, payload):
        '''
        Process SSH_MSG_DEBUG 3

        boolean   always_display
        string    message in ISO-10646 UTF-8 encoding [RFC3629]
        string    language tag [RFC3066]
        '''
        bools, payload = get_boolean(payload)
        result = "ALWAYS_DISPLAY (boolean):\n    %s\n" % bools[0]
        strings, payload = get_net_string(payload, 2)
        result += "MESSAGE (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        result += "LANGUAGE_TAG (string %s):\n" % len(strings[1])
        result += self.indent_break(strings[1])
        return result

    def msg_unimplemented(self, payload):
        '''
        Process SSH_MSG_UNIMPLEMENTED 3
        uint32    packet sequence number of rejected message
        '''
        uints, payload = get_uint32(payload)
        result = "REJECTED_PACKET_SEQUENCE_NUMBER (uint32):\n"
        result += "    %s\n" % uints[0]
        return result

    def msg_service_request(self, payload):
        '''
        Proces SSH_MSG_SERVICE_REQUEST 5

        string    service name
        '''
        strings, payload = get_net_string(payload)
        result = "SERVICE_NAME (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        return result

    def msg_service_accept(self, payload):
        '''
        Proces SSH_MSG_SERVICE_ACCEPT 6

        string    service name
        '''
        strings, payload = get_net_string(payload)
        result = "SERVICE_NAME (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        return result

    def msg_kexinit(self, payload):
        '''
        Process SSH_MSG_KEXINIT 20
        byte[16]     cookie (random bytes)
        name-list    kex_algorithms
        name-list    server_host_key_algorithms
        name-list    encryption_algorithms_client_to_server
        name-list    encryption_algorithms_server_to_client
        name-list    mac_algorithms_client_to_server
        name-list    mac_algorithms_server_to_client
        name-list    compression_algorithms_client_to_server
        name-list    compression_algorithms_server_to_client
        name-list    languages_client_to_server
        name-list    languages_server_to_client
        boolean      first_kex_packet_follows
        uint32       0 (reserved for future extension)
        '''
        cookie = payload[0:16]
        result = "COOKIE (byte[16]):\n"
        result += self.indent_break(cookie)
        payload = payload[16:]
        lists, payload = get_name_list(payload, 10)
        result += "KEX_ALGORITHMS (name-list):\n"
        result += self.indent_break(lists[0])
        result += "SERVER_HOST_KEY_ALGORITHMS (name-list):\n"
        result += self.indent_break(lists[1])
        result += "ENCRYPTION_ALGORITHMS_CLIENT_TO_SERVER (name-list):\n"
        result += self.indent_break(lists[2])
        result += "ENCRYPTION_ALGORITHMS_SERVER_TO_CLIENT (name-list):\n"
        result += self.indent_break(lists[3])
        result += "MAC_ALGORITHMS_CLIENT_TO_SERVER (name-list):\n"
        result += self.indent_break(lists[4])
        result += "MAC_ALGORITHMS_SERVER_TO_CLIENT (name-list):\n"
        result += self.indent_break(lists[5])
        result += "COMPRESSION_ALGORITHMS_CLIENT_TO_SERVER (name-list):\n"
        result += self.indent_break(lists[6])
        result += "COMPRESSION_ALGORITHMS_SERVER_TO_CLIENT (name-list):\n"
        result += self.indent_break(lists[7])
        result += "LANGUAGES_CLIENT_TO_SERVER (name-list):\n"
        result += self.indent_break(lists[8])
        result += "LANGUAGES_SERVER_TO_CLIENT (name-list):\n"
        result += self.indent_break(lists[9])
        bools, payload = get_boolean(payload)
        result += "FIRST_KEX_PACKET_FOLLOWS (boolean):\n"
        result += self.indent_break(str(bools[0]))
        uints, payload = get_uint32(payload)
        result += "RESERVED_FOR_FUTURE_EXTENSION (uint32):\n"
        result += self.indent_break(str(uints[0]))
        return result

    def msg_newkeys(self, payload):
        '''
        Process SSH_MSG_NEWKEYS 21
        No payload to process.
        '''
        return payload

    def msg_kexdh_init(self, payload):
        '''
        Process SSH_MSG_KEXDH_INIT 30

        mpint   e
        '''
        mpints, payload = get_mpint(payload)
        result = "E:\n"
        result += self.indent_break(str(mpints[0]))
        return result

    #def msg_kexdh_reply(self, payload):
    #    '''
    #    Process SSH_MSG_KEXDH_REPLY 31

    #    string    server public host key and certificates (K_S)
    #    mpint     f
    #    string    signature of H
    #    '''
    #    strings, payload = get_net_string(payload)
    #    result = "SERVER_PUBLIC_HOST_KEY_AND_CERTS (string %s):\n" % len(
    #            strings[0])
    #    result += self.indent_break(strings[0])
    #    mpints, payload = get_mpint(payload)
    #    result += "F:\n    %s\n" % mpints[0]
    #    strings, payload = get_net_string(payload)
    #    result += "SIGNATURE_OF_H (string %s):\n" % len(strings[0])
    #    result += self.indent_break(strings[0])
    #    return result


    def msg_userauth_request(self, payload):
        '''
        Process SSH_MSG_USERAUTH_REQUEST 50
        string    user name in ISO-10646 UTF-8 encoding [RFC3629]
        string    service name in US-ASCII
        string    method name in US-ASCII
        ....      method specific fields
        '''
        strings, payload = get_net_string(payload, 3)
        result = "USER_NAME (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        result += "SERVICE_NAME (string %s):\n" % len(strings[1])
        result += self.indent_break(strings[1])
        result += "METHOD_NAME (string %s):\n" % len(strings[2])
        result += self.indent_break(strings[2])
        method = strings[2]
        if method == "publickey":
            # boolean   has signature
            # string    public key algorithm name
            # string    public key blob
            bools, payload = get_boolean(payload)
            has_signature = bools[0]
            result += "HAS_SIGNATURE (boolean):\n    %s\n" % has_signature
            strings, payload = get_net_string(payload, 2)
            result += "PUBLIC_KEY_ALGORITM_NAME (string %s):\n" % len(
                    strings[0])
            result += self.indent_break(strings[0])
            result += "PUBLIC_KEY_BLOB (string %s):\n" % len(strings[1])
            result += self.indent_break(strings[1])
            if has_signature:
                strings, payload = get_net_string(payload)
                result += "SIGNATURE (string %s):\n" % len(strings[0])
                result += self.indent_break(strings[0])
            return result
        elif method == "password":
            # boolean   new password
            # string    plaintext password in ISO-10646 UTF-8 encoding [RFC3629]
            # string    plaintext new password in ISO-10646 UTF-8 encoding
            #           [RFC3629]
            bools, payload = get_boolean(payload)
            has_new_password = bools[0]
            result += "HAS_NEW_PASSWORD (boolean):\n    %s\n" % has_new_password
            strings, payload = get_net_string(payload)
            if self.showpass:
                password = strings[0]
            else:
                password = "<show password disabled>"
            result += "PASSWORD (string %s):\n" % len(password)
            result += self.indent_break(password)
            if has_new_password:
                if self.showpass:
                    password = strings[0]
                else:
                    password = "<show password disabled>"
                strings, payload = get_net_string(payload)
                result += "NEW_PASSWORD (string %s):\n" % len(password)
                result += self.indent_break(password)
            return result
        elif method == "none":
            return result
        result += "METHOD_SPECIFIC_FIELDS:\n"
        result += self.indent_break(payload)
        return result

    def msg_userauth_pk_ok(self, payload):
        '''
        Process SSH_MSG_USERAUTH_PK_OK 60
        No payload to process.
        '''
        return payload

    def msg_userauth_failure(self, payload):
        '''
        Process SSH_MSG_USERAUTH_FAILURE
        name-list    authentications that can continue
        boolean      partial success
        '''
        lists, payload = get_name_list(payload)
        result = "AUTH_CAN_CONTINUE (name-list):\n"
        result += self.indent_break(lists[0])
        bools, payload = get_boolean(payload)
        result += "PARTIAL_SUCCESS (boolean):\n    %s\n" % bools[0]
        return result

    def msg_userauth_success(self, payload):
        '''
        Process SSH_MSG_USERAUTH_SUCCESS
        No payload to process.
        '''
        return payload

    def msg_userauth_banner(self, payload):
        '''
        Process SSH_MSG_USERAUTH_BANNER
        string    message in ISO-10646 UTF-8 encoding [RFC3629]
        string    language tag [RFC3066]
        '''
        strings, payload = get_net_string(payload, 2)
        result = "MESSAGE (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        result += "LANGUAGE_TAG (string %s):\n" % len(strings[1])
        result += self.indent_break(strings[1])
        return result


    def msg_channel_open(self, payload):
        '''
        Process SSH_MSG_CHANNEL_OPEN.

        string    channel type in US-ASCII only
        uint32    sender channel
        uint32    initial window size
        uint32    maximum packet size
        ....      channel type specific data follows
        '''
        strings, payload = get_net_string(payload)
        result = "CHANNEL_TYPE (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        uints, payload = get_uint32(payload, 3)
        result += "SENDER_CHANNEL (uint32):\n    %s\n" % uints[0]
        result += "INITIAL_WINDOWS_SIZE (uint32):\n    %s\n" % uints[1]
        result += "MAXIMUM_PACKET_SIZE (uint32):\n    %s\n" % uints[2]
        result += "CHANNEL_TYPE_SPECIFIC_DATA:\n"
        result += self.indent_break(payload)
        return result

    def msg_channel_open_confirmation(self, payload):
        '''
        Process SSH_MSG_CHANNEL_OPEN_CONFIRMATION

        uint32    recipient channel
        uint32    sender channel
        uint32    initial window size
        uint32    maximum packet size
        ....      channel type specific data follows
        '''
        uints, payload = get_uint32(payload, 4)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % uints[0]
        result += "SENDER_CHANNEL (uint32):\n    %s\n" % uints[1]
        result += "INITIAL_WINDOWS_SIZE (uint32):\n    %s\n" % uints[2]
        result += "MAXIMUM_PACKET_SIZE (uint32):\n    %s\n" % uints[3]
        result += "CHANNEL_TYPE_SPECIFIC_DATA:\n"
        result += self.indent_break(payload)
        return result

    def msg_channel_open_failure(self, payload):
        '''
        Process SSH_MSG_CHANNEL_OPEN_FAILURE

        uint32    recipient channel
        uint32    reason code
        string    description in ISO-10646 UTF-8 encoding [RFC3629]
        string    language tag [RFC3066]
        '''
        def decode_code(key):
            '''
            Decode simple map from code to string.
            '''
            codes = {
                1: "SSH_OPEN_ADMINISTRATIVELY_PROHIBITED",
                2: "SSH_OPEN_CONNECT_FAILED",
                3: "SSH_OPEN_UNKNOWN_CHANNEL_TYPE",
                4: "SSH_OPEN_RESOURCE_SHORTAGE",
            }
            if key in codes.keys():
                return codes[key]
            else:
                return "UNKNOWN_CODE"

        uints, payload = get_uint32(payload, 2)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % uints[0]
        result += "REASON_CODE (uint32):\n    %s (%s)\n" % (uints[1],
                decode_code(uints[1]))
        strings, payload = get_net_string(payload, 2)
        result += "DESCRIPTION (string %s):\n" % len(strings[0])
        result += self.indent_break(strings[0])
        result += "LANGUAGE (string %s):\n" % len(strings[1])
        result += self.indent_break(strings[1])
        return result

    def msg_channel_window_adjust(self, payload):
        '''
        Process SSH_MSG_CHANNEL_DATA
        uint32    recipient channel
        string    data
        '''
        uints, payload = get_uint32(payload, 2)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % uints[0]
        result += "BYTES_TO_ADD (uint32):\n    %s\n" % uints[1]
        return result

    def msg_channel_data(self, payload):
        '''
        Process SSH_MSG_CHANNEL_DATA

        uint32    recipient channel
        string    data
        '''
        uints, payload = get_uint32(payload)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % (uints[0])
        strings, payload = get_net_string(payload)
        result += "DATA (string %s):\n" % (len(strings[0]))
        result += self.indent_break(strings[0])
        return result

    def msg_channel_extended_data(self, payload):
        '''
        Process SSH_MSG_CHANNEL_EXTENDED_DATA
        uint32    recipient channel
        uint32    data_type_code
        string    data
        '''
        def decode_code(key):
            '''
            Decode simple map from code to string.
            '''
            codes = {
                1: "SSH_EXTENDED_DATA_STDERR",
            }
            if key in codes.keys():
                return codes[key]
            else:
                return "UNKNOWN_CODE"
        uints, payload = get_uint32(payload, 2)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % (uints[0])
        result += "DATA_TYPE_CODE (uint32):\n    %s (%s)\n" % (uints[0],
                decode_code(uints[0]))
        strings, payload = get_net_string(payload)
        result += "DATA (string %s):\n" % (len(strings[0]))
        result += self.indent_break(strings[0])
        return result

    def msg_channel_eof(self, payload):
        '''
        Process SSH_MSG_CHANNEL_EOF
        uint32    recipient channel
        '''
        uints, payload = get_uint32(payload)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % (uints[0])
        return result

    def msg_channel_close(self, payload):
        '''
        Process SSH_MSG_CHANNEL_CLOSE
        uint32    recipient channel
        '''
        uints, payload = get_uint32(payload)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % (uints[0])
        return result

    def msg_channel_request(self, payload):
        '''
        Process SSH_MSG_CHANNEL_REQUEST
        uint32    recipient channel
        string    request type in US-ASCII characters only
        boolean   want reply
        ....      type-specific data follows
        '''
        uints, payload = get_uint32(payload)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % (uints[0])
        strings, payload = get_net_string(payload)
        result += "REQUEST_TYPE (string %s):\n    %s\n" % (len(strings[0]),
                strings[0])
        bools, payload = get_boolean(payload)
        result += "WANT_REPLY (boolean):\n    %s\n" % bools[0]
        result += "TYPE_SPECIFIC_DATA:\n"
        result += self.indent_break(payload)
        return result

    def msg_channel_success(self, payload):
        '''
        Process SSH_MSG_CHANNEL_SUCCESS
        uint32    recipient channel
        '''
        uints, payload = get_uint32(payload)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % (uints[0])
        return result

    def msg_channel_failure(self, payload):
        '''
        Process SSH_MSG_CHANNEL_FAILURE
        uint32    recipient channel
        '''
        uints, payload = get_uint32(payload)
        result = "RECIPIENT_CHANNEL (uint32):\n    %s\n" % (uints[0])
        return result

    def msg_global_request(self, payload):
        '''
        Process SSH_MSG_GLOBAL_REQUEST
        string    request name in US-ASCII only
        boolean   want reply
        ....      request-specific data
        '''
        strings, payload = get_net_string(payload)
        result = "REQUEST_NAME (string %s):\n    %s\n" % (len(strings[0]),
                strings[0])
        bools, payload = get_boolean(payload)
        result += "WANT_REPLY (boolean):\n    %s\n" % bools[0]
        result += "REQUEST_SPECIFIC_DATA:\n"
        result += self.indent_break(payload)
        return result

    def msg_request_failure(self, payload):
        '''
        Process SSH_MSG_REQUEST_FAILURE
        '''
        result = self.indent_break(payload)
        return result

    def msg_request_success(self, payload):
        '''
        Process SSH_MSG_REQUEST_SUCCESS
        ....    response specific data
        '''
        result = "RESPONSE_SPECIFIC_DATA:\n"
        result += self.indent_break(payload)
        return result

def get_uint32(payload, count=1):
    '''
    Get uint32 values. [rfc4251#section-5]
    '''
    uints = []
    index = 0
    for _ in range(count):
        uint, = struct.unpack('!L', payload[index:index+4])
        uints.append(uint)
        index += 4
    return (uints, payload[index:])


def get_name_list(payload, count=1):
    '''
    Get name list. [rfc4251#section-5]
    '''
    lists = []
    for _ in range(count):
        uints, payload = get_uint32(payload)
        length = uints[0]
        lists.append(payload[:length])
        payload = payload[length:]
    return (lists, payload)

def get_mpint(payload, count=1):
    '''
    Get mpint number. [rfc4251#section-5]
    '''
    mpints = []
    index = 0
    for _ in range(count):
        length, = struct.unpack('>L', payload[index:index+4])
        mpints.append(Util.number.bytes_to_long(
            payload[index+4:index+4+length]))
        index += 4 + length
    return (mpints, payload[index:])

def get_boolean(payload, count=1):
    '''
    Get boolean values. [rfc4251#section-5]
    '''
    bools = []
    index = 0
    for _ in range(count):
        if payload[index] != "\x00":
            bools.append(True)
        else:
            bools.append(False)
        index += 1
    return (bools, payload[index:])

def get_net_string(payload, count=1):
    '''
    Get net string. [rfc4251#section-5]
    '''
    strings = []
    index = 0
    for _ in range(count):
        length, = struct.unpack('!L', payload[index:index+4])
        strings.append(payload[index+4:index+4+length])
        index += length + 4
    return (strings, payload[index:])

