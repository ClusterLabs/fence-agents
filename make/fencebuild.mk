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
	> $@
