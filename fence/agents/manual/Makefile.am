MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_ack_manual

sbin_SCRIPTS		= $(TARGET)

EXTRA_DIST		= $(TARGET)

$(TARGET): $(TARGET).in
	cat $^ | sed \
		-e 's#@clustervarrun@#${CLUSTERVARRUN}#g' \
	> $@

clean-local:
	rm -f $(TARGET)
