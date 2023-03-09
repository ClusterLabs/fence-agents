###############################################################################
###############################################################################
##
##  Copyright (C) 2009-2021 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2.
##
###############################################################################
###############################################################################

MAINTAINERCLEANFILES	= Makefile.in

EXTRA_DIST		= docs/architecture.txt docs/fence_virt.txt \
			  docs/README docs/TODO include \
			  fence_virtd.service.in

SUBDIRS			= config common client server man

all-local: fence_virtd.service

clean-local:
	rm -f $(SPEC) fence_virtd.service

fence_virtd.service: fence_virtd.service.in
	SBINDIR="@sbindir@"; \
	INITCONFDIR="@initconfdir@"; \
	cat $^ > $@ ; \
	echo "EnvironmentFile=-$$INITCONFDIR/fence_virtd" >> $@ ;\
	echo "ExecStart=$$SBINDIR/fence_virtd \$$FENCE_VIRTD_ARGS" >> $@
