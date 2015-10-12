#!/usr/bin/bash
cd ..
./autogen.sh && ./configure && make && cd mitm/mitmproxy-0.1/ && python setup.py build && echo "OK"
