MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_mcdata

SRC			= $(TARGET).pl

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fencemanperl.mk

clean-local: clean-man
	rm -f $(TARGET)
