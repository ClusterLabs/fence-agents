MAINTAINERCLEANFILES	= Makefile.in

sbin_PROGRAMS		= fence_zvm fence_zvmip

noinst_HEADERS		= fence_zvm.h

fence_zvm_SOURCES	= fence_zvm.c
fence_zvm_CFLAGS	= -D_GNU_SOURCE

fence_zvmip_SOURCES	= fence_zvmip.c
fence_zvmip_CFLAGS	= -D_GNU_SOURCE

man_MANS		= fence_zvm.8 fence_zvmip.8
