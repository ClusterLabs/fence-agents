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


TARGETS=fence_virtd

fence_virtd_SOURCES = mcast.c libvirt.c main.c

INCLUDES=-I../include\
	-I/usr/include/openais -I/usr/include/libvirt \
	-I/usr/include/nss3 -I/usr/include/nspr4 \
	-I../../../cman/lib -I../../../ccs/lib -I/usr/include/libxml2 \
	-I/usr/include/libvirt

CFLAGS+=-DFENCE_RELEASE_NAME=\"devel\" \
	-Wall -Werror -Wstrict-prototypes -Wshadow -ggdb -D_GNU_SOURCE

LIBS+=-L/usr/lib64/openais -lnss3 -lxml2 -lSaCkpt -lccs -lvirt -lcman \
      -L../common -lfence_virt

all: ${TARGETS}

fence_virtd: ${fence_virtd_SOURCES:.c=.o}
	gcc -o $@ $^ $(LIBS) -L../common -lfence_virt

%.o: %.c
	gcc $(CFLAGS) -c -o $@ $^ $(INCLUDES)

install: all
	if [ ! -d ${sbindir} ]; then \
		install -d ${sbindir}; \
	fi
	install -m755 ${TARGETS} ${sbindir}

clean:
	rm -f ${TARGETS} *.o *.d *~
