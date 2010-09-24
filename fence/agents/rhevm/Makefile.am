MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_rhevm

EXTRA_DIST		= $(TARGET).py

sbin_SCRIPTS		= $(TARGET)

dist_man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk

clean-local: clean-man
	rm -f $(TARGET)
