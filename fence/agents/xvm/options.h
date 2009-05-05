#ifndef _XVM_OPTIONS_H
#define _XVM_OPTIONS_H

typedef enum {
	F_FOREGROUND	= 0x1,
	F_NOCCS		= 0x2,
	F_ERR		= 0x4,
	F_HELP		= 0x8,
	F_USE_UUID	= 0x10,
	F_VERSION	= 0x20,
	F_CCSERR	= 0x40,
	F_CCSFAIL	= 0x80,
	F_NOCLUSTER	= 0x100,
	F_DEBUG		= 0x200,
	F_METADATA	= 0x400
} arg_flags_t;


typedef struct {
	char *addr;
	char *domain;
	char *key_file;
	char *uri;
	fence_cmd_t op;
	fence_hash_t hash;
	fence_auth_type_t auth;
	int port;
	unsigned int ifindex;
	int family;
	int timeout;
	int retr_time;
	arg_flags_t flags;
	int debug;
	int ttl;
} fence_xvm_args_t;

/* Private structure for commandline / stdin fencing args */
struct arg_info {
	const char opt;
	const char *opt_desc;
	const char *stdin_opt;
	const char *desc;
	void (*assign)(fence_xvm_args_t *, struct arg_info *, char *);
};


/* Get options */
void args_init(fence_xvm_args_t *args);
void args_finalize(fence_xvm_args_t *args);

void args_get_getopt(int argc, char **argv, const char *optstr,
		     fence_xvm_args_t *args);
void args_get_stdin(const char *optstr, fence_xvm_args_t *args);
void args_get_ccs(const char *optstr, fence_xvm_args_t *args);
void args_usage(char *progname, const char *optstr, int print_stdin);
void args_metadata(char *progname, const char *optstr);
void args_print(fence_xvm_args_t *args);

struct arg_info *find_arg_by_char(char arg);
struct arg_info *find_arg_by_string(char *arg);

#endif
