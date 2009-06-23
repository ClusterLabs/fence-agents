MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_vmware_helper fence_vmware

EXTRA_DIST		= fence_vmware_helper.pl fence_vmware.py

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
