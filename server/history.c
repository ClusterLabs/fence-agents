#include "config.h"

#include <stdio.h>
#include <malloc.h>
#include <sys/types.h>
#include <errno.h>
#include <string.h>
#include <list.h>
#include <time.h>

#include "history.h"

history_info_t *
history_init(history_compare_fn func, time_t expiration, size_t element_size)
{
	history_info_t *hist;

	errno = EINVAL;
	if (!func || !expiration || !element_size)
		return NULL;

	hist = malloc(sizeof(*hist));
	if (!hist)
		return NULL;
	memset(hist, 0, sizeof(*hist));

	hist->timeout = expiration;
	hist->element_size = element_size;
	hist->compare_func = func;

	return hist;
}


/*
 * Purge our history when the entries time out.
 *
 * Returns 1 if a matching history node was found, or 0
 * if not. 
 */
int
history_check(history_info_t *hinfo, void *stuff)
{
	history_node *entry = NULL;
	time_t now;
	int x;

	if (!hinfo)
		return 0; /* XXX */

	if (!hinfo->hist)
		return 0;

	now = time(NULL);

loop_again:
	list_for((&hinfo->hist), entry, x) {
		if (entry->when < (now - hinfo->timeout)) {
			list_remove((&hinfo->hist), entry);
			free(entry->data);
			free(entry);
			goto loop_again;
		}

		if (hinfo->compare_func(entry->data, stuff)) {
			return 1;
		}
	}
	return 0;
}


int
history_record(history_info_t *hinfo, void *data)
{
	history_node *entry = NULL;

	errno = EINVAL;
	if (!data || !hinfo)
		return -1;

	if (history_check(hinfo, data) == 1) {
		errno = EEXIST;
		return -1;
	}

	entry = malloc(sizeof(*entry));
	if (!entry) {
		return -1;
	}
	memset(entry, 0, sizeof(*entry));

	entry->data = malloc(hinfo->element_size);
	if (!entry->data) {
		free(entry);
		errno = ENOMEM;
		return -1;
	}

	memcpy(entry->data, data, hinfo->element_size);
	entry->when = time(NULL);
	list_insert((&hinfo->hist), entry);
	return 0;
}


int
history_wipe(history_info_t *hinfo)
{
	history_node *entry = NULL;

	if (!hinfo)
		return -1;

	while (hinfo->hist) {
		entry = hinfo->hist;
		list_remove((&hinfo->hist), entry);
		free(entry->data);
		free(entry);
	}

	/* User must free(hinfo); */
	return 0;
}
