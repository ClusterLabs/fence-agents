###############################################################################
###############################################################################
##
##  Copyright (C) 2009-2019 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2.
##
###############################################################################
###############################################################################

MAINTAINERCLEANFILES	= Makefile.in aclocal.m4 configure depcomp \
			  config.guess config.sub missing install-sh \
			  ltmain.sh compile config.h.in config.h.in~ \
			  autoscan.log configure.scan test-driver \
			  m4/libtool.m4 m4/lt~obsolete.m4 m4/ltoptions.m4 \
			  m4/ltsugar.m4 m4/ltversion.m4 include/config.in*

AUTOMAKE_OPTIONS	= foreign

ACLOCAL_AMFLAGS		= -I m4

EXTRA_DIST		= autogen.sh .version architecture.txt \
			  fence_virtd.init.in fence_virtd.service.in \
			  fence_virt.txt README README.md TODO \
			  include build-aux

SUBDIRS			= config common client server man

all-local: fence_virtd.service

clean-local:
	rm -f fence_virtd.service

fence_virtd.service: fence_virtd.service.in
	SBINDIR="@sbindir@"; \
	SCDIR="@sysconfdir@"; \
	cat $^ > $@ ; \
	echo "EnvironmentFile=-$$SCDIR/sysconfig/fence_virtd" >> $@ ;\
	echo "ExecStart=$$SBINDIR/fence_virtd \$$FENCE_VIRTD_ARGS" >> $@

# release/versioning
BUILT_SOURCES	= .version
.version:
	echo $(VERSION) > $@-t && mv $@-t $@

dist-hook:
	echo $(VERSION) > $(distdir)/.tarball-version
	echo $(SOURCE_EPOCH) > $(distdir)/source_epoch
