#include <stdio.h>
#include <pthread.h>
#include <string.h>
#include <malloc.h>
#include "simpleconfig.h"
#include "config-stack.h"

static pthread_mutex_t parser_mutex = PTHREAD_MUTEX_INITIALIZER;

static int
print_value(struct value *v, int depth, FILE *fp)
{
	int x;
	for (x = 0; x < depth; x++)
		fprintf(fp, "\t");
	fprintf(fp, "%s = \"%s\";\n", v->id, v->val);

	return 0;
}


static void
_sc_dump_d(struct node *node, int depth, FILE *fp) 
{
	struct node *n;
	struct value *v;
	int x;

	if (!node) {
		//printf("Empty node\n");
		return;
	}

	for (x = 0; x < depth; x++)
		fprintf(fp, "\t");
	fprintf(fp, "%s {\n", node->id);

	for (n = node->nodes; n; n = n->next) {
		_sc_dump_d(n, depth+1, fp);
	}

	for (v = node->values; v; v = v->next) {
		print_value(v, depth+1, fp);
	}

	for (x = 0; x < depth; x++)
		fprintf(fp, "\t");
	fprintf(fp, "}\n\n");
}


static void
_sc_dump(config_info_t *config, FILE *fp)
{
	struct node *n, *node;
	struct value *v, *values;

	if (!config)
		return;

	values = ((struct parser_context *)config)->val_list;
	node = ((struct parser_context *)config)->node_list;

	for (n = node; n; n = n->next) {
		_sc_dump_d(n, 0, fp);
	}

	for (v = values; v; v = v->next) {
		print_value(v, 0, fp);
	}
}


static int
free_value(struct value *v)
{
	int x;

	if (v) {
		free(v->id);
		free(v->val);
		free(v);
	}

	return 0;
}


static void
_sc_free_node(struct node *node) 
{
	struct node *n;
	struct value *v;
	int x;

	if (!node)
		return;

	while (node->nodes) {
		n = node->nodes;
		if (n) {
			node->nodes = node->nodes->next;
			_sc_free_node(n);
		}
	}

	while (node->values) {
		v = node->values;
		node->values = node->values->next;
		free_value(v);
	}

	free(node->id);
	free(node);
}


static int
_sc_free(config_info_t *config)
{
	struct node *n, *nlist;
	struct value *v, *vlist;
       
	if (!config)
		return -1;

	vlist = ((struct parser_context *)config)->val_list;
	nlist = ((struct parser_context *)config)->node_list;

	while (nlist) {
		n = nlist;
		nlist = nlist->next;
		_sc_free_node(n);
	}

	((struct parser_context *)config)->node_list = NULL;

	while (vlist) {
		v = vlist;
		vlist = vlist->next;
		free_value(v);
	}

	((struct parser_context *)config)->val_list = NULL;

	free(config);

	return 0;
}


static int
_sc_get(config_info_t *config, const char *key, char *value, size_t valuesz)
{
	char buf[1024];
	struct node *n, *node = ((struct parser_context *)config)->node_list;
	struct value *v, *values = ((struct parser_context *)config)->val_list;
	char *ptr;
	char *slash;
	int found;

	ptr = (char *)key;
	while ((slash = strchr(ptr, '/'))) {
		memset(buf, 0, sizeof(buf));
		strncpy(buf, ptr, (slash - ptr));
		ptr = ++slash;

		found = 0;

		for (n = node; n; n = n->next) {
			if (!strcasecmp(n->id, buf)) {
				node = n->nodes;
				values = n->values;
				found = 1;
				break;
			}
		}

		if (!found)
			return 1;
	}

	if (ptr[0] == '@') {
		++ptr;
		found = 0;

		for (v = values; v; v = v->next) {
			if (!strcasecmp(v->id, ptr)) {
				snprintf(value, valuesz, "%s", v->val);
				return 0;
			}
		}
	}

	return 1;
}


static int
_sc_parse(const char *filename, config_info_t **config)
{
	struct parser_context *c;
	FILE *fp = NULL;
	int ret = 0;

	if (!config)
		return -1;

	pthread_mutex_lock(&parser_mutex);
	if (filename) {
		fp = fopen(filename, "r");
		yyin = fp;
		if (!fp)
			return -1;
	}

	ret = yyparse();

	if (!ret) {
		c = malloc(sizeof(*c));
		if (!c)
			return -1;
		c->node_list = node_list;
		c->val_list = val_list;
		c->next = NULL;
		val_list = NULL;
		node_list = NULL;
		*config = (config_info_t *)c;
	}

	if (fp)
		fclose(fp);

	pthread_mutex_unlock(&parser_mutex);

	return ret;
}


static const config_object_t sc_object = {
	.get = _sc_get,
	.parse = _sc_parse,
	.free = _sc_free,
	.dump = _sc_dump,
	.info = NULL
};


config_object_t *
sc_init(void)
{
	config_object_t *o;

	o = malloc(sizeof(*o));
	if (!o)
		return NULL;
	memset(o, 0, sizeof(*o));
	memcpy(o, &sc_object, sizeof(*o));

	return o;
}


void
sc_release(config_object_t *c)
{
	sc_free(c);
	free(c);
}
