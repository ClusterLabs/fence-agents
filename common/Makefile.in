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

TARGETS=libfence_virt.a

libfence_virt_a_SOURCE=mcast.c ip_lookup.c simple_auth.c tcp.c \
		    debug.c simple_auth.c fdops.c log.c

INCLUDES=-I../include \
	-I/usr/include/openais -I/usr/include/libvirt \
	-I/usr/include/nss3 -I/usr/include/nspr4 \
	-I../../../cman/lib -I../../../ccs/lib -I/usr/include/libxml2 \
	-I/usr/include/libvirt

CFLAGS+=-DFENCE_RELEASE_NAME=\"devel\"

LIBS+=-L../../../cman/lib -L../../../ccs/lib -L${libdir}/openais \
      -L../../../dlm/lib -lnss3 -lxml2

all: ${TARGETS}

libfence_virt.a: ${libfence_virt_a_SOURCE:.c=.o}
	ar rc $@ $^

%.o: %.c
	gcc $(CFLAGS) -c -o $@ $^ $(INCLUDES)

clean:
	rm -f ${TARGETS} *~ *.o testprog

install:

