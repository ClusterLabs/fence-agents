uninstall:
ifdef SBINDIRT
	${UNINSTALL} ${SBINDIRT} ${sbindir}
endif
ifdef SBINSYMT
	${UNINSTALL} ${SBINSYMT} ${sbindir}
endif
ifdef INITDT
	${UNINSTALL} ${INITDT} ${initddir}
endif
ifdef MIBRESOURCE
	${UNINSTALL} ${MIBRESOURCE} ${mibdir}
endif
ifdef FENCEAGENTSLIB
	${UNINSTALL} ${FENCEAGENTSLIB}* ${DESTDIR}/${fenceagentslibdir}
endif
ifdef DOCS
	${UNINSTALL} ${DOCS} ${docdir}
endif
ifdef NOTIFYD
	${UNINSTALL} ${NOTIFYD} ${notifyddir}
endif
