TARGET= fence_nss_wrapper

SBINDIRT=$(TARGET)

all: ${TARGET}

include ../../../make/defines.mk
include $(OBJDIR)/make/cobj.mk
include $(OBJDIR)/make/clean.mk
include $(OBJDIR)/make/install.mk
include $(OBJDIR)/make/uninstall.mk

OBJS=	fence_nss_wrapper.o

CFLAGS += -I${incdir} -I${nsprincdir} -I${nssincdir}

LDFLAGS += -L${libdir} -L${nsprlibdir} -L${nsslibdir} -lnss3 -lssl3

${TARGET}: ${OBJS}
	$(CC) -o $@ $^ $(LDFLAGS)

clean: generalclean

-include $(OBJS:.o=.d)
