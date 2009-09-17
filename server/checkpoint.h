#ifndef _CHECKPOINT_H
#define _CHECKPOINT_H

struct ckpt_fence_req {
	char vm_name[128];
	int request;
	uint32_t seqno;
	uint32_t response;
};

typedef void (*request_callback_fn)(void *data, size_t len, uint32_t nodeid,
	      uint32_t seqno);

int cpg_get_ids(uint32_t *me, uint32_t *high);
int cpg_start(const char *name, request_callback_fn func);
int cpg_stop(void);
int cpg_send_req(void *data, size_t len, uint32_t *seqno);
int cpg_wait_reply(void **data, size_t *len, uint32_t seqno);
int cpg_send_reply(void *data, size_t len, uint32_t nodeid, uint32_t seqno);

#endif
