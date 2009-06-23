MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_cisco_mds

EXTRA_DIST		= $(TARGET).py

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
