MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_scsi fence_scsi_test

EXTRA_DIST		= fence_scsi.pl fence_scsi_test.pl

sbin_SCRIPTS		= $(TARGET)

include $(top_srcdir)/make/fencebuild.mk

clean-local:
	rm -f $(TARGET)
