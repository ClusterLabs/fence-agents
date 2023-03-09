#include "config.h"

#include <uuid/uuid.h>
#include <errno.h>
#include <string.h>

#include "uuid-test.h"

int
is_uuid(const char *value)
{
	uuid_t id;
	char test_value[37];

	if (strlen(value) < 36) {
		return 0;
	}

	memset(id, 0, sizeof(uuid_t));

	if (uuid_is_null(id) < 0) {
		errno = EINVAL;
		return -1;
	}

	if (uuid_parse(value, id) < 0) {
		return 0;
	}

	memset(test_value, 0, sizeof(test_value));
	uuid_unparse(id, test_value);

	if (strcasecmp(value, test_value)) {
		return 0;
	}

	return 1;
}

#ifdef STANDALONE
#include <stdio.h>

int 
main(int argc, char **argv)
{
	int ret;

	if (argc < 2) {
		printf("Usage: uuidtest <value>\n");
		return 1;
	}

	ret = is_uuid(argv[1]);
	if (ret == 0) {
		printf("%s is NOT a uuid\n", argv[1]);
	} else if (ret == 1) {
		printf("%s is a uuid\n", argv[1]);
	} else {
		printf("Error: %s\n", strerror(errno));
		return 1;
	}

	return 0;
}

#endif
