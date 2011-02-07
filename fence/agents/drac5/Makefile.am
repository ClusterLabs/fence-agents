MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_drac5

EXTRA_DIST		= $(TARGET).py

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk

clean-local: clean-man
	rm -f $(TARGET)
