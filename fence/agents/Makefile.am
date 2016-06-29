MAINTAINERCLEANFILES		= Makefile.in

TARGET				= $(AGENTS_LIST:%.py=%)

SRC				= $(TARGET:=.py)

CLEAN_TARGET_ADDITIONAL		= kdump/fence_kdump_send manual/fence_ack_manual

EXTRA_DIST			= $(SRC) manual/fence_ack_manual.in manual/fence_ack_manual.8

sbin_SCRIPTS			= $(TARGET) manual/fence_ack_manual

EXTRA_SCRIPTS			=

man_MANS			= $(sbin_SCRIPTS:=.8)

sbin_PROGRAMS			= kdump/fence_kdump zvm/fence_zvm
libexec_PROGRAMS		= kdump/fence_kdump_send

noinst_HEADERS			= kdump/list.h kdump/message.h kdump/options.h kdump/version.h

kdump_fence_kdump_SOURCES	= kdump/fence_kdump.c
kdump_fence_kdump_CFLAGS	= -D_GNU_SOURCE -Ikdump

kdump_fence_kdump_send_SOURCES	= kdump/fence_kdump_send.c
kdump_fence_kdump_send_CFLAGS	= -D_GNU_SOURCE -Ikdump

dist_man_MANS			= kdump/fence_kdump.8 kdump/fence_kdump_send.8

scsidatadir			= $(CLUSTERDATA)
scsidata_SCRIPTS		= scsi/fence_scsi_check scsi/fence_scsi_check_hardreboot

zvm_fence_zvm_SOURCES		= zvm/fence_zvm.c
zvm_fence_zvm_CFLAGS		= -D_GNU_SOURCE

FENCE_TEST_ARGS			= \
login=test\n\
passwd=test\n\
ipaddr=test\n\
port=1\n\
managed=1\n\
devices=test\n\
session_url=http://test\n\
email=test@test.te

manual/fence_ack_manual: manual/fence_ack_manual.in
	mkdir -p $(@D)
	cat $^ | sed \
		-e 's#@clustervarrun@#${CLUSTERVARRUN}#g' \
	> $@

scsi/fence_scsi_check: scsi/fence_scsi
	cp $^ $@

scsi/fence_scsi_check_hardreboot: scsi/fence_scsi
	cp $^ $@

kdump/fence_kdump.8: kdump/fence_kdump $(top_srcdir)/fence/agents/lib/fence2man.xsl
	set -e && \
		./$(@:%.8=%) -o metadata > $(@D)/.$(@F).tmp && \
	xmllint --noout --relaxng $(top_srcdir)/fence/agents/lib/metadata.rng $(@D)/.$(@F).tmp && \
	xsltproc $(top_srcdir)/fence/agents/lib/fence2man.xsl $(@D)/.$(@F).tmp > $@
	xsltproc $(top_srcdir)/fence/agents/lib/fence2wiki.xsl $(@D)/.$(@F).tmp | grep -v '<?xml' > $(@D)/$(@F:%.8=%.wiki)

kdump/fence_kdump_send.8:
	true

manual/fence_ack_manual.8:
	true

zvm/fence_zvm.8: zvm/fence_zvm
	cp $(top_srcdir)/fence/agents/zvm/fence_zvm_man_page $(@D)/fence_zvm.8

cisco_mds/fence_cisco_mds.delay-check: cisco_mds/fence_cisco_mds
	$(eval INPUT=$(subst .delay-check,,$@))
	FENCE_TEST_ARGS_CISCO_MDS=$$(/bin/echo -e '$(FENCE_TEST_ARGS)' | sed 's#port=1#port=fc1/1#'); \
	test `PYTHONPATH=$(abs_srcdir)/lib:$(abs_builddir)/lib /usr/bin/time -f "%e" \
	sh -c "/bin/echo -e 'delay=10\n $$FENCE_TEST_ARGS_CISCO_MDS' | $(PYTHON) ./$(INPUT)" 2>&1 |\
	sed 's/\.//' | tail -n 1` -ge 1000 || ( \
	PYTHONPATH=$(abs_srcdir)/lib:$(abs_builddir)/lib /usr/bin/time -f "%e" \
	sh -c "/bin/echo -e "delay=0\n $$FENCE_TEST_ARGS_CISCO_MDS" | $(PYTHON) ./$(INPUT)"; false )

include $(top_srcdir)/make/fencebuild.mk
include $(top_srcdir)/make/fenceman.mk
include $(top_srcdir)/make/agentpycheck.mk
