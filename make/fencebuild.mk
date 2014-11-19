$(TARGET): $(SRC)
	bash $(top_srcdir)/scripts/fenceparse \
		$(top_srcdir)/make/copyright.cf REDHAT_COPYRIGHT \
		$(VERSION) \
		$(abs_srcdir) $@ | \
	sed \
		-e 's#@''FENCEAGENTSLIBDIR@#${FENCEAGENTSLIBDIR}#g' \
		-e 's#@''SNMPBIN@#${SNMPBIN}#g' \
		-e 's#@''LOGDIR@#${LOGDIR}#g' \
		-e 's#@''SBINDIR@#${sbindir}#g' \
		-e 's#@''LIBEXECDIR@#${libexecdir}#g' \
		-e 's#@''IPMITOOL_PATH@#${IPMITOOL_PATH}#g' \
		-e 's#@''AMTTOOL_PATH@#${AMTTOOL_PATH}#g' \
		-e 's#@''GNUTLSCLI_PATH@#${GNUTLSCLI_PATH}#g' \
		-e 's#@''COROSYNC_CMAPCTL_PATH@#${COROSYNC_CMAPCTL_PATH}#g' \
		-e 's#@''SG_PERSIST_PATH@#${SG_PERSIST_PATH}#g' \
		-e 's#@''SG_TURS_PATH@#${SG_TURS_PATH}#g' \
		-e 's#@''VGS_PATH@#${VGS_PATH}#g' \
		-e 's#@''SUDO_PATH@#${SUDO_PATH}#g' \
		-e 's#@''SSH_PATH@#${SSH_PATH}#g' \
		-e 's#@''TELNET_PATH@#${TELNET_PATH}#g' \
		-e 's#@''MPATH_PATH@#${MPATH_PATH}#g' \
		-e 's#@''STORE_PATH@#${CLUSTERVARRUN}#g' \
		-e 's#@''SUDO_PATH@#${SUDO_PATH}#g' \
	> $@

	if [ 0 -eq `echo "$(SRC)" | grep fence_ &> /dev/null; echo $$?` ]; then \
		PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib $(top_srcdir)/fence/agents/lib/check_used_options.py $@; \
	else true ; fi

clean: clean-man
	rm -f $(TARGET) $(SYMTARGET) *.pyc *.wiki

clean-local: clean