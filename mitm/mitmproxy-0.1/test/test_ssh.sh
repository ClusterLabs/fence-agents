#!/usr/bin/env bash

set -e
HOST=${HOST:-""}
PASS=${PASS:-""}
LOGIN=${LOGIN:-""}
SRC_ROOT=..

if [ -z $HOST -o -z $PASS -o -z $LOGIN ]; then
    echo "*** Set variables! 'HOST=example.example.com PASS=pass LOGIN=user ./$0'"
    exit 1
fi

for action in status on off reboot ; do
    echo "# Testing action: ${action}"
    $SRC_ROOT/mitmproxy_ssh -H $HOST -o ${action}.log &
    sleep 2
    fence_apc -a localhost -u 2222 -l $LOGIN -p $PASS -n 1 -x -o ${action} \
        --ssh-options="-2 -o PubKeyAuthentication=no" --login-timeout=100
    $SRC_ROOT/mitmreplay_ssh -f ${action}.log > /dev/null &
    sleep 2
    fence_apc -a localhost -u 2222 -l $LOGIN -p $PASS -n 1 -x -o ${action} \
        --ssh-options="-2 -o PubKeyAuthentication=no" --login-timeout=100
    rm -f ${action}.log
done
