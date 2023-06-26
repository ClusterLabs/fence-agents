#!/usr/bin/bash

echo "### Running autogen"
./autogen.sh
echo "### Running configure"
./configure
echo "### Running make"
make
