%{
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include "config-stack.h"
#include "y.tab.h"
#include "simpleconfig.h"

/* Some distributions can't use the output from flex without help */
#define ECHO if(fwrite( yytext, yyleng, 1, yyout ))

struct value *val_list = NULL;
struct node *node_list = NULL;
struct parser_context *context_stack = NULL;

int _line_count = 1;

%}
%%
[\n] {
	++_line_count;
}

[ \t]* {}

\#[^\n]* {}

"{" {
	struct parser_context *c = NULL;
	//printf("obrace\n");

	c = malloc(sizeof(*c));
	assert(c);

	c->next = context_stack;
	c->val_list = val_list;
	c->node_list = node_list;

	context_stack = c;
	val_list = NULL;
	node_list = NULL;

	return T_OBRACE;
}

"}" {
	return T_CBRACE;
}

";" {
	return T_SEMI;
}

"=" {
	return T_EQ;
}

[^ \t{};=\"\n]+ {
	yylval.sval = strdup(yytext);
	return T_ID;
}

\"[^\"]+\" {
	yylval.sval = strdup(yytext+1);
	yylval.sval[strlen(yytext)-2] = 0;
	return T_VAL;
}

%%
void
reset_vars(void)
{
	_line_count = 1;
}


int
yywrap(void)
{
	return 1;
}


#ifdef STANDALONE
int
main(int argc, char *argv[])
{
	char value[80];
	config_object_t *c = NULL;

	yyout = fopen("/dev/null","w");

	c = sc_init();
	sc_parse(c, NULL);
	sc_dump(c, stdout);
	if (argc == 2) {
		if (sc_get(c, argv[1], value, sizeof(value)) == 0)
			printf("%s = %s\n", argv[1], value);
		else
			printf("Not found\n");
	} else if (argc == 3) {
		printf("---------\n");
		if (sc_set(c, argv[1], argv[2]) == 0)
			sc_dump(c, stdout);
	}

	sc_release(c);

	return 0;
}
#endif
