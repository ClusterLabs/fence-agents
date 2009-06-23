MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_ilo

EXTRA_DIST		= $(TARGET).py

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
