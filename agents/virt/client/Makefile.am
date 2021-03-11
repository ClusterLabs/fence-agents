###############################################################################
###############################################################################
##
##  Copyright (C) 2009-2019 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2
##
###############################################################################
###############################################################################

MAINTAINERCLEANFILES	= Makefile.in

sbin_PROGRAMS		= fence_virt

fence_virt_SOURCES	= mcast.c serial.c main.c options.c tcp.c vsock.c

fence_virt_CFLAGS	= $(AM_CFLAGS) $(nss_CFLAGS) $(xml2_CFLAGS) $(PTHREAD_CFLAGS)

fence_virt_LDFLAGS	= $(AM_LDFLAGS) $(COMMON_LDFLAGS)
fence_virt_LDADD	= $(COMMON_LIBS) $(nss_LIBS) $(xml2_LIBS) $(PTHREAD_LIBS)

if xvmcompat
install-exec-hook: fence_virt
	(cd $(DESTDIR)/${sbindir}; $(LN_S) -nf $^ fence_xvm)

uninstall-hook:
	(cd $(DESTDIR)/${sbindir}; rm -f fence_xvm)
endif
