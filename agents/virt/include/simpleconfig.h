#ifndef _SIMPLECONFIG_H
#define _SIMPLECONFIG_H

typedef int (*config_get_t)(void *config, const char *key,
			    char *value, size_t valuesz);
typedef int (*config_set_t)(void *config, const char *key,
			    const char *value);
typedef int (*config_parse_t)(const char *filename, void **config);
typedef int (*config_free_t)(void *config);
typedef void (*config_dump_t)(void *config, FILE *fp);

/*
 * We use an abstract object here so we do not have to link loadable
 * modules against the configuration library.
 */

typedef struct {
	config_get_t get;
	config_set_t set;
	config_parse_t parse;
	config_free_t free;
	config_dump_t dump;
	void *info;
} config_object_t;

/*
 * These macros may be called from within a loadable module
 */
#define sc_get(obj, key, value, valuesz) \
	obj->get(obj->info, key, value, valuesz)
#define sc_set(obj, key, value) \
	obj->set(obj->info, key, value)
#define sc_parse(obj, filename) \
	obj->parse(filename, &obj->info)
#define sc_free(obj) \
	obj->free(obj->info)
#define sc_dump(obj, fp) \
	obj->dump(obj->info, fp)

/*
 * Do not call the below functions from loadable modules.  Doing so 
 * requires linking the configuration library in to the modules, which
 * is what we want to avoid.
 */

/* Returns a copy of our simple config object */
config_object_t *sc_init(void);

/* Frees a previously-allocated copy of our simple config object */
void sc_release(config_object_t *c);

int check_file_permissions(const char *fname);

int do_configure(config_object_t *config, const char *filename);

#endif
