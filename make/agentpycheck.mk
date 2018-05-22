DATADIR:=$(abs_top_srcdir)/tests/data/metadata
AWK_VAL='BEGIN {store=-1} /name=\".*_path\"/ {store=2} {if (store!=0) {print}; store--}'

TEST_TARGET=$(filter-out $(TEST_TARGET_SKIP),$(TARGET))

check: $(TEST_TARGET:%=%.xml-check) $(SYMTARGET:%=%.xml-check) $(TEST_TARGET:%=%.delay-check) $(TEST_TARGET:%=%.rng-check)
xml-check: $(TEST_TARGET:%=%.xml-check) $(SYMTARGET:%=%.xml-check)
xml-upload: $(TEST_TARGET:%=%.xml-upload) $(SYMTARGET:%=%.xml-upload)

%.xml-check: %
	$(eval INPUT=$(subst .xml-check,,$(@F)))
	for x in $(INPUT) `PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@D)/$(INPUT) -o metadata | grep symlink | sed -e "s/.*\(fence.*\)\" .*/\1/g"`; do \
		TEMPFILE=$$(mktemp); \
		PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@D)/$$x -o metadata | $(AWK) $(AWK_VAL) > $$TEMPFILE && \
		diff $$TEMPFILE $(DATADIR)/$$x.xml || exit 1 && \
		rm $$TEMPFILE; \
	done

%.xml-upload: %
	$(eval INPUT=$(subst .xml-upload,,$(@F)))
	for x in $(INPUT) `PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@D)/$(INPUT) -o metadata | grep symlink | sed -e "s/.*\(fence.*\)\" .*/\1/g"`; do \
		PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@D)/$$x -o metadata | $(AWK) $(AWK_VAL) > $(DATADIR)/$$x.xml; \
	done

# If test will fail, rerun fence agents to show problems
%.delay-check: %
	$(eval INPUT=$(subst .delay-check,,$(@F)))
	for x in $(INPUT) `PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@D)/$(INPUT) -o metadata | grep symlink | sed -e "s/.*\(fence.*\)\" .*/\1/g"`; do \
		test `PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib /usr/bin/time -p \
		sh -c "printf 'delay=10\n $(FENCE_TEST_ARGS)' | $(PYTHON) $(@D)/$$x" 2>&1 |\
		awk -F"[. ]" -vOFS= '/real/ {print $$2,$$3}'` -ge 1000 || ( \
		PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib /usr/bin/time -p \
		sh -c "printf 'delay=0\n $(FENCE_TEST_ARGS)' | $(PYTHON) $(@D)/$$x"; false ); \
	done

%.rng-check: %
	$(eval INPUT=$(subst .rng-check,,$(@F)))
	for x in $(INPUT) `PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@D)/$(INPUT) -o metadata | grep symlink | sed -e "s/.*\(fence.*\)\" .*/\1/g"`; do \
		PYTHONPATH=$(abs_top_srcdir)/lib:$(abs_top_builddir)/lib $(PYTHON) $(@D)/$$x -o metadata | \
		xsltproc ${abs_top_srcdir}/lib/fence2rng.xsl - | \
		sed -e 's/ rha:description=/ description=/g' -e 's/ rha:name=/ name=/g' | \
		xmllint --nsclean --noout -; \
	done
