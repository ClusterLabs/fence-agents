DATADIR:=$(abs_top_srcdir)/tests/data/metadata
TEST_TARGET=$(filter-out $(TEST_TARGET_SKIP),$(TARGET))

check: $(TEST_TARGET:%=%.xml-check) $(SYMTARGET:%=%.xml-check) $(TEST_TARGET:%=%.delay-check) $(TEST_TARGET:%=%.rng-check)
delay-check: $(TEST_TARGET:%=%.delay-check) $(SYMTARGET:%=%.delay-check)
xml-check: $(TEST_TARGET:%=%.xml-check) $(SYMTARGET:%=%.xml-check)
xml-upload: $(TEST_TARGET:%=%.xml-upload) $(SYMTARGET:%=%.xml-upload)

%.xml-check: %
	$(eval INPUT=$(subst .xml-check,,$@))
	$(eval TEMPFILE = $(shell mktemp))
	./$(INPUT) -o metadata > $(TEMPFILE)
	diff $(TEMPFILE) $(DATADIR)/$(INPUT).xml
	rm $(TEMPFILE)

%.xml-upload: %
	$(eval INPUT=$(subst .xml-upload,,$@))
	./$(INPUT) -o metadata > $(DATADIR)/$(INPUT).xml

# If test will fail, rerun fence agents to show problems
%.delay-check: %
	$(eval INPUT=$(subst .delay-check,,$@))
	test `/usr/bin/time -p ./$(INPUT) --delay 10 $(FENCE_TEST_ARGS) -- 2>&1 |\
	awk -F"[. ]" -vOFS= '/real/ {print $$2,$$3}' | tail -n 1` -ge 1000 || \
	/usr/bin/time -p ./$(INPUT) --delay 0 $(FENCE_TEST_ARGS) --

%.rng-check: %
	$(eval INPUT=$(subst .rng-check,,$@))
	./$(INPUT) -o metadata | \
	xsltproc ${abs_top_srcdir}/lib/fence2rng.xsl - | \
	sed -e 's/ rha:description=/ description=/g' -e 's/ rha:name=/ name=/g' | \
	xmllint --nsclean --noout -;
