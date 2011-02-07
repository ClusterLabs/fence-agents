MAINTAINERCLEANFILES	= Makefile.in

TARGET			= fence_na

EXTRA_DIST		= $(TARGET).pl \
			  $(TARGET).conf.in \
			  $(TARGET).lib.in \
			  $(TARGET).pod.in

fencelibdir		= ${FENCEAGENTSLIBDIR}

fencelib_DATA		= $(TARGET).lib

conffiledir		= ${DEFAULT_CONFIG_DIR}

conffile_DATA		= $(TARGET).conf

sbin_SCRIPTS		= $(TARGET)

man_MANS		= $(TARGET).8

$(TARGET): $(TARGET).pl
	cat $^ |  sed \
		-e 's#@''NACONFFILE@#${conffiledir}/$(TARGET).conf#g' \
		-e 's#@''FENCEAGENTSLIBDIR@#${FENCEAGENTSLIBDIR}#g' \
	> $@

$(TARGET).pod: $(TARGET).pod.in
	cat $^ | sed \
		-e 's#@''NACONFFILE@#${conffiledir}/$(TARGET).conf#g' \
	> $@

$(TARGET).8: $(TARGET).pod
	pod2man --section=8 $< $@

$(TARGET).conf: $(TARGET).conf.in
	cat $^ | sed \
		-e 's#@''LOGDIR@#${LOGDIR}#g' \
		-e 's#@''CONFDIR@#${DEFAULT_CONFIG_DIR}#g' \
		-e 's#@''CONFFILE@#${DEFAULT_CONFIG_FILE}#g' \
	> $@

$(TARGET).lib: $(TARGET).lib.in
	cat $^ | sed \
		-e 's#@''NACONFFILE@#${conffiledir}/$(TARGET).conf#g' \
	> $@

clean-local:
	rm -f $(TARGET) $(TARGET).pod $(TARGET).8 $(TARGET).conf $(TARGET).lib
