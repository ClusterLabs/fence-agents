#ifndef __FENCE_VIRTD_CPG_H
#define __FENCE_VIRTD_CPG_H

struct cpg_fence_req {
	char vm_name[128];
	int request;
	uint32_t seqno;
	uint32_t response;
};

typedef void (*request_callback_fn)(void *data, size_t len, uint32_t nodeid,
	      uint32_t seqno);
typedef void (*confchange_callback_fn)(const struct cpg_address *m, size_t len);

int cpg_start(	const char *name,
				request_callback_fn func,
				request_callback_fn store_func,
				confchange_callback_fn join,
				confchange_callback_fn leave);

int cpg_get_ids(uint32_t *me, uint32_t *high);
int cpg_stop(void);
int cpg_send_req(void *data, size_t len, uint32_t *seqno);
int cpg_wait_reply(void **data, size_t *len, uint32_t seqno);
int cpg_send_reply(void *data, size_t len, uint32_t nodeid, uint32_t seqno);
int cpg_send_vm_state(virt_state_t *vs);


#endif
