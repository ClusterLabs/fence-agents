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

TARGET			= $(sbin_PROGRAMS)

fence_virt_SOURCES	= mcast.c serial.c main.c options.c tcp.c vsock.c

fence_virt_CFLAGS	= $(VIRT_AM_CFLAGS) $(nss_CFLAGS) $(xml2_CFLAGS) $(PTHREAD_CFLAGS) $(AM_CFLAGS)

fence_virt_LDFLAGS	= $(VIRT_AM_LDFLAGS) $(COMMON_LDFLAGS)
fence_virt_LDADD	= $(VIRT_COMMON_LIBS) $(nss_LIBS) $(xml2_LIBS) $(PTHREAD_LIBS)

if xvmcompat
install-exec-hook: fence_virt
	(cd $(DESTDIR)/${sbindir}; $(LN_S) -nf $^ fence_xvm)

uninstall-hook:
	(cd $(DESTDIR)/${sbindir}; rm -f fence_xvm)
endif

fence_virt.delay-check: fence_virt
	$(eval INPUT=$(subst .delay-check,,$@))
	test `/usr/bin/time -p ./$(INPUT) -w 10 -n test $(FENCE_TEST_ARGS) -- 2>&1 |\
	awk -F"[. ]" -vOFS= '/real/ {print $$2,$$3}' | tail -n 1` -ge 1000 || \
	/usr/bin/time -p ./$(INPUT) -w 0 -n test $(FENCE_TEST_ARGS) --

include $(top_srcdir)/make/agentccheck.mk
