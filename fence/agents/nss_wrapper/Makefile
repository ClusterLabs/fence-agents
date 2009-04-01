TARGET= fence_nss_wrapper

SBINDIRT=$(TARGET)

all: ${TARGET}

include ../../../make/defines.mk
include $(OBJDIR)/make/cobj.mk
include $(OBJDIR)/make/clean.mk
include $(OBJDIR)/make/install.mk
include $(OBJDIR)/make/uninstall.mk

OBJS=	$(TARGET).o

CFLAGS += -I${nsprincdir} -I${nssincdir}
CFLAGS += -I${incdir}

LDFLAGS += -L${nsslibdir} -lnss3 -lssl3
LDFLAGS += -L${libdir}

${TARGET}: ${OBJS}
	$(CC) -o $@ $^ $(LDFLAGS)

clean: generalclean

-include $(OBJS:.o=.d)
