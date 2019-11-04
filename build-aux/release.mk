#
# Copyright (C) 2012-2019 Red Hat, Inc.  All rights reserved.
#
# Author: Fabio M. Di Nitto <fabbione@kronosnet.org>
#
# This software licensed under GPL-2.0+
#

# to build official release tarballs, handle tagging and publish.

# example:
# make -f build-aux/release.mk all version=0.9 release=yes publish

gpgsignkey = 1F22889A

project = kronosnet

deliverables = $(project)-$(version).sha256 \
               $(project)-$(version).tar.bz2 \
               $(project)-$(version).tar.gz \
               $(project)-$(version).tar.xz

.PHONY: all
all: tag tarballs sign  # first/last skipped per release/gpgsignkey respectively


.PHONY: checks
checks:
ifeq (,$(version))
	@echo ERROR: need to define version=
	@exit 1
endif
	@if [ ! -d .git ]; then \
		echo This script needs to be executed from top level cluster git tree; \
		exit 1; \
	fi


.PHONY: setup
setup: checks
	./autogen.sh
	./configure
	make maintainer-clean


.PHONY: tag
tag: setup ./tag-$(version)

tag-$(version):
ifeq (,$(release))
	@echo Building test release $(version), no tagging
	echo '$(version)' > .tarball-version
else
	# following will be captured by git-version-gen automatically
	git tag -a -m "v$(version) release" v$(version) HEAD
	@touch $@
endif


.PHONY: tarballs
tarballs: tag
	./autogen.sh
	./configure
	#make distcheck (disabled.. needs root)
	make dist


.PHONY: sha256
sha256: $(project)-$(version).sha256

# NOTE: dependency backtrack may fail trying to sign missing tarballs otherwise
#       (actually, only when signing tarballs directly, but doesn't hurt anyway)
$(deliverables): tarballs

$(project)-$(version).sha256:
	# checksum anything from deliverables except for in-prep checksums file
	sha256sum $(deliverables:$@=) | sort -k2 > $@


.PHONY: sign
ifeq (,$(gpgsignkey))
sign: $(deliverables)
	@echo No GPG signing key defined
else
sign: $(deliverables:=.asc)
endif

# NOTE: cannot sign multiple files at once
$(project)-$(version).%.asc: $(project)-$(version).%
	gpg --default-key "$(gpgsignkey)" \
		--detach-sign \
		--armor \
		$<


.PHONY: publish
publish:
ifeq (,$(release))
	@echo Building test release $(version), no publishing!
else
	@echo : pushing tags
	@git push --follow-tags origin
	@echo : publishing files
	@scp $(deliverables) $(deliverables:=.asc) www.kronosnet.org:kronosnet/releases/.
endif


.PHONY: clean
clean:
	rm -rf $(project)-* tag-* .tarball-version
