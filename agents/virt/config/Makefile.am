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

MAINTAINERCLEANFILES	  = Makefile.in

EXTRA_DIST		  = config.l config.y fence_virt.conf

noinst_LIBRARIES	  = libsimpleconfig.a

libsimpleconfig_a_SOURCES = \
			    simpleconfig.c

nodist_libsimpleconfig_a_SOURCES = \
			    y.tab.c \
			    config.c

libsimpleconfig_a_CFLAGS  = $(VIRT_AM_CFLAGS) $(AM_CFLAGS) -Wno-unused

noinst_HEADERS		  = config-stack.h


sysconf_DATA		  = fence_virt.conf

# local rules
y.tab.c: config.y
	$(YACC) -d $^

config.c: y.tab.c config.l
	$(LEX) -oconfig.c $(srcdir)/config.l

install-exec-hook:
	chmod 600 $(DESTDIR)$(sysconfdir)/fence_virt.conf

clean-local:
	rm -f config.tab.c config.tab.h config.c y.tab.c y.tab.h
