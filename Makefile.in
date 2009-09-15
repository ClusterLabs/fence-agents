###############################################################################
###############################################################################
##
##  Copyright (C) 2006 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2.
##
###############################################################################
###############################################################################


all:
	make -C config
	make -C common
	make -C client
	make -C server

install:
	make -C config install
	make -C client install
	make -C server install

clean:
	make -C config clean
	make -C common clean
	make -C client clean
	make -C server clean

