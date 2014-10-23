#!/bin/sh
# Run this to generate all the initial makefiles, etc.
mkdir -p m4
autoreconf -i -I make -v && echo Now run ./configure and make
