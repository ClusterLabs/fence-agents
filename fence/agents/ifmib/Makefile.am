MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_ifmib

EXTRA_DIST		= $(TARGET).py README

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
