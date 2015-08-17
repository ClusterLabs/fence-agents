DATADIR:=$(abs_top_srcdir)/tests/data/metadata
AWK_VAL='BEGIN {store=-1} /name=\"store_path\"/ {store=2} {if (store!=0) {print}; store--}'

check: $(TARGET:%=xml-check.%) $(SYMTARGET:%=xml-check.%) $(TARGET:%=delay-check.%) $(TARGET:%=rng-check.%)

xml-check.%: %
	$(eval INPUT=$(subst xml-check.,,$@))
	$(eval TEMPFILE = $(shell mktemp))
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib python ./$(INPUT) -o metadata | $(AWK) $(AWK_VAL) > $(TEMPFILE)
	diff $(TEMPFILE) $(DATADIR)/$(INPUT).xml
	rm $(TEMPFILE)

xml-upload.%: %
	$(eval INPUT=$(subst xml-upload.,,$@))
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib python ./$(INPUT) -o metadata | $(AWK) $(AWK_VAL) > $(DATADIR)/$(INPUT).xml

# If test will fail, rerun fence agents to show problems
delay-check.%: %
	$(eval INPUT=$(subst delay-check.,,$@))
	test `PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib /usr/bin/time -f "%e" \
	python ./$(INPUT) --delay 10 $(FENCE_TEST_ARGS) -- 2>&1 |\
	sed 's/\.//' | tail -n 1` -ge 1000 || ( \
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib /usr/bin/time -f "%e" \
	python ./$(INPUT) --delay 0 $(FENCE_TEST_ARGS) --; false )

rng-check.%: %
	PYTHONPATH=$(abs_srcdir)/../lib:$(abs_builddir)/../lib python ./$(INPUT) -o metadata | \
	/usr/bin/xsltproc ${abs_top_srcdir}/fence/agents/lib/fence2rng.xsl - | \
	sed -e 's/ rha:description=/ description=/g' -e 's/ rha:name=/ name=/g' | \
	xmllint --nsclean --noout -
