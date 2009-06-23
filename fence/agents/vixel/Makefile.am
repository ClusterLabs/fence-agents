MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_vixel

EXTRA_DIST		= $(TARGET).pl

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
