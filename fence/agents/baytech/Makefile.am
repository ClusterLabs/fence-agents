MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_baytech

SRC			= $(TARGET).pl

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET)

dist_man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fencemanperl.mk

clean-local: clean-man
	rm -f $(TARGET)
