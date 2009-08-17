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


TARGETS=fence_virtd libvirt.so

fence_virtd_SOURCES = mcast.c main.c plugin.c

libvirt_so_SOURCES = libvirt.c

INCLUDES=-I../include\
	-I/usr/include/openais -I/usr/include/libvirt \
	-I/usr/include/nss3 -I/usr/include/nspr4 \
	-I../../../cman/lib -I../../../ccs/lib -I/usr/include/libxml2 \
	-I/usr/include/libvirt

CFLAGS+=-DFENCE_RELEASE_NAME=\"devel\" -D_MODULE

LIBS+=-L/usr/lib64/openais -lnss3 -lxml2 -lSaCkpt -lccs -lvirt -lcman \
      -L../common -lfence_virt

all: ${TARGETS}

fence_virtd: ${fence_virtd_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) -L../common -lfence_virt

libvirt.so: ${libvirt_so_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) -shared -L../common -lvirt

%.o: %.c
	gcc $(CFLAGS) -c -o $@ $^ $(INCLUDES)

install: all
	if [ ! -d ${sbindir} ]; then \
		install -d ${sbindir}; \
	fi
	install -m755 ${TARGETS} ${sbindir}

clean:
	rm -f ${TARGETS} *.o *.d *~
