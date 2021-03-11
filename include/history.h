#ifndef _HISTORY_H
#define _HISTORY_H

typedef struct _history_node {
	list_head();
	void *data;
	time_t when;
} history_node;

typedef int (*history_compare_fn)(void *, void *);

typedef struct _history_info {
	history_node *hist;
	history_compare_fn compare_func;
	time_t timeout;
	size_t element_size;
} history_info_t;

history_info_t *history_init(history_compare_fn func,
			     time_t expiration, size_t element_size);
int history_check(history_info_t *hinfo, void *stuff);
int history_record(history_info_t *hinfo, void *data);
int history_wipe(history_info_t *hinfo);

#endif
