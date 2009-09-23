MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_drac5

EXTRA_DIST		= fence_drac5.py

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
