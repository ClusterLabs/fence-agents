/**
 * Syslog wrapper that does not block
 *
 * Lon Hohberger, 2009
 */

#include "config.h"

#include <pthread.h>
#include <unistd.h>
#include <sys/syslog.h>
#include <signal.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdarg.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/time.h>
#include <errno.h>

#include "list.h"

struct log_entry {
	list_head();
	char *message;
	int sev;
	int bufsz;
};

#define MAX_QUEUE_LENGTH 10
#define LOGLEN 256

static struct log_entry *_log_entries = NULL;
static pthread_mutex_t log_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t log_cond = PTHREAD_COND_INITIALIZER;
static int log_size = 0;
static int dropped = 0;
static pthread_t thread_id = 0;

void __real_syslog(int severity, const char *fmt, ...);
void __wrap_syslog(int severity, const char *fmt, ...);
void __wrap_closelog(void);

static void *
_log_thread(void *arg)
{
	struct timeval tv;
	struct timespec ts;
	struct log_entry *entry;

	do {
		gettimeofday(&tv, NULL);
		ts.tv_sec = tv.tv_sec + 10;
		ts.tv_nsec = tv.tv_usec;

		pthread_mutex_lock(&log_mutex);

		while (!(entry = _log_entries)) {
			if (pthread_cond_timedwait(&log_cond,
						   &log_mutex,
						   &ts) == ETIMEDOUT)
				goto out;
		}

		list_remove(&_log_entries, entry);
		--log_size;
		if (log_size < 0)
			raise(SIGSEGV);
		pthread_mutex_unlock(&log_mutex);

		__real_syslog(entry->sev, entry->message);
		free(entry->message);
		free(entry);
	} while (1);

out:
	thread_id = (pthread_t)0;
	pthread_mutex_unlock(&log_mutex);
	return NULL;
}


static int
insert_entry(int sev, char *buf, int bufsz)
{
	struct log_entry *lent;
	pthread_attr_t attrs;

	lent = malloc(sizeof(*lent));
	if (!lent)
		return -1;
	lent->sev = sev;
	lent->message = buf;
	lent->bufsz = bufsz;

	pthread_mutex_lock(&log_mutex);
	if (log_size >= MAX_QUEUE_LENGTH) {
		free(lent->message);
		free(lent);

		++dropped;
		lent = (struct log_entry *)(le(_log_entries)->le_prev);

		lent->sev = LOG_WARNING;
		snprintf(lent->message, lent->bufsz,
			 "%d message(s) lost due to syslog load\n",
			 dropped + 1);
		/* Dropped +1 because we overwrote a message to
		 * give the 'dropped' message */
	} else {
		++log_size;
		dropped = 0;
		list_insert(&_log_entries, lent);
	}

	if (!thread_id) {
		pthread_attr_init(&attrs);
	       	pthread_attr_setinheritsched(&attrs, PTHREAD_INHERIT_SCHED);

		if (pthread_create(&thread_id, &attrs, _log_thread, NULL) < 0)
			thread_id = 0;
		pthread_mutex_unlock(&log_mutex);
	} else {
		pthread_mutex_unlock(&log_mutex);
		pthread_cond_signal(&log_cond);
	}

	return 0;
}


__attribute__((__format__ (__printf__, 2, 0)))
void
__wrap_syslog(int severity, const char *fmt, ...)
{
	va_list      args;
	char         *logmsg;

	logmsg = malloc(LOGLEN);
	if (!logmsg)
		return;
	memset(logmsg, 0, LOGLEN);

	va_start(args, fmt);
	vsnprintf(logmsg + strlen(logmsg), LOGLEN - strlen(logmsg), 
		  fmt, args);
	va_end(args);

	insert_entry(severity, logmsg, LOGLEN);

	return;
}


void __real_closelog(void);

void
__wrap_closelog(void)
{
	struct log_entry *lent;
#ifdef DEBUG
	int lost = 0;
#endif

	if (thread_id != 0) {
		pthread_cancel(thread_id);
		pthread_join(thread_id, NULL);
		thread_id = 0;
	}
	__real_closelog();
	while (_log_entries) {
#ifdef DEBUG
		++lost;
#endif
		lent = _log_entries;
		list_remove(&_log_entries, lent);
		free(lent->message);
		free(lent);
	}

#ifdef DEBUG
	printf("%d lost\n", lost);
#endif
}


#ifdef STANDALONE
int
main(int argc, char**argv)
{
	int x;

	for (x = 0; x < 100; x++) {
		syslog(1, "Yo %d\n", x);
	}
	sleep(1);

	closelog();

	return 0;
}

#endif
