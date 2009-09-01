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

MODULES=libvirt.so checkpoint.so multicast.so null.so

fence_virtd_SOURCES = main.c plugin.c
libvirt_so_SOURCES = libvirt.c
null_so_SOURCES = null.c
multicast_so_SOURCES = mcast.c
checkpoint_so_SOURCES = virt.c vm_states.c

INCLUDES=-I../include\
	-I/usr/include/openais -I/usr/include/libvirt \
	-I/usr/include/nss3 -I/usr/include/nspr4 \
	-I../../../cman/lib -I../../../ccs/lib -I/usr/include/libxml2 \
	-I/usr/include/libvirt

CFLAGS+=-DFENCE_RELEASE_NAME=\"devel\" -D_MODULE

LIBS+=-L/usr/lib64/openais -lnss3 -lxml2 -lSaCkpt -lccs -lvirt -lcman \
      -L../common -lfence_virt -Wl,-wrap,syslog,-wrap,closelog -lpthread
      
MAIN_LIBS=-L../config -lsimpleconfig

all: ${TARGETS} ${MODULES}

fence_virtd: ${fence_virtd_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) $(MAIN_LIBS)

multicast.so: ${multicast_so_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) -shared

libvirt.so: ${libvirt_so_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) -shared

null.so: ${null_so_SOURCES:.c=.o}
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
	rm -f ${TARGETS} ${MODULES} *.o *.d *~
