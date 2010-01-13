#include <stdio.h>
#include <simpleconfig.h>
#include <string.h>
#include <signal.h>
#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
#include <list.h>
#include <debug.h>

struct perm_entry {
	list_head();
	char name[128];
};

struct perm_group {
	list_head();
	struct perm_entry *entries;
	char name[128];
};


void
static_map_cleanup(void *info)
{
	struct perm_group *groups = (struct perm_group *)info;
	struct perm_group *group;
	struct perm_entry *entry;

	while (groups) {
		group = groups;
		list_remove(&groups, group);
		while (group->entries) {
			entry = group->entries;
			list_remove(&group->entries, entry);
			free(entry);
		}
		free(group);
	}
}


int
static_map_check(void *info, const char *value1, const char *value2)
{
	struct perm_group *groups = (struct perm_group *)info;
	struct perm_group *group;
	struct perm_entry *left, *tmp;
	int x, y;

	if (!info)
		return 1; /* no maps == wide open */

	list_for(&groups, group, x) {
		left = NULL;

		list_for(&group->entries, tmp, y) {
			if (!strcasecmp(tmp->name, value1)) {
				left = tmp;
				break;
			}
		}

		if (!left)
			continue;

		list_for(&group->entries, tmp, y) {
			if (!strcasecmp(tmp->name, value2)) {
				return 1;
			}
		}
	}

	return 0;
}


int
static_map_init(config_object_t *config, void **perm_info)
{
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
			snprintf(buf2, sizeof(buf2)-1, "%s/@member", buf);
			if (sc_get(config, buf2, value, sizeof(value)) != 0) {
				break;
			} else {
				snprintf(value, sizeof(value), "unnamed-%d", group_idx);
			}
		}

		group = malloc(sizeof(*group));
		assert(group);
		memset(group, 0, sizeof(*group));
		strncpy(group->name, value, sizeof(group->name));
		dbg_printf(3, "Group: %s\n", value);

		entry_idx = 0;
		found = 0;
		do {
			snprintf(buf2, sizeof(buf2)-1, "%s/@member[%d]", buf, ++entry_idx);

			if (sc_get(config, buf2, value, sizeof(value)) != 0) {
				break;
			}

			++found;
			entry = malloc(sizeof(*entry));
			assert(entry);
			memset(entry, 0, sizeof(*entry));
			strncpy(entry->name, value, sizeof(entry->name));
			dbg_printf(3, " - Entry: %s\n", value);

			list_insert(&group->entries, entry);

		} while (1);

		if (!found)
			free(group);
		else
			list_insert(&groups, group);

	} while (1);

	*perm_info = groups;

	return 0;
}
