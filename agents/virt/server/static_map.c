#include "config.h"

#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>

#include "simpleconfig.h"
#include "static_map.h"
#include "list.h"
#include "debug.h"
#include "serial.h"
#include "uuid-test.h"

struct perm_entry {
	list_head();
	char name[129];
};

struct perm_group {
	list_head();
	struct perm_entry *uuids;
	struct perm_entry *ips;
	char name[129];
};


static void
static_map_cleanup(void **info)
{
	struct perm_group *groups = (struct perm_group *)(*info);
	struct perm_group *group;
	struct perm_entry *entry;

	while (groups) {
		group = groups;
		list_remove(&groups, group);
		while (group->uuids) {
			entry = group->uuids;
			list_remove(&group->uuids, entry);
			free(entry);
		}
		while (group->ips) {
			entry = group->ips;
			list_remove(&group->ips, entry);
			free(entry);
		}
		free(group);
	}

	*info = NULL;
}


static int
static_map_check(void *info, const char *src, const char *tgt_uuid, const char *tgt_name)
{
	struct perm_group *groups = (struct perm_group *)info;
	struct perm_group *group;
	struct perm_entry *left, *tmp;
	int x, y, uuid = 0;

	if (!info)
		return 1; /* no maps == wide open */

	dbg_printf(99, "[server:map_check] map request: src: %s uuid: %s name: %s\n", src, tgt_uuid, tgt_name);

	uuid = is_uuid(src);

	list_for(&groups, group, x) {
		left = NULL;

		if (uuid) {
			list_for(&group->uuids, tmp, y) {
				if (!strcasecmp(tmp->name, src)) {
					left = tmp;
					break;
				}
			}
		} else {
			list_for(&group->ips, tmp, y) {
				if (!strcasecmp(tmp->name, src)) {
					left = tmp;
					break;
				}
			}
		}

		if (!left)
			continue;

		list_for(&group->uuids, tmp, y) {
			if (!strcasecmp(tmp->name, tgt_uuid)) {
				return 1;
			}
			/* useful only for list */
			if (tgt_name) {
				if (!strcasecmp(tmp->name, tgt_name)) {
					return 1;
				}
			}
		}
	}

	return 0;
}


static int
static_map_load(void *config_ptr, void **perm_info)
{
	config_object_t *config = config_ptr;
	int group_idx = 0;
	int entry_idx = 0;
	int found;
	char value[128];
	char buf[256];
	char buf2[512];
	struct perm_group *group = NULL, *groups = NULL;
	struct perm_entry *entry = NULL;

	if (!perm_info)
		return -1;

	do {
		snprintf(buf, sizeof(buf)-1, "groups/group[%d]", ++group_idx);

		if (sc_get(config, buf, value, sizeof(value)) != 0) {
			snprintf(buf2, sizeof(buf2)-1, "%s/@uuid", buf);
			if (sc_get(config, buf2, value, sizeof(value)) != 0) {
				snprintf(buf2, sizeof(buf2)-1, "%s/@ip", buf);
				if (sc_get(config, buf2, value,
					   sizeof(value)) != 0) {
					break;
				}
			}
			snprintf(buf2, sizeof(buf2)-1, "%s/@name", buf);
			if (sc_get(config, buf2, value, sizeof(value)) != 0) {
				snprintf(value, sizeof(value), "unnamed-%d",
					 group_idx);
			}
		}

		group = malloc(sizeof(*group));
		assert(group);
		memset(group, 0, sizeof(*group));
		strncpy(group->name, value, sizeof(group->name));
		dbg_printf(3, "Group: %s\n", value);

		found = 0;
		entry_idx = 0;
		do {
			snprintf(buf2, sizeof(buf2)-1, "%s/@uuid[%d]",
				 buf, ++entry_idx);

			if (sc_get(config, buf2, value, sizeof(value)) != 0) {
				break;
			}

			++found;
			entry = malloc(sizeof(*entry));
			assert(entry);
			memset(entry, 0, sizeof(*entry));
			strncpy(entry->name, value, sizeof(entry->name));
			dbg_printf(3, " - UUID Entry: %s\n", value);

			list_insert(&group->uuids, entry);

		} while (1);

		entry_idx = 0;
		do {
			snprintf(buf2, sizeof(buf2)-1, "%s/@ip[%d]",
				 buf, ++entry_idx);

			if (sc_get(config, buf2, value, sizeof(value)) != 0) {
				break;
			}

			++found;
			entry = malloc(sizeof(*entry));
			assert(entry);
			memset(entry, 0, sizeof(*entry));
			strncpy(entry->name, value, sizeof(entry->name));
			dbg_printf(3, " - IP Entry: %s\n", value);

			list_insert(&group->ips, entry);

		} while (1);


		if (!found)
			free(group);
		else
			list_insert(&groups, group);

	} while (1);

	*perm_info = groups;

	return 0;
}


static const map_object_t static_map_obj = {
	.load = static_map_load,
	.check = static_map_check,
	.cleanup = static_map_cleanup,
	.info = NULL
};


void *
map_init(void)
{
	map_object_t *o;

	o = malloc(sizeof(*o));
	if (!o)
		return NULL;
	memset(o, 0, sizeof(*o));
	memcpy(o, &static_map_obj, sizeof(*o));

	return (void *)o;
}


void
map_release(void *c)
{
	map_object_t *o = (map_object_t *)c;

	static_map_cleanup(&o->info);
	free(c);
}
