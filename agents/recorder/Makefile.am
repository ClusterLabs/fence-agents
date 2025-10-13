MAINTAINERCLEANFILES = Makefile.in

EXTRA_DIST = $(TARGET)

TARGET = fence_recorder

sbin_SCRIPTS = $(TARGET)

man_MANS = $(TARGET).8

FENCE_TEST_ARGS = -h compute-node-test --action monitor

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk

$(TARGET): $(TARGET:.in=)
	cp $< $@

clean-local:
	rm -f $(TARGET)
