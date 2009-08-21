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


TARGETS=fence_virtd

MODULES=libvirt.so checkpoint.so

fence_virtd_SOURCES = mcast.c main.c plugin.c

libvirt_so_SOURCES = libvirt.c

checkpoint_so_SOURCES = virt.c vm_states.c

INCLUDES=-I../include\
	-I/usr/include/openais -I/usr/include/libvirt \
	-I/usr/include/nss3 -I/usr/include/nspr4 \
	-I../../../cman/lib -I../../../ccs/lib -I/usr/include/libxml2 \
	-I/usr/include/libvirt

CFLAGS+=-DFENCE_RELEASE_NAME=\"devel\" -D_MODULE

LIBS+=-L/usr/lib64/openais -lnss3 -lxml2 -lSaCkpt -lccs -lvirt -lcman \
      -L../common -lfence_virt
      
MAIN_LIBS=-L../config -lsimpleconfig

all: ${TARGETS} ${MODULES}

fence_virtd: ${fence_virtd_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) $(MAIN_LIBS)

libvirt.so: ${libvirt_so_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) -shared

checkpoint.so: ${checkpoint_so_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) -shared

%.o: %.c
	gcc $(CFLAGS) -c -o $@ $^ $(INCLUDES)

install: all
	# XXX hardcoded sbin
	if [ ! -d /usr/sbin ]; then \
		install -d /usr/sbin; \
	fi
	install -m755 ${TARGETS} /usr/sbin
	# XXX hardcoded sbin
	if [ ! -d /usr/lib64/fence_virt ]; then \
		install -d /usr/lib64/fence_virt ; \
	fi
	install -m755 ${MODULES} /usr/lib64/fence_virt

clean:
	rm -f ${TARGETS} *.o *.d *~
