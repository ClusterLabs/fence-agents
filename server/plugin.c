#include <stdio.h>
#include <list.h>
#include <server_plugin.h>
#include <malloc.h>
#include <string.h>


typedef struct _plugin_list {
	list_head();
	const plugin_t *plugin;
} plugin_list_t;

static plugin_list_t *server_plugins = NULL;

void
plugin_register(const plugin_t *plugin)
{
	plugin_list_t *newplug;

	newplug = malloc(sizeof(*newplug));
	if (!newplug)
		return;
	memset(newplug, 0, sizeof(*newplug));
	newplug->plugin = plugin;
	list_insert(&server_plugins, newplug);
}

void
plugin_dump(void)
{
	plugin_list_t *p;
	int x;

	list_for(&server_plugins, p, x) {
		printf("%s %s\n", p->plugin->name, p->plugin->version);
	}
}

const plugin_t *
plugin_find(const char *name)
{
	plugin_list_t *p;
	int x;

	list_for(&server_plugins, p, x) {
		if (!strcasecmp(name, p->plugin->name))
			return p->plugin;
	}

	return NULL;
}


int
plugin_init(const plugin_t *p, srv_context_t *c)
{
	return p->init(c);
}


int
plugin_shutdown(const plugin_t *p, srv_context_t c)
{
	return p->cleanup(c);
}


