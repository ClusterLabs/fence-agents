define gen_agent_from_py
	mkdir -p `dirname $@`
	cat $(abs_srcdir)/$@.py | \
	sed \
		-e 's#@''PYTHON@#${PYTHON}#g' \
		-e 's#@''RELEASE_VERSION@#${VERSION}#g' \
		-e 's#@''FENCEAGENTSLIBDIR@#${FENCEAGENTSLIBDIR}#g' \
		-e 's#@''LOGDIR@#${LOGDIR}#g' \
		-e 's#@''SBINDIR@#${sbindir}#g' \
		-e 's#@''LIBEXECDIR@#${libexecdir}#g' \
		-e 's#@''IPMITOOL_PATH@#${IPMITOOL_PATH}#g' \
		-e 's#@''OPENSTACK_PATH@#${OPENSTACK_PATH}#g' \
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
		-e 's#@''SBD_PATH@#${SBD_PATH}#g' \
		-e 's#@''STORE_PATH@#${CLUSTERVARRUN}#g' \
		-e 's#@''SUDO_PATH@#${SUDO_PATH}#g' \
		-e 's#@''SNMPWALK_PATH@#${SNMPWALK_PATH}#g' \
		-e 's#@''SNMPSET_PATH@#${SNMPSET_PATH}#g' \
		-e 's#@''SNMPGET_PATH@#${SNMPGET_PATH}#g' \
		-e 's#@''NOVA_PATH@#${NOVA_PATH}#g' \
		-e 's#@''POWERMAN_PATH@#${POWERMAN_PATH}#g' \
		-e 's#@''PING_CMD@#${PING_CMD}#g' \
		-e 's#@''PING6_CMD@#${PING6_CMD}#g' \
		-e 's#@''PING4_CMD@#${PING4_CMD}#g' \
	> $@

	if [ 0 -eq `echo "$(@)" | grep fence_ 2>&1 /dev/null; echo $$?` ]; then \
		PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(top_srcdir)/lib/check_used_options.py $@; \
	else true ; fi

	for x in `PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@) -o metadata | grep symlink | sed -e "s/.*\(fence.*\)\" .*/\1/g"`; do \
		cp -f $(@) $(@D)/$$x; \
		$(MAKE) $(@D)/$$x.8; \
	done
endef

# dependency, one on one
$(foreach t,$(TARGET),$(eval $(t) : $(t:=.py)))

# rule
$(TARGET):
	$(call gen_agent_from_py)

clean: clean-man
	rm -f $(CLEAN_TARGET:%.8=%) $(CLEAN_TARGET_ADDITIONAL) $(scsidata_SCRIPTS) */*.pyc *.pyc */*.wiki

	if [ "$(abs_builddir)" = "$(abs_top_builddir)/lib" ]; then \
		rm -f $(TARGET); \
	fi

clean-local: clean

install-exec-hook: $(TARGET)
	if [ -n "$(man8dir)" ]; then \
		echo " $(MKDIR_P) '$(DESTDIR)$(man8dir)'"; \
		$(MKDIR_P) "$(DESTDIR)$(man8dir)" || exit 1; \
	fi
	for p in $(TARGET); do \
		dir=`dirname $$p`; \
		for x in `PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $$p -o metadata | grep symlink | sed -e "s/.*\(fence.*\)\" .*/\1/g"`; do \
			echo " $(INSTALL_SCRIPT) $$dir/$$x '$(DESTDIR)$(sbindir)'"; \
			$(INSTALL_SCRIPT) $$dir/$$x "$(DESTDIR)$(sbindir)" || exit $$?; \
			echo " $(INSTALL_DATA) '$$dir/$$x.8' '$(DESTDIR)$(man8dir)'"; \
			$(INSTALL_DATA) "$$dir/$$x.8" "$(DESTDIR)$(man8dir)" || exit $$?; \
		done; \
	done

uninstall-hook: $(TARGET)
	files=`for p in $(TARGET); do \
		for x in \`PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $$p -o metadata | grep symlink | sed -e "s/.*\(fence.*\)\" .*/\1/g"\`; do \
			echo " rm -f '$(DESTDIR)$(sbindir)/$$x'"; \
			rm -f "$(DESTDIR)$(sbindir)/$$x"; \
			echo " rm -f '$(DESTDIR)$(man8dir)/$$x.8'"; \
			rm -f "$(DESTDIR)$(man8dir)/$$x.8"; \
		done; \
	done`
