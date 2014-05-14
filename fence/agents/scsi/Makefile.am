MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_scsi

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET) fence_scsi_check

man_MANS		= $(TARGET).8

FENCE_TEST_ARGS         = -k 1

fence_scsi_check: $(TARGET)
	cp -s $^ $@

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk

clean-local: clean-man
	rm -f $(TARGET) $(SYMTARGET)
