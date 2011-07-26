MAINTAINERCLEANFILES		= Makefile.in

sbin_PROGRAMS			= fence_kdump fence_kdump_send

noinst_HEADERS			= list.h message.h options.h version.h

fence_kdump_SOURCES		= fence_kdump.c
fence_kdump_CFLAGS		= -D_GNU_SOURCE

fence_kdump_send_SOURCES	= fence_kdump_send.c
fence_kdump_send_CFLAGS		= -D_GNU_SOURCE

man_MANS			= fence_kdump.8 fence_kdump_send.8
