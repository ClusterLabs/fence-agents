# to build official release tarballs, handle tagging and publish.

gpgsignkey = 0x6CE95CA7  # signing key

project = fence-agents

deliverables = $(project)-$(version).sha256 \
               $(project)-$(version).tar.gz \
               $(project)-$(version).tar.xz

all: checks setup tag tarballs sha256 sign

checks:
ifeq (,$(version))
	@echo ERROR: need to define version=
	@exit 1
endif
	@if [ ! -d .git ]; then \
		echo This script needs to be executed from top level cluster git tree; \
		exit 1; \
	fi

setup: checks
	./autogen.sh
	./configure
	make maintainer-clean

tag: setup ./tag-$(version)

tag-$(version):
ifeq (,$(release))
	@echo Building test release $(version), no tagging
else
	git tag -a -m "v$(version) release" v$(version) HEAD
	@touch $@
endif

tarballs: tag
	./autogen.sh
	./configure
	make distcheck

sha256: $(project)-$(version).sha256

# NOTE: dependency backtrack may fail trying to sign missing tarballs otherwise
#       (actually, only when signing tarballs directly, but doesn't hurt anyway)
$(deliverables): tarballs

$(project)-$(version).sha256:
ifeq (,$(release))
	@echo Building test release $(version), no sha256
else
	# checksum anything from deliverables except for in-prep checksums file
	sha256sum $(deliverables:$@=) | sort -k2 > $@
endif

sign: $(project)-$(version).sha256.asc  # "$(deliverables:=.asc)" to sign all

# NOTE: cannot sign multiple files at once like this
$(project)-$(version).%.asc: $(project)-$(version).%
ifeq (,$(release))
	@echo Building test release $(version), no sign
else
	gpg --default-key $(gpgsignkey) \
		--detach-sign \
		--armor \
		$<
endif

publish:
ifeq (,$(release))
	@echo Building test release $(version), no publishing!
else
	git push --tags origin
	scp $(project)-$(version).* \
		fedorahosted.org:$(project)
	@echo Hey you!.. yeah you looking somewhere else!
	@echo remember to update the wiki and send the email to cluster-devel and linux-cluster
endif

clean:
	rm -rf $(project)* tag-*
