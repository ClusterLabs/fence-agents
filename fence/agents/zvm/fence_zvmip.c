/*
 * fence_zvmip.c: SMAPI interface for managing zVM Guests
 *
 * Copyright (C) 2012 Sine Nomine Associates
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.  If not, see
 * <http://www.gnu.org/licenses/>.
 *
 * Authors:
 * Neale Ferguson <neale@sinenomine.net>
 *
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <dirent.h>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>
#include <limits.h>
#include <errno.h>
#include <string.h>
#include <sys/wait.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netiucv/iucv.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <getopt.h>
#include <ctype.h>
#include <syslog.h>
#include "fence_zvm.h"

#define MIN(a,b)	((a) < (b) ? (a) : (b))
#define DEFAULT_TIMEOUT 300
#define DEFAULT_DELAY	0

#define ACT_OFFON 	0
#define ACT_OFF		1
#define ACT_ON		2
#define ACT_METADATA	3
#define ACT_STATUS	4
#define ACT_MONITOR	5
#define ACT_LIST	6
#define ACT_HELP	7

static int zvm_smapi_reportError(void *, void *);

static struct option longopts[] = {
	{"action",	required_argument,	NULL, 'o'},
	{"delay",	required_argument,	NULL, 'd'},
	{"help",	no_argument,		NULL, 'h'},
	{"ipaddr",	required_argument,	NULL, 'a'},
	{"password",	required_argument,	NULL, 'p'},
	{"plug",	required_argument,	NULL, 'n'},
	{"timeout",	required_argument,	NULL, 't'},
	{"username",	required_argument,	NULL, 'u'},
	{NULL,		0,			NULL, 0}
};

static const char *optString = "a:o:hn:p:t:u:";

static int zvm_metadata(void);
static int usage(void);

/**
 * zvm_smapi_open:
 * @zvm: z/VM driver information
 *
 * Opens a connection with the z/VM SMAPI server
 */
int
zvm_smapi_open(zvm_driver_t *zvm)
{
	int	rc = -1,
		option = SO_REUSEADDR,
		optVal = 1,
		lOption = sizeof(optVal);
	struct addrinfo hints, *ai;

	hints.ai_family   = AF_UNSPEC;
	hints.ai_socktype = SOCK_STREAM;
	hints.ai_flags    = AI_PASSIVE;
	hints.ai_protocol = IPPROTO_TCP;
	if ((rc = getaddrinfo(zvm->smapiSrv, "44444", &hints, &ai)) == 0) {
		if ((zvm->sd = socket(ai->ai_family, ai->ai_socktype, ai->ai_protocol)) != -1) {
			rc = setsockopt(zvm->sd,SOL_SOCKET,option,&optVal,lOption);

			if ((rc = connect(zvm->sd, ai->ai_addr, ai->ai_addrlen)) == -1) {
				syslog(LOG_ERR, "Error connecting to %s - %m", zvm->smapiSrv);
				close(zvm->sd);
			}
		} else {
			syslog(LOG_ERR, "Error creating socket - %m");
		}
	} else {
		syslog(LOG_ERR, "Error resolving server address: %s", gai_strerror(rc));
	}
	return(rc);
}

/**
 * zvm_smapi_imageRecycle
 * @zvm: z/VM driver information
 *
 * Deactivates a virtual image
 */
int
zvm_smapi_imageRecycle(zvm_driver_t *zvm)
{
	struct _inPlist {
		int32_t	lPlist;
		int32_t	lFName;
		char	fName[13];
	} __attribute__ ((packed)) *inPlist;
	struct _authUser {
		int32_t  lAuthUser;
		char	 userId[0];
	} __attribute__ ((packed)) *authUser;
	struct _authPass {
		int32_t  lAuthPass;
		char	 password[0];
	} __attribute__ ((packed)) *authPass;
	struct _image {
		int32_t	lTarget;
		char    target[0];
	} __attribute__ ((packed)) *image;
	int32_t	lInPlist;
	struct	_outPlist {
		smapiOutHeader_t hdr;
		int32_t	nActive;
		int32_t	nInActive;
		int32_t	lFail;
		char	failArray[0];
	} *outPlist = NULL;
	void	*pOut = NULL;
	int32_t	lRsp;
	uint32_t reqId;
	int	rc;

	/*
	 * Implement any delay
	 */ 
	if (zvm->delay > 0) 
		sleep(zvm->delay);

	lInPlist = sizeof(*inPlist) + sizeof(*authUser) + strlen(zvm->authUser) +
		   sizeof(*authPass) + strlen(zvm->authPass) + sizeof(*image) + 
		   + strlen(zvm->target);
	inPlist = malloc(lInPlist);
	if (inPlist != NULL) {
		authUser = (void *) ((uintptr_t) inPlist + sizeof(*inPlist));
		authPass = (void *) ((uintptr_t) authUser + sizeof(*authUser) +
			   strlen(zvm->authUser));
		image    = (void *) ((uintptr_t) authPass + sizeof(*authPass) + 
			   strlen(zvm->authPass));
		inPlist->lPlist = lInPlist - sizeof(inPlist->lPlist);
		inPlist->lFName = sizeof(inPlist->fName);
		memcpy(inPlist->fName, Image_Recycle, sizeof(inPlist->fName));
		authUser->lAuthUser = strlen(zvm->authUser);
		memcpy(authUser->userId, zvm->authUser, strlen(zvm->authUser));
		authPass->lAuthPass = strlen(zvm->authPass);
		memcpy(authPass->password, zvm->authPass, strlen(zvm->authPass));
		image->lTarget = strlen(zvm->target);
		strncpy(image->target, zvm->target, strlen(zvm->target));
		if ((rc = zvm_smapi_send(zvm, inPlist, &reqId, lInPlist)) != -1) {
			if ((rc = zvm_smapi_recv(zvm, &pOut, &lRsp)) != -1) {
				outPlist = pOut;
				if (outPlist->hdr.rc == 0) {
					syslog(LOG_INFO, "Recycling of %s successful",
					       zvm->target);
					rc = 0;
				} else {
					if ((ntohl(outPlist->hdr.rc) == RCERR_IMAGEOP) &
					    ((ntohl(outPlist->hdr.reason) == RS_NOT_ACTIVE) |
					     (ntohl(outPlist->hdr.reason) == RS_BEING_DEACT))) {
						syslog(LOG_INFO, "Recycling of %s successful",
						       zvm->target);
						rc = 0;
					} else {
						rc = ntohl(outPlist->hdr.rc);
						zvm->reason = ntohl(outPlist->hdr.reason);
						(void) zvm_smapi_reportError(inPlist, outPlist);
					}
				}
			}
		}
		free(inPlist);
		free(outPlist);
	} else {
		syslog(LOG_ERR, "%s - cannot allocate parameter list", __func__);
		rc = -1;
	}
	return(rc);
}

/**
 * zvm_smapi_imageDeactivate
 * @zvm: z/VM driver information
 *
 * Deactivates a virtual image
 */
int
zvm_smapi_imageDeactivate(zvm_driver_t *zvm)
{
	struct _inPlist {
		int32_t	lPlist;
		int32_t	lFName;
		char	fName[16];
	} __attribute__ ((packed)) *inPlist;
	struct _authUser {
		int32_t  lAuthUser;
		char	 userId[0];
	} __attribute__ ((packed)) *authUser;
	struct _authPass {
		int32_t  lAuthPass;
		char	 password[0];
	} __attribute__ ((packed)) *authPass;
	struct _image {
		int32_t	lTarget;
		char    target[0];
	} __attribute__ ((packed)) *image;
	struct _deactTime {
		int32_t lForceTime;
		char	forceTime[5];
	} __attribute__ ((__packed__)) *deactTime;
	int32_t	lInPlist;
	struct	_outPlist {
		smapiOutHeader_t hdr;
		int32_t	nActive;
		int32_t	nInActive;
		int32_t	lFail;
		char	failArray[0];
	} *outPlist = NULL;
	void	*pOut = NULL;
	int32_t	lRsp;
	uint32_t reqId;
	int	rc;

	/*
	 * Implement any delay
	 */ 
	if (zvm->delay > 0) 
		sleep(zvm->delay);

	lInPlist = sizeof(*inPlist) + sizeof(*authUser) + strlen(zvm->authUser) +
		   sizeof(*authPass) + strlen(zvm->authPass) + sizeof(*image) + 
		   sizeof(*deactTime) + strlen(zvm->target);
	inPlist = malloc(lInPlist);
	if (inPlist != NULL) {
		authUser =  (void *) ((uintptr_t) inPlist + sizeof(*inPlist));
		authPass =  (void *) ((uintptr_t) authUser + sizeof(*authUser) +
			    strlen(zvm->authUser));
		image    =  (void *) ((uintptr_t) authPass + sizeof(*authPass) + 
			    strlen(zvm->authPass));
		deactTime = (void *) ((intptr_t) image + sizeof(*image) + 
			    strlen(zvm->target));
		inPlist->lPlist = lInPlist - sizeof(inPlist->lPlist);
		inPlist->lFName = sizeof(inPlist->fName);
		memcpy(inPlist->fName, Image_Deactivate, sizeof(inPlist->fName));
		authUser->lAuthUser = strlen(zvm->authUser);
		memcpy(authUser->userId, zvm->authUser, strlen(zvm->authUser));
		authPass->lAuthPass = strlen(zvm->authPass);
		memcpy(authPass->password, zvm->authPass, strlen(zvm->authPass));
		image->lTarget = strlen(zvm->target);
		memcpy(image->target, zvm->target, strlen(zvm->target));
		deactTime->lForceTime = sizeof(deactTime->forceTime);
		memcpy(deactTime->forceTime, "IMMED", sizeof(deactTime->forceTime));
		if ((rc = zvm_smapi_send(zvm, inPlist, &reqId, lInPlist)) != -1) {
			if ((rc = zvm_smapi_recv(zvm, &pOut, &lRsp)) != -1) {
				outPlist = pOut;
				if (outPlist->hdr.rc == 0) {
					syslog(LOG_INFO, "Deactivation of %s successful",
					       zvm->target);
					rc = 0;
				} else {
					if ((outPlist->hdr.rc == RCERR_IMAGEOP) &
					    ((outPlist->hdr.reason == RS_NOT_ACTIVE) |
					     (outPlist->hdr.reason == RS_BEING_DEACT))) {
						syslog(LOG_INFO, "Deactivation of %s successful",
						       zvm->target);
						rc = 0;
					} else {
						rc = outPlist->hdr.rc;
						zvm->reason = outPlist->hdr.reason;
						(void) zvm_smapi_reportError(inPlist, outPlist);
					}
				}
			}
		}
		free(inPlist);
		free(outPlist);
	} else {
		syslog(LOG_ERR, "%s - cannot allocate parameter list", __func__);
		rc = -1;
	}
	return(rc);
}

/**
 * zvm_smapi_imageActivate
 * @zvm: z/VM driver information
 *
 * Deactivates a virtual image
 */
int
zvm_smapi_imageActivate(zvm_driver_t *zvm)
{
	struct _inPlist {
		int32_t	lPlist;
		int32_t	lFName;
		char	fName[14];
	} __attribute__ ((packed)) *inPlist;
	struct _authUser {
		int32_t  lAuthUser;
		char	 userId[0];
	} __attribute__ ((packed)) *authUser;
	struct _authPass {
		int32_t  lAuthPass;
		char	 password[0];
	} __attribute__ ((packed)) *authPass;
	struct _image {
		int32_t	lTarget;
		char    target[0];
	} __attribute__ ((packed)) *image;
	int32_t	lInPlist;
	struct	_outPlist {
		smapiOutHeader_t hdr;
		int32_t	nActive;
		int32_t	nInActive;
		int32_t	lFail;
		char	failArray[0];
	} *outPlist = NULL;
	void	*pOut = NULL;
	int32_t	lRsp;
	uint32_t reqId;
	int	rc;

	/*
	 * Implement any delay
	 */ 
	if (zvm->delay > 0) 
		sleep(zvm->delay);

	lInPlist = sizeof(*inPlist) + sizeof(*authUser) + strlen(zvm->authUser) +
		   sizeof(*authPass) + strlen(zvm->authPass) + sizeof(*image) + 
		   strlen(zvm->target);
	inPlist = malloc(lInPlist);
	if (inPlist != NULL) {
		authUser = (void *) ((uintptr_t) inPlist + sizeof(*inPlist));
		authPass = (void *) ((uintptr_t) authUser + sizeof(*authUser) +
			   strlen(zvm->authUser));
		image    = (void *) ((uintptr_t) authPass + sizeof(*authPass) + 
			   strlen(zvm->authPass));
		inPlist->lPlist = lInPlist - sizeof(inPlist->lPlist);
		inPlist->lFName = sizeof(inPlist->fName);
		memcpy(inPlist->fName, Image_Activate, sizeof(inPlist->fName));
		authUser->lAuthUser = strlen(zvm->authUser);
		memcpy(authUser->userId, zvm->authUser, strlen(zvm->authUser));
		authPass->lAuthPass = strlen(zvm->authPass);
		memcpy(authPass->password, zvm->authPass, strlen(zvm->authPass));
		image->lTarget = strlen(zvm->target);
		memcpy(image->target, zvm->target, strlen(zvm->target));
		if ((rc = zvm_smapi_send(zvm, inPlist, &reqId, lInPlist)) != -1) {
			if ((rc = zvm_smapi_recv(zvm, &pOut, &lRsp)) != -1) {
				outPlist = pOut;
				if (outPlist->hdr.rc == 0) {
					syslog(LOG_INFO, "Activation of %s successful",
					       zvm->target);
					rc = 0;
				} else {
					if ((outPlist->hdr.rc == RCERR_IMAGEOP) &
					     (outPlist->hdr.reason == RS_ALREADY_ACTIVE)) {
						syslog(LOG_INFO, "Activation of %s successful",
						       zvm->target);
						rc = 0;
					} else {
						rc = outPlist->hdr.rc;
						zvm->reason = outPlist->hdr.reason;
						(void) zvm_smapi_reportError(inPlist, outPlist);
					}
				}
			}
		}
		free(inPlist);
		free(outPlist);
	} else {
		syslog(LOG_ERR, "%s - cannot allocate parameter list", __func__);
		rc = -1;
	}
	return(rc);
}

/**
 * zvm_smapi_imageQuery
 * @zvm: z/VM driver information
 *
 * Queries the state of a virtual image
 */
int
zvm_smapi_imageQuery(zvm_driver_t *zvm)
{
	struct _inPlist {
		int32_t	lPlist;
		int32_t	lFName;
		char	fName[18];
		int32_t lUser;
		int32_t lPass;
		int32_t	lTarget;
		char	target[0];
	} __attribute__ ((__packed__)) *inPlist;
	int32_t	lInPlist;
	struct	_outPlist {
		smapiOutHeader_t hdr;
		int32_t	lNames;
		char	nameArray[0];
	} *outPlist = NULL;
	void	*pOut = NULL;
	int32_t	lRsp;
	uint32_t reqId;
	int	rc;

	/*
	 * Implement any delay
	 */ 
	if (zvm->delay > 0) 
		sleep(zvm->delay);

	lInPlist = sizeof(*inPlist) + strlen(zvm->target);
	inPlist = malloc(lInPlist);
	if (inPlist != NULL) {
		inPlist->lPlist = lInPlist - sizeof(inPlist->lPlist);
		inPlist->lFName = sizeof(inPlist->fName);
		memcpy(inPlist->fName, Image_Status_Query, sizeof(inPlist->fName));
		inPlist->lUser = inPlist->lPass = 0;
		inPlist->lTarget = strlen(zvm->target);
		memcpy(inPlist->target, zvm->target, inPlist->lTarget);
		if ((rc = zvm_smapi_send(zvm, inPlist, &reqId, lInPlist)) != -1) {
			if ((rc = zvm_smapi_recv(zvm, &pOut, &lRsp)) != -1) {
				outPlist = pOut;
				if (outPlist->hdr.rc == 0) {
					if (outPlist->hdr.reason == 0) {
						syslog(LOG_INFO, "Node %s is active",
						       zvm->target);
						rc = 0;
					} else { 
						syslog(LOG_INFO, "Node %s is inactive",
						       zvm->target);
						rc = 2;
					}
				} else {
					rc = 1;
					zvm->reason = outPlist->hdr.reason;
					(void) zvm_smapi_reportError(inPlist, outPlist);
				}
			}
		}
		free(inPlist);
		free(outPlist);
	} else {
		syslog(LOG_ERR, "%s - cannot allocate parameter list", __func__);
		rc = -1;
	}
	return(rc);
}

/**
 * zvm_smapi_send:
 * @zvm: z/VM driver information
 * @reqid: Returned request id
 * @req: Request parameter list
 * @lSend: Length of request
 *
 * Send a request to the SMAPI server and retrieve the request id
 */
int
zvm_smapi_send(zvm_driver_t *zvm, void *req, uint32_t *reqId, int32_t lSend)
{
	int	rc,
		nFds;
	fd_set	readFds;
	struct timeval timeout;

	timeout.tv_sec = 30;
	timeout.tv_usec = 0;
	zvm->reason = -1;
	if ((rc = zvm_smapi_open(zvm)) == 0) {
		rc = send(zvm->sd,req,lSend,0);
		if (rc != -1) {
			FD_ZERO(&readFds);
			FD_SET(zvm->sd,&readFds);
			nFds = zvm->sd + 1; 

			if ((rc = select(nFds,&readFds,NULL,NULL,&timeout)) != -1) {
				/*
				 * Get request ID
				 */ 
				rc = recv(zvm->sd,reqId,sizeof(*reqId),0);
				if (rc == -1)
					syslog(LOG_ERR, "Error receiving from SMAPI - %m");
			}
		} else 
			syslog(LOG_ERR, "Error sending to SMAPI - %m");
	}
	return(rc);
}

/**
 * zvm_smapi_recv:
 * @zvm: z/VM driver information
 * @req: Returned response parameter list
 * @lRsp: Length of response
 *
 * Receive a response from the SMAPI server
 */
int
zvm_smapi_recv(zvm_driver_t *zvm, void **rsp, int32_t *lRsp)
{
	int	rc,
		lRem = 0,
		nFds;
	void	*pRecv = rsp;
	fd_set	readFds;
	smapiOutHeader_t *out;
	struct timeval timeout;

	timeout.tv_sec = 30;
	timeout.tv_usec = 0;
	FD_ZERO(&readFds);
	FD_SET(zvm->sd,&readFds);
	nFds = zvm->sd + 1; 

	zvm->reason = -1;
	if ((rc = select(nFds,&readFds,NULL,NULL,&timeout)) != -1) {
	/*
	 * Get response length
	 */ 
	if ((rc = recv(zvm->sd,lRsp,sizeof(*lRsp),0)) != -1) {
		*lRsp = ntohl(*lRsp);
		lRem  = *lRsp;
		if (*rsp == NULL) 
			*rsp = malloc(*lRsp + sizeof(out->outLen));
		out = *rsp;
		out->outLen = *lRsp;
		pRecv = &out->reqId;
		while (lRem > 0) {
			if ((rc = recv(zvm->sd,pRecv,lRem,0)) != -1) {
				lRem -= rc;
				pRecv = (void *) ((uintptr_t) pRecv + rc);
			} else 
				syslog(LOG_ERR, "Error receiving from SMAPI - %m");
				(void) zvm_smapi_close(zvm);
				return(rc);
			}
			zvm->reason = out->reason;
		}
	} else 
		syslog(LOG_ERR, "Error receiving from SMAPI - %m");

	(void) zvm_smapi_close(zvm);

	return(rc);
}

/**
 * zvm_smapi_close:
 * @zvm: z/VM driver information
 *
 * Close a connection with the z/VM SMAPI server
 */
int
zvm_smapi_close(zvm_driver_t *zvm)
{
	close(zvm->sd);
	return(0);
}

/**
 * zvm_smapi_reportError
 * @inHdr - Input parameter list header
 * @outHdr - Output parameter list header
 *
 * Report an error from the SMAPI server
 */
static int
zvm_smapi_reportError(void *inHdr, void *oHdr)
{
	struct _inParm {
		int32_t	lPlist;
		int32_t	lFName;
		char	fName[0];
	} *inParm = inHdr;
	smapiOutHeader_t *outHdr = oHdr;
	char	fName[64];

	memset(fName, 0, sizeof(fName));
	memcpy(fName, inParm->fName, inParm->lFName);
	syslog(LOG_ERR, "%s - returned (%d,%d)", 
		fName, ntohl(outHdr->rc), ntohl(outHdr->reason));
	return(-1);
}


/**
 * trim - Trim spaces from string
 * @str - Pointer to string
 *
 */
static int
trim(char *str)
{
	char *p;
	int len;

	if (!str) 
		return (0);

	len = strlen (str);

	while (len--) {
		if (isspace (str[len])) {
			str[len] = 0;
		} else {
			break;
		}
	}

	for (p = str; *p && isspace (*p); p++);

	memmove(str, p, strlen (p) + 1);

	return (strlen (str));
}

/**
 * get_options_stdin - get options from stdin
 * @zvm - Pointer to driver information
 *
 */
static int
get_options_stdin (zvm_driver_t *zvm)
{
	char	buf[1024],
		*endPtr,
		*opt,
		*arg;
	int32_t lSrvName,
		lTarget;
	int	fence = ACT_OFFON;

	while (fgets (buf, sizeof (buf), stdin) != 0) {
		if (trim(buf) == 0) {
			continue;
		}
		if (buf[0] == '#') {
			continue;
		}

		opt = buf;

		if ((arg = strchr(opt, '=')) != 0) {
			*arg = 0;
			arg++;
		} else {
			continue;
		}

		if (trim(arg) == 0)
			continue;

		if (!strcasecmp (opt, "action")) {
			if (strcasecmp(arg, "reboot") == 0) {
				fence = ACT_OFFON;
			} else if (strcasecmp(arg, "off") == 0) {
				fence = ACT_OFF;
			} else if (strcasecmp(arg, "on") == 0) {
				fence = ACT_ON;
			} else if (strcasecmp(arg, "metadata") == 0) {
				fence = ACT_METADATA;
			} else if (strcasecmp(arg, "status") == 0) {
				fence = ACT_STATUS;
			} else if (strcasecmp(arg, "monitor") == 0) {
				fence = ACT_MONITOR;
			} else if (strcasecmp(arg, "list") == 0) {
				fence = ACT_LIST;
			} else {
				fence = ACT_HELP;
			}
		} else if (!strcasecmp (opt, "ipaddr")) {
			lSrvName = MIN(strlen(arg), sizeof(zvm->smapiSrv)-1);
			memcpy(zvm->smapiSrv, arg, lSrvName);
			continue;
		} else if (!strcasecmp (opt, "login")) {
			lSrvName = MIN(strlen(arg), sizeof(zvm->authUser)-1);
			memcpy(zvm->authUser, arg, lSrvName);
			continue;
		} else if (!strcasecmp (opt, "passwd")) {
			lSrvName = MIN(strlen(arg), sizeof(zvm->authPass)-1);
			memcpy(zvm->authPass, arg, lSrvName);
			continue;
		} else if (!strcasecmp (opt, "port")) {
			lTarget = MIN(strlen(arg), sizeof(zvm->target)-1);
			strncpy(zvm->target, arg, lTarget);
			continue;
		} if (!strcasecmp (opt, "timeout")) {
			zvm->timeOut = strtoul(arg, &endPtr, 10);
			if (*endPtr != 0) {
				syslog(LOG_WARNING, "Invalid timeout value specified %s "
				       "defaulting to %d", 
				       arg, DEFAULT_TIMEOUT);
				zvm->timeOut = DEFAULT_TIMEOUT;
			}
		} else if (!strcasecmp (opt, "help")) {
			fence = ACT_HELP;
		}
	}
	return(fence);
}

/**
 * get_options - get options from the command line
 * @argc - Count of arguments
 * @argv - Array of character strings
 * @zvm - Pointer to driver information
 *
 */
static int
get_options(int argc, char **argv, zvm_driver_t *zvm)
{
	int	c,
		fence = ACT_OFFON;
	int32_t	lSrvName,
		lTarget;
	char	*endPtr;

	while ((c = getopt_long(argc, argv, optString, longopts, NULL)) != -1) {
		switch (c) {
		case 'a' :
			lSrvName = MIN(strlen(optarg), sizeof(zvm->smapiSrv)-1);
			memcpy(zvm->smapiSrv, optarg, lSrvName);
			break;
		case 'n' :
			lTarget = MIN(strlen(optarg), sizeof(zvm->target)-1);
			memcpy(zvm->target, optarg, lTarget);
			break;
		case 'o' :
			if (strcasecmp(optarg, "reboot") == 0) {
				fence = ACT_OFFON;
			} else if (strcasecmp(optarg, "off") == 0) {
				fence = ACT_OFF;
			} else if (strcasecmp(optarg, "on") == 0) {
				fence = ACT_ON;
			} else if (strcasecmp(optarg, "metadata") == 0) {
				fence = ACT_METADATA;
			} else if (strcasecmp(optarg, "status") == 0) {
				fence = ACT_STATUS;
			} else if (strcasecmp(optarg, "monitor") == 0) {
				fence = ACT_MONITOR;
			} else if (strcasecmp(optarg, "list") == 0) {
				fence = ACT_LIST;
			} else {
				fence = ACT_HELP;
			}
			break;
		case 'p' :
			lSrvName = MIN(strlen(optarg), 8);
			memcpy(zvm->authPass, optarg, lSrvName);
			break;
		case 'u' :
			lSrvName = MIN(strlen(optarg), 8);
			memcpy(zvm->authUser, optarg, lSrvName);
			break;
		case 't' :
			zvm->timeOut = strtoul(optarg, &endPtr, 10);
			if (*endPtr != 0) {
				syslog(LOG_WARNING, "Invalid timeout value specified: %s - "
				       "defaulting to %d", 
				       optarg, DEFAULT_TIMEOUT);
				zvm->timeOut = DEFAULT_TIMEOUT;
			}
			break;
		case 'd' :
			zvm->delay = strtoul(optarg, &endPtr, 10);
			if (*endPtr != 0) {
				syslog(LOG_WARNING, "Invalid delay value specified: %s - "
				       "defaulting to %d", 
				       optarg, DEFAULT_DELAY);
				zvm->delay = DEFAULT_DELAY;
			}
			break;
		default :
			fence = ACT_HELP;
		}
	}
	return(fence);
}

/**
 * zvm_metadata - Show fence metadata 
 * @self - Path to this executable
 *
 */
static int
zvm_metadata()
{
	fprintf (stdout, "<?xml version=\"1.0\" ?>\n");
	fprintf (stdout, "<resource-agent name=\"fence_zvmip\"");
	fprintf (stdout, " shortdesc=\"Fence agent for use with z/VM Virtual Machines\">\n");
	fprintf (stdout, "<longdesc>");
	fprintf (stdout, "The fence_zvm agent is intended to be used with with z/VM SMAPI service via TCP/IP");
	fprintf (stdout, "</longdesc>\n");
	fprintf (stdout, "<vendor-url>http://www.ibm.com</vendor-url>\n");

	fprintf (stdout, "<parameters>\n");

	fprintf (stdout, "\t<parameter name=\"port\" unique=\"1\" required=\"1\">\n");
	fprintf (stdout, "\t\t<getopt mixed=\"-n, --plug\" />\n");
	fprintf (stdout, "\t\t<content type=\"string\" />\n");
	fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
	     "Name of the Virtual Machine to be fenced");
	fprintf (stdout, "\t</parameter>\n");

	fprintf (stdout, "\t<parameter name=\"ipaddr\" unique=\"1\" required=\"1\">\n");
	fprintf (stdout, "\t\t<getopt mixed=\"-i, --ip\" />\n");
	fprintf (stdout, "\t\t<content type=\"string\" />\n");
	fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
	     "IP Name or Address of SMAPI Server");
	fprintf (stdout, "\t</parameter>\n");

	fprintf (stdout, "\t<parameter name=\"login\" unique=\"1\" required=\"1\">\n");
	fprintf (stdout, "\t\t<getopt mixed=\"-u, --username\" />\n");
	fprintf (stdout, "\t\t<content type=\"string\" />\n");
	fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
	     "Name of authorized SMAPI user");
	fprintf (stdout, "\t</parameter>\n");

	fprintf (stdout, "\t<parameter name=\"passwd\" unique=\"1\" required=\"1\">\n");
	fprintf (stdout, "\t\t<getopt mixed=\"-p, --password\" />\n");
	fprintf (stdout, "\t\t<content type=\"string\" />\n");
	fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
	     "Password of authorized SMAPI user");
	fprintf (stdout, "\t</parameter>\n");

	fprintf (stdout, "\t<parameter name=\"action\" unique=\"1\" required=\"0\">\n");
	fprintf (stdout, "\t\t<getopt mixed=\"-o, --action\" />\n");
	fprintf (stdout, "\t\t<content type=\"string\" default=\"off\" />\n");
	fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
	     "Fencing action");
	fprintf (stdout, "\t</parameter>\n");

	fprintf (stdout, "\t<parameter name=\"delay\" unique=\"1\" required=\"0\">\n");
	fprintf (stdout, "\t\t<getopt mixed=\"--delay\" />\n");
	fprintf (stdout, "\t\t<content type=\"string\" default=\"0\" />\n");
	fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
	     "Time to delay fencing action in seconds");
	fprintf (stdout, "\t</parameter>\n");

	fprintf (stdout, "\t<parameter name=\"usage\" unique=\"1\" required=\"0\">\n");
	fprintf (stdout, "\t\t<getopt mixed=\"-h, --help\" />\n");
	fprintf (stdout, "\t\t<content type=\"boolean\" />\n");
	fprintf (stdout, "\t\t<shortdesc lang=\"en\">%s</shortdesc>\n",
	     "Print usage");
	fprintf (stdout, "\t</parameter>\n");

	fprintf (stdout, "</parameters>\n");

	fprintf (stdout, "<actions>\n");
	fprintf (stdout, "\t<action name=\"off\" />\n");
	fprintf (stdout, "\t<action name=\"on\" automatic=\"0\" />\n");
	fprintf (stdout, "\t<action name=\"list\" />\n");
	fprintf (stdout, "\t<action name=\"metadata\" />\n");
	fprintf (stdout, "\t<action name=\"monitor\" />\n");
	fprintf (stdout, "\t<action name=\"status\" />\n");
	fprintf (stdout, "\t<action name=\"reboot\" />\n");
	fprintf (stdout, "</actions>\n");

	fprintf (stdout, "</resource-agent>\n");

	return(0);

}

/**
 * usage - display command syntax and parameters
 *
 */
static int
usage()
{
	fprintf(stderr,"Usage: fence_zvmip [options]\n\n"
		"\tWhere [options] =\n"
		"\t-o --action [action] - \"off\", \"on\", \"list\", \"metadata\", "
					 "\"monitor\", \"reboot\", \"status\"\n"
		"\t--delay [seconds]    - Time to delay fencing action in seconds\n"
		"\t-n --plug [target]   - Name of virtual machine to fence\n"
		"\t-a --ip [server]     - IP Name/Address of SMAPI Server\n"
		"\t-u --username [user] - Name of autorized SMAPI user\n"
		"\t-p --password [pass] - Password of autorized SMAPI user\n"
		"\t-t --timeout [secs]  - Time to wait for fence in seconds - currently ignored\n"
		"\t-h --help            - Display this usage information\n");
	return(1);
}

/**
 * check_param - Check that mandatory parameters have been specified
 * @zvm - Pointer to driver information
 *
 */
static int
check_parm(zvm_driver_t *zvm) 
{
	int rc;

	if (zvm->smapiSrv[0] != 0) {
		if (zvm->target[0] != 0) {
			if (zvm->authUser[0] != 0) {
				if (zvm->authPass[0] != 0) {
					rc = 0;
				} else {
					syslog(LOG_ERR, "Missing authorized password");
					rc = 4;
				}	
			} else {
				syslog(LOG_ERR, "Missing authorized user name");
				rc = 3;
			}	
		} else {
			syslog(LOG_ERR, "Missing fence target name");
			rc = 2;
		}	
	} else {
		syslog(LOG_ERR, "Missing SMAPI server name");
		rc = 1;
	}	
	return(rc);
}

int
main(int argc, char **argv)
{
	zvm_driver_t	zvm;
	int	fence = 1,
		rc = 0;

	openlog ("fence_zvmip", LOG_CONS|LOG_PID, LOG_DAEMON);
	memset(&zvm, 0, sizeof(zvm));
	zvm.timeOut = DEFAULT_TIMEOUT;
	zvm.delay   = DEFAULT_DELAY;

	if (argc > 1)
		fence = get_options(argc, argv, &zvm);
	else
		fence = get_options_stdin(&zvm);

	switch(fence) {
		case ACT_OFFON :	// OFFON
			if ((rc = check_parm(&zvm)) == 0)
				rc = zvm_smapi_imageRecycle(&zvm);
			break;
		case ACT_OFF :		// OFF
			if ((rc = check_parm(&zvm)) == 0)
				rc = zvm_smapi_imageDeactivate(&zvm);
			break;
		case ACT_ON :		// ON
			if ((rc = check_parm(&zvm)) == 0)
				rc = zvm_smapi_imageActivate(&zvm);
			break;
		case ACT_METADATA :	// METADATA
			rc = zvm_metadata();
			break;
		case ACT_STATUS :	// STATUS
			if ((rc = check_parm(&zvm)) == 0)
				rc = zvm_smapi_imageQuery(&zvm);
			break;
		case ACT_MONITOR :	// MONITOR
			rc = 0;
			break;
		case ACT_LIST :
			printf("N/A");
			break;
		case ACT_HELP :
			rc = usage();
	}
	closelog();
	return (rc);
}
