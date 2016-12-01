#!/bin/sh
# Run this to generate all the initial makefiles, etc.
# ("-I make" is superfluous, kept only for legacy purposes, if any)
autoreconf -i -I make -v && echo Now run ./configure and make
