#ifndef _CONFIG_STACK_H
#define _CONFIG_STACK_H

int yyparse (void);
extern FILE *yyin;

struct value {
	char *id;
	char *val;
	struct value *next;
};


struct node {
	char *id;
	char *val;
	struct node *nodes;
	struct value *values;
	struct node *next;
};


struct parser_context {
	struct value *val_list;
	struct node *node_list;
	struct parser_context *next;
};

extern struct value *val_list;
extern struct node *node_list;
extern struct parser_context *context_stack;

int _sc_value_add(char *id, char *val, struct value **list);
int _sc_node_add(char *id, char *val, struct value *vallist,
		 struct node *nodelist, struct node **list);


#endif
