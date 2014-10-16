TEMPFILE:=$(shell mktemp)
DATADIR:=$(abs_top_srcdir)/tests/data/metadata

check: $(TARGET:%=xml-check.%) $(SYMTARGET:%=xml-check.%)

xml-check.%: %
	$(eval INPUT=$(subst xml-check.,,$@))
	./$(INPUT) -o metadata > $(TEMPFILE)
	diff $(TEMPFILE) $(DATADIR)/$(INPUT).xml
	rm $(TEMPFILE)

xml-upload.%: %
	$(eval INPUT=$(subst xml-upload.,,$@))
	./$(INPUT) -o metadata > $(DATADIR)/$(INPUT).xml

# If test will fail, rerun fence agents to show problems
delay-check.%: %
	$(eval INPUT=$(subst delay-check.,,$@))
	test `/usr/bin/time -f "%e" ./$(INPUT) --delay 10 $(FENCE_TEST_ARGS) -- 2>&1 |\
	sed 's/\.//' | tail -n 1` -ge 1000 || \
	/usr/bin/time -f "%e" ./$(INPUT) --delay 0 $(FENCE_TEST_ARGS) --

