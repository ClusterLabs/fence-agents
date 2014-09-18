MAINTAINERCLEANFILES		= Makefile.in

sbin_PROGRAMS			= fence_kdump
libexec_PROGRAMS		= fence_kdump_send

noinst_HEADERS			= list.h message.h options.h version.h

fence_kdump_SOURCES		= fence_kdump.c
fence_kdump_CFLAGS		= -D_GNU_SOURCE

fence_kdump_send_SOURCES	= fence_kdump_send.c
fence_kdump_send_CFLAGS		= -D_GNU_SOURCE

dist_man_MANS			= fence_kdump.8 fence_kdump_send.8

FENCE_TEST_ARGS			= -n test

include $(top_srcdir)/make/agentccheck.mk

check: xml-check.fence_kdump
