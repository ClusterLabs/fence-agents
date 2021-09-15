/*
  Copyright Red Hat, Inc. 2006

  This program is free software; you can redistribute it and/or modify it
  under the terms of the GNU General Public License as published by the
  Free Software Foundation; either version 2, or (at your option) any
  later version.

  This program is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; see the file COPYING.  If not, write to the
  Free Software Foundation, Inc.,  675 Mass Ave, Cambridge, 
  MA 02139, USA.
*/

#include "config.h"

#include <sys/types.h>
#include <string.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sechash.h>
#include <fcntl.h>
#include <stdio.h>
#include <errno.h>

/* Local includes */
#include "xvm.h"
#include "fdops.h"
#include "simple_auth.h"
#include "debug.h"


static void
print_hash(unsigned char *hash, size_t hashlen)
{
	int x; 

	for (x = 0; x < hashlen; x++)
		printf("%02x", (hash[x]&0xff));
}


static int
sha_sign(fence_req_t *req, void *key, size_t key_len)
{
	unsigned char hash[SHA512_LENGTH];
	HASHContext *h;
	HASH_HashType ht;
	unsigned int rlen;
	int devrand;
	int ret;

	switch(req->hashtype) {
		case HASH_SHA1:
			ht = HASH_AlgSHA1;
			break;
		case HASH_SHA256:
			ht = HASH_AlgSHA256;
			break;
		case HASH_SHA512:
			ht = HASH_AlgSHA512;
			break;
		default:
			dbg_printf(1, "Unknown hash type: %d\n", req->hashtype);
			return -1;
	}

	dbg_printf(4, "Opening /dev/urandom\n");
	devrand = open("/dev/urandom", O_RDONLY);
	if (devrand < 0) {
		dbg_printf(1, "Error: open: /dev/urandom: %s", strerror(errno));
		return -1;
	}

	ret = _read_retry(devrand, req->random, sizeof(req->random), NULL);
	if (ret <= 0) {
		dbg_printf(1, "Error: read: /dev/urandom: %s", strerror(errno));
		close(devrand);
		return -1;
	}
	close(devrand);

	memset(hash, 0, sizeof(hash));
	h = HASH_Create(ht);
	if (!h)
		return -1;

	HASH_Begin(h);
	HASH_Update(h, key, key_len);
	HASH_Update(h, (void *)req, sizeof(*req));
	HASH_End(h, hash, &rlen, sizeof(hash));
	HASH_Destroy(h);

	memcpy(req->hash, hash, sizeof(req->hash));
	return 0;
}


static int
sha_verify(fence_req_t *req, void *key, size_t key_len)
{
	unsigned char hash[SHA512_LENGTH];
	unsigned char pkt_hash[SHA512_LENGTH];
	HASHContext *h = NULL;
	HASH_HashType ht;
	unsigned int rlen;
	int ret;

	switch(req->hashtype) {
		case HASH_SHA1:
			ht = HASH_AlgSHA1;
			break;
		case HASH_SHA256:
			ht = HASH_AlgSHA256;
			break;
		case HASH_SHA512:
			ht = HASH_AlgSHA512;
			break;
		default:
			dbg_printf(3, "%s: no-op (HASH_NONE)\n", __FUNCTION__);
			return 0;
	}

	if (!key || !key_len) {
		dbg_printf(3, "%s: Hashing requested when we have no key data\n",
			   __FUNCTION__);
		return 0;
	}

	memset(hash, 0, sizeof(hash));
	h = HASH_Create(ht);
	if (!h)
		return 0;

	memcpy(pkt_hash, req->hash, sizeof(pkt_hash));
	memset(req->hash, 0, sizeof(req->hash));

	HASH_Begin(h);
	HASH_Update(h, key, key_len);
	HASH_Update(h, (void *)req, sizeof(*req));
	HASH_End(h, hash, &rlen, sizeof(hash));
	HASH_Destroy(h);

	memcpy(req->hash, pkt_hash, sizeof(req->hash));

	ret = !memcmp(hash, pkt_hash, sizeof(hash));
	if (!ret) {
		printf("Hash mismatch:\nPKT = ");
		print_hash(pkt_hash, sizeof(pkt_hash));
		printf("\nEXP = ");
		print_hash(hash, sizeof(hash));
		printf("\n");
	}

	return ret;
}


int
sign_request(fence_req_t *req, void *key, size_t key_len)
{
	memset(req->hash, 0, sizeof(req->hash));
	switch(req->hashtype) {
	case HASH_NONE:
		dbg_printf(3, "%s: no-op (HASH_NONE)\n", __FUNCTION__);
		return 0;
	case HASH_SHA1:
	case HASH_SHA256:
	case HASH_SHA512:
		return sha_sign(req, key, key_len);
	default:
		break;
	}
	return -1;
}


int
verify_request(fence_req_t *req, fence_hash_t min,
	       void *key, size_t key_len)
{
	if (req->hashtype < min) {
		printf("Hash type not strong enough (%d < %d)\n",
		       req->hashtype, min);
		return 0;
	}
	switch(req->hashtype) {
	case HASH_NONE:
		return 1;
	case HASH_SHA1:
	case HASH_SHA256:
	case HASH_SHA512:
		return sha_verify(req, key, key_len);
	default:
		break;
	}
	return 0;
}


static int
sha_challenge(int fd, fence_auth_type_t auth, void *key,
	      size_t key_len, int timeout)
{
	fd_set rfds;
	struct timeval tv;
	unsigned char hash[MAX_HASH_LENGTH];
	unsigned char challenge[MAX_HASH_LENGTH];
	unsigned char response[MAX_HASH_LENGTH];
	int devrand;
	int ret;
	HASHContext *h;
	HASH_HashType ht;
	unsigned int rlen;

	devrand = open("/dev/urandom", O_RDONLY);
	if (devrand < 0) {
		dbg_printf(1, "Error: open /dev/urandom: %s", strerror(errno));
		return 0;
	}

	tv.tv_sec = timeout;
	tv.tv_usec = 0;
	ret = _read_retry(devrand, challenge, sizeof(challenge), &tv);
	if (ret < 0) {
		dbg_printf(1, "Error: read: /dev/urandom: %s", strerror(errno));
		close(devrand);
		return 0;
	}
	close(devrand);

	tv.tv_sec = timeout;
	tv.tv_usec = 0;
	ret = _write_retry(fd, challenge, sizeof(challenge), &tv);
	if (ret < 0) {
		dbg_printf(2, "Error: write: %s", strerror(errno));
		return 0;
	}

	switch(auth) {
		case HASH_SHA1:
			ht = HASH_AlgSHA1;
			break;
		case HASH_SHA256:
			ht = HASH_AlgSHA256;
			break;
		case HASH_SHA512:
			ht = HASH_AlgSHA512;
			break;
		default:
			return 0;
	}

	memset(hash, 0, sizeof(hash));
	h = HASH_Create(ht);
	if (!h)
		return 0;

	HASH_Begin(h);
	HASH_Update(h, key, key_len);
	HASH_Update(h, challenge, sizeof(challenge));
	HASH_End(h, hash, &rlen, sizeof(hash));
	HASH_Destroy(h);

	memset(response, 0, sizeof(response));

	FD_ZERO(&rfds);
	FD_SET(fd, &rfds);

	tv.tv_sec = timeout;
	tv.tv_usec = 0;
	if (_select_retry(fd + 1, &rfds, NULL, NULL, &tv) <= 0) {
		dbg_printf(0, "Error: select: %s\n", strerror(errno));
		return 0;
	}

	tv.tv_sec = timeout;
	tv.tv_usec = 0;
	ret = _read_retry(fd, response, sizeof(response), &tv);
	if (ret < 0) {
		dbg_printf(0, "Error reading challenge response: %s", strerror(errno));
		return 0;
	} else if (ret < sizeof(response)) {
		dbg_printf(0,
			"read data from socket is too short(actual: %d, expected: %zu)\n",
			ret, sizeof(response));
		return 0;
	}

	ret = !memcmp(response, hash, sizeof(response));
	if (!ret) {
		printf("Hash mismatch:\nC = ");
		print_hash(challenge, sizeof(challenge));
		printf("\nH = ");
		print_hash(hash, sizeof(hash));
		printf("\nR = ");
		print_hash(response, sizeof(response));
		printf("\n");
	}

	return ret;
}


static int
sha_response(int fd, fence_auth_type_t auth, void *key,
	     size_t key_len, int timeout)
{
	fd_set rfds;
	struct timeval tv;
	unsigned char challenge[MAX_HASH_LENGTH];
	unsigned char hash[MAX_HASH_LENGTH];
	HASHContext *h;
	HASH_HashType ht;
	unsigned int rlen;
	int ret;

	FD_ZERO(&rfds);
	FD_SET(fd, &rfds);

	tv.tv_sec = timeout;
	tv.tv_usec = 0;
	if (_select_retry(fd + 1, &rfds, NULL, NULL, &tv) <= 0) {
		dbg_printf(2, "Error: select: %s\n", strerror(errno));
		return 0;
	}

	tv.tv_sec = timeout;
	tv.tv_usec = 0;
	if (_read_retry(fd, challenge, sizeof(challenge), &tv) < 0) {
		dbg_printf(2, "Error reading challenge hash: %s\n", strerror(errno));
		return 0;
	}

	switch(auth) {
		case AUTH_SHA1:
			ht = HASH_AlgSHA1;
			break;
		case AUTH_SHA256:
			ht = HASH_AlgSHA256;
			break;
		case AUTH_SHA512:
			ht = HASH_AlgSHA512;
			break;
		default:
			dbg_printf(3, "%s: no-op (AUTH_NONE)\n", __FUNCTION__);
			return 0;
	}

	memset(hash, 0, sizeof(hash));
	h = HASH_Create(ht); /* */
	if (!h)
		return 0;

	HASH_Begin(h);
	HASH_Update(h, key, key_len);
	HASH_Update(h, challenge, sizeof(challenge));
	HASH_End(h, hash, &rlen, sizeof(hash));
	HASH_Destroy(h);

	tv.tv_sec = timeout;
	tv.tv_usec = 0;
	ret = _write_retry(fd, hash, sizeof(hash), &tv);
	if (ret < 0) {
		perror("write");
		return 0;
	} else if (ret < sizeof(hash)) {
		dbg_printf(2,
			"Only part of hash is written(actual: %d, expected: %zu)\n",
			ret,
			sizeof(hash));
		return 0;
	}

	return 1;
}


int
sock_challenge(int fd, fence_auth_type_t auth, void *key, size_t key_len,
	      int timeout)
{
	switch(auth) {
	case AUTH_NONE:
		dbg_printf(3, "%s: no-op (AUTH_NONE)\n", __FUNCTION__);
		return 1;
	case AUTH_SHA1:
	case AUTH_SHA256:
	case AUTH_SHA512:
		return sha_challenge(fd, auth, key, key_len, timeout);
	default:
		break;
	}
	return -1;
}


int
sock_response(int fd, fence_auth_type_t auth, void *key, size_t key_len,
	     int timeout)
{
	switch(auth) {
	case AUTH_NONE:
		dbg_printf(3, "%s: no-op (AUTH_NONE)\n", __FUNCTION__);
		return 1;
	case AUTH_SHA1:
	case AUTH_SHA256:
	case AUTH_SHA512:
		return sha_response(fd, auth, key, key_len, timeout);
	default:
		break;
	}
	return -1;
}


int
read_key_file(char *file, char *key, size_t max_len)
{
	int fd;
	int nread, remain = max_len;
	char *p;

	dbg_printf(3, "Reading in key file %s into %p (%d max size)\n",
		file, key, (int)max_len);
	fd = open(file, O_RDONLY);
	if (fd < 0) {
		dbg_printf(2, "Error opening key file: %s\n", strerror(errno));
		return -1;
	}

	memset(key, 0, max_len);
	p = key;
	remain = max_len;

	while (remain) {
		nread = read(fd, p, remain);
		if (nread < 0) {
			if (errno == EINTR)
				continue;
			dbg_printf(2, "Error from read: %s\n", strerror(errno));
			close(fd);
			return -1;
		}

		if (nread == 0) {
			dbg_printf(3, "Stopped reading @ %d bytes\n",
				(int)max_len-remain);
			break;
		}
		
		p += nread;
		remain -= nread;
	}

	close(fd);	
	dbg_printf(3, "Actual key length = %d bytes\n", (int)max_len-remain);
	
	return (int)(max_len - remain);
}
