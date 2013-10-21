$(TARGET): $(SRC)
	if [ 0 -eq `echo "$(SRC)" | grep fence_ &> /dev/null; echo $$?` ]; then \
		PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib $(top_srcdir)/fence/agents/lib/check_used_options.py $(SRC); \
	else true ; fi

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
	> $@
