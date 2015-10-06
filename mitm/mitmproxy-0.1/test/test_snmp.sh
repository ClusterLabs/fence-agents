#!/usr/bin/env bash

set -e
HOST=${HOST:-""}
PASS=${PASS:-""}
LOGIN=${LOGIN:-""}
SRC_ROOT=..

if [ -z "$HOST" -o -z "$PASS" -o -z "$LOGIN" ]; then
    echo "*** Set variables! 'HOST=example.example.com PASS=pass LOGIN=user ./$0'"
    exit 1
fi

for action in status on off reboot ; do
    echo "# Testing action: ${action}"
    $SRC_ROOT/mitmproxy_snmp -H $HOST -o ${action}.log &
    PID=$!
    sleep 2
    fence_apc_snmp -a localhost -u 1610 -l $LOGIN -p $PASS -n 1 -d 1 -o ${action}
    kill -15 $PID
    $SRC_ROOT/mitmreplay_snmp -f ${action}.log > /dev/null &
    sleep 2
    fence_apc_snmp -a localhost -u 1610 -l $LOGIN -p $PASS -n 1 -d 1 -o ${action}
    rm -f ${action}.log
done
