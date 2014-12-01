MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_ilo_ssh

SYMTARGET		= fence_ilo3_ssh fence_ilo4_ssh

SRC			= $(TARGET).py

EXTRA_DIST		= $(SRC)

sbin_SCRIPTS		= $(TARGET) $(SYMTARGET)

man_MANS		= $(TARGET).8 $(SYMTARGET:%=%.8)

FENCE_TEST_ARGS         = -p test -a test -l test

$(SYMTARGET) : $(TARGET)
	cp $^ $@

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk
