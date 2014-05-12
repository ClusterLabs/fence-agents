MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_scsi

SYMTARGET		= fence_scsi_check

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET) $(SYMTARGET)

man_MANS		= $(TARGET).8

$(SYMTARGET): $(TARGET)
	ln -s $^ $@

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk

clean-local: clean-man
	rm -f $(TARGET) $(SYMTARGET)
