###############################################################################
###############################################################################
##
##  Copyright (C) 2006 Red Hat, Inc.
##  
##  This copyrighted material is made available to anyone wishing to use,
##  modify, copy, or redistribute it subject to the terms and conditions
##  of the GNU General Public License v.2.
##
###############################################################################
###############################################################################

include ../Makefile.top

TARGETS=libsimpleconfig.a

libsimpleconfig_a_SOURCE= config.tab.c \
			  config.c simpleconfig.c

INCLUDES=-I../include \
	-I/usr/include/openais -I/usr/include/libvirt \
	-I/usr/include/nss3 -I/usr/include/nspr4 \
	-I../../../cman/lib -I../../../ccs/lib -I/usr/include/libxml2 \
	-I/usr/include/libvirt

CFLAGS+=-DFENCE_RELEASE_NAME=\"devel\" -Wno-unused

LIBS+=-L../../../cman/lib -L../../../ccs/lib -L${libdir}/openais \
      -L../../../dlm/lib -lnss3 -lxml2

all: ${TARGETS}

libsimpleconfig.a: ${libsimpleconfig_a_SOURCE:.c=.o}
	ar rc $@ $^

config.tab.c config.tab.h: config.y
	bison -d $^

config.c: config.tab.h config.l
	flex -oconfig.c config.l

%.o: %.c
	gcc $(CFLAGS) -c -o $@ $^ $(INCLUDES)

clean:
	rm -f ${TARGETS} *~ *.o testprog config.tab.c config.tab.h config.c

install:
	if [ ! -f /etc/fence_virt.conf ]; then \
		install -m 0644 example.conf /etc/fence_virt.conf; \
	fi
