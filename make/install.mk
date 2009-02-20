install:
ifdef SBINDIRT
	install -d ${sbindir}
	install -m755 ${SBINDIRT} ${sbindir}
endif
ifdef SBINSYMT
	cp -a ${SBINSYMT} ${sbindir}
endif
ifdef INITDT
	install -d ${initddir}
	set -e; \
	for i in ${INITDT}; do \
		if [ -f $$i ]; then \
			install -m755 $$i ${initddir}; \
		else \
			install -m755 $(S)/$$i ${initddir}; \
		fi; \
	done
endif
ifdef MIBRESOURCE
	install -d ${mibdir}
	install -m644 $(S)/${MIBRESOURCE} ${mibdir}
endif
ifdef FENCEAGENTSLIB
	install -d ${DESTDIR}/${fenceagentslibdir}
	install -m644 ${FENCEAGENTSLIB} ${DESTDIR}/${fenceagentslibdir}
endif
ifdef DOCS
	install -d ${docdir}
	set -e; \
	for i in ${DOCS}; do \
		install -m644 $(S)/$$i ${docdir}; \
	done
endif
ifdef NOTIFYD
	install -d ${notifyddir}
	install -m755 ${NOTIFYD} ${notifyddir}
endif
