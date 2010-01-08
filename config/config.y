%{
#include <stdio.h>
#include <malloc.h>
#include <string.h>
#include <assert.h>
#include "config-stack.h"

extern int yylex (void);
int yyerror(const char *foo);

int
_sc_value_add(char *id, char *val, struct value **list)
{
	struct value *v;

	v = malloc(sizeof(*v));
	assert(v);

	memset(v, 0, sizeof(*v));
	v->id = id;
	v->val = val;
	//snprintf(v->id, sizeof(v->id), "%s", id);
	//snprintf(v->val, sizeof(v->val), "%s", val);
	//printf("add %s %s on to %p\n", id, val, *list);

	v->next = *list;
	*list = v;

	//printf("new list %p\n", *list);
	return 0;
}


int
_sc_node_add(char *id, char *val, struct value *vallist,
	     struct node *nodelist, struct node **list)
{
	struct node *n;

	n = malloc(sizeof(*n));
	assert(n);

	//printf("nodes %p values %p\n", nodelist, vallist);

	memset(n, 0, sizeof(*n));
	//snprintf(n->id, sizeof(n->id), "%s", id);
	n->id = id; /* malloc'd during parsing */
	n->val = val; /* malloc'd during parsing */
	n->values = vallist;
	n->nodes = nodelist;
	n->next = *list;
	*list = n;

	return 0;
}

%}

%token <sval> T_ID
%token <sval> T_VAL
%token T_OBRACE T_CBRACE T_EQ T_SEMI

%start stuff

%union {
	char *sval;
	int ival;
}

%%
node:
	T_ID T_OBRACE stuff T_CBRACE {
		struct parser_context *c = NULL;

		c = context_stack;
		_sc_node_add($1, NULL, val_list, node_list, &c->node_list);
		val_list = c->val_list;
		node_list = c->node_list;
        	context_stack = c->next;

		free(c);
	}
	|
	T_ID T_EQ T_VAL T_OBRACE stuff T_CBRACE {
		struct parser_context *c = NULL;

		c = context_stack;
		_sc_node_add($1, $3, val_list, node_list, &c->node_list);
		val_list = c->val_list;
		node_list = c->node_list;
        	context_stack = c->next;

		free(c);
	}
	|
	T_ID T_OBRACE T_CBRACE {
		struct parser_context *c = NULL;

		c = context_stack;
		_sc_node_add($1, NULL, val_list, node_list, &c->node_list);
		val_list = c->val_list;
		node_list = c->node_list;
        	context_stack = c->next;

		free(c);
	}
	|
	T_ID T_EQ T_VAL T_OBRACE T_CBRACE {
		struct parser_context *c = NULL;

		c = context_stack;
		_sc_node_add($1, $3, val_list, node_list, &c->node_list);
		val_list = c->val_list;
		node_list = c->node_list;
        	context_stack = c->next;

		free(c);
	}
	;

stuff:
	node stuff | assign stuff | node | assign
	;

assign:
	T_ID T_EQ T_VAL T_SEMI {
		_sc_value_add($1, $3, &val_list);
	}
	;
%%

extern int _line_count;

int
yyerror(const char *foo)
{
	printf("%s on line %d\n", foo, _line_count);
	return 0;
}
