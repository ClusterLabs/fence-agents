MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_scsi

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC) 

scsidatadir		= $(CLUSTERDATA)
scsidata_SCRIPTS	= fence_scsi_check fence_scsi_check_hardreboot

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

FENCE_TEST_ARGS         = -k 1

fence_scsi_check: $(TARGET)
	cp $^ $@

fence_scsi_check_hardreboot: $(TARGET)
	cp $^ $@

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk

clean-local: clean-man
	rm -f $(TARGET) $(SYMTARGET) $(scsidata_SCRIPTS)
