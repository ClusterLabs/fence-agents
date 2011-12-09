MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_ipmilan

sbin_PROGRAMS		= $(TARGET)

noinst_HEADERS		= expect.h

fence_ipmilan_SOURCES	= expect.c ipmilan.c

dist_man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencemanc.mk

clean-local: clean-man
	rm -f $(TARGET)
