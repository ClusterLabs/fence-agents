#ifndef _STATIC_MAP_H
#define _STATIC_MAP_H

typedef int (*map_load_t)(void *config, void **perm_info);
typedef int (*map_check_t)(void *info, const char *src, const char *tgt_uuid, const char *tgt_name);
typedef void (*map_cleanup_t)(void **info);

typedef struct {
	map_load_t load;
	map_check_t check;
	map_cleanup_t cleanup;
	void *info;
} map_object_t;

/*
 * These macros may be called from within a loadable module
 */
#define map_load(obj, config) \
	obj->load(config, &obj->info)
#define map_check(obj, src, tgt_uuid) \
	obj->check(obj->info, src, tgt_uuid, NULL)
#define map_check2(obj, src, tgt_uuid, tgt_name) \
	obj->check(obj->info, src, tgt_uuid, tgt_name)
#define map_free(obj) \
	obj->cleanup(obj->info)

/* Returns a copy of our simple config object */
void *map_init(void);

/* Frees a previously-allocated copy of our simple config object */
void map_release(void *c);


#endif
