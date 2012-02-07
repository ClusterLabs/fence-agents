/*
  Copyright Red Hat, Inc. 2006

  This program is free software; you can redistribute it and/or modify it
  under the terms of the GNU General Public License as published by the
  Free Software Foundation; either version 2, or (at your option) any
  later version.

  This program is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; see the file COPYING.  If not, write to the
  Free Software Foundation, Inc.,  675 Mass Ave, Cambridge, 
  MA 02139, USA.
*/
#include <stdio.h>
#include <netdb.h>
#include <errno.h>
#include <syslog.h>
#include <simpleconfig.h>
#include <static_map.h>

#include <server_plugin.h>

#include <crm/cib.h>
#include <crm/pengine/status.h>

/* Local includes */
#include "xvm.h"
#include "debug.h"


#define BACKEND_NAME "pm-fence"
#define VERSION "0.1"

#define MAGIC 0x1e0d197a

#define ATTR_NAME_PREFIX "force_stop-"
#define ATTR_VALUE "true"
#define READ_CIB_RETRY 30

enum rsc_status {
	RS_STARTED = 1,
	RS_STOPPED,
	RS_UNDEFINED,
	RS_GETERROR
};

struct pf_info {
	int magic;
	cib_t *cib;
	unsigned int loglevel;
};
cib_t **cib = NULL;
pe_working_set_t data_set;

#define VALIDATE(arg) \
do { \
	if (!arg || ((struct pf_info *)arg)->magic != MAGIC) { \
		errno = EINVAL; \
		return -1; \
	} \
} while(0)


static void
free_dataset(void)
{
	dbg_printf(5, "%s\n", __FUNCTION__);

	if (!data_set.input)
		return;
	free_xml(data_set.input);
	data_set.input = NULL;
	cleanup_calculations(&data_set);
	memset(&data_set, 0, sizeof(pe_working_set_t));
}

static void
disconnect_cib(void)
{
	dbg_printf(5, "%s\n", __FUNCTION__);

	if (*cib) {
		(*cib)->cmds->signoff(*cib);
		cib_delete(*cib);
		*cib = NULL;
	}
	free_dataset();
}

static gboolean
connect_cib(void)
{
	enum cib_errors rc = cib_ok;
	int i;

	dbg_printf(5, "%s\n", __FUNCTION__);

	if (*cib)
		return TRUE;
	memset(&data_set, 0, sizeof(pe_working_set_t));

	*cib = cib_new();
	if (!*cib) {
		syslog(LOG_NOTICE, "cib connection initialization failed\n");
		printf("cib connection initialization failed\n");
		return FALSE;
	}
	for (i = 1; i <= 20; i++) {
		if (i) sleep(1);
		dbg_printf(4, "%s: connect to cib attempt: %d\n", __FUNCTION__, i);
		rc = (*cib)->cmds->signon(*cib, crm_system_name, cib_command);
		if (rc == cib_ok)
			break;
	}
	if (rc != cib_ok) {
		syslog(LOG_NOTICE,
			"failed to signon to cib: %s\n", cib_error2string(rc));
		printf("failed to signon to cib: %s\n", cib_error2string(rc));
		disconnect_cib();
		return FALSE;
	}
	dbg_printf(3, "%s: succeed at connect to cib\n", __FUNCTION__);
	return TRUE;
}

static gboolean
get_dataset(void)
{
	xmlNode *current_cib;
	unsigned int loglevel;

	dbg_printf(5, "%s\n", __FUNCTION__);

	free_dataset();
	current_cib = get_cib_copy(*cib);
	if (!current_cib)
		return FALSE;
	set_working_set_defaults(&data_set);
	data_set.input = current_cib;
	data_set.now = new_ha_date(TRUE);

	/* log output of the level below LOG_ERR is deterred */
	loglevel = get_crm_log_level();
	set_crm_log_level(LOG_ERR);
	cluster_status(&data_set);
	set_crm_log_level(loglevel);
	return TRUE;
}

static enum rsc_status
get_rsc_status(const char *rid, char **node, char **uuid)
{
	GListPtr gIter = NULL, gIter2 = NULL;
	resource_t *rsc;

	dbg_printf(5, "%s: Resource %s\n", __FUNCTION__, rid);

	if (!rid || connect_cib() == FALSE)
		return RS_GETERROR;
	if (get_dataset() == FALSE) {
		disconnect_cib();
		if (connect_cib() == FALSE || get_dataset() == FALSE)
			return RS_GETERROR;
	}

	/* find out from RUNNING resources */
	gIter = data_set.nodes;
	for(; gIter; gIter = gIter->next) {
		node_t *node2 = (node_t*)gIter->data;

		gIter2 = node2->details->running_rsc;
		for(; gIter2; gIter2 = gIter2->next) {
			resource_t *rsc2 = (resource_t*)gIter2->data;

			dbg_printf(3, "%s: started resource [%s]\n",
				__FUNCTION__, rsc2->id);
			if (safe_str_eq(rid, rsc2->id)) {
				if (node && !*node) {
					*node = crm_strdup(node2->details->uname);
					*uuid = crm_strdup(node2->details->id);
					dbg_printf(3, "%s: started node [%s(%s)]\n",
						__FUNCTION__, *node, *uuid);
				}
				return RS_STARTED;
			}
		}
	}

	/* find out from ALL resources */
	rsc = pe_find_resource(data_set.resources, rid);
	if (rsc) {
		dbg_printf(3, "%s: stopped resource [%s]\n", __FUNCTION__, rsc->id);
		return RS_STOPPED;
	}
	return RS_UNDEFINED;
}

/*
 * The cluster node attribute is updated for RA which controls a virtual machine.
 */
static gboolean
update_status_attr(char cmd, const char *rid,
	const char *node, const char *uuid, gboolean confirm)
{
	char *name = g_strdup_printf("%s%s", ATTR_NAME_PREFIX, rid);
	char *value;
	gboolean ret = FALSE;

	dbg_printf(5, "%s\n", __FUNCTION__);

	switch (cmd) {
	case 'U':
		value = ATTR_VALUE;
		break;
	case 'D':
		value = NULL;
		break;
	default:
		goto out;
	}
	dbg_printf(1, "%s: Update attribute %s=%s for %s\n",
		__FUNCTION__, name, value, node);

	ret = attrd_lazy_update(cmd, node,
		name, value, XML_CIB_TAG_STATUS, NULL, NULL);
	if (confirm == FALSE)
		goto out;
	if (ret == TRUE) {
		enum cib_errors rc;
		int i;
		ret = FALSE; value = NULL;
		for (i = 1; i <= READ_CIB_RETRY; i++) {
			dbg_printf(4, "%s: waiting..[%d]\n", __FUNCTION__, i);
			sleep(1);
#ifdef PM_1_0
			rc = read_attr(*cib, XML_CIB_TAG_STATUS,
				uuid, NULL, NULL, name, &value, FALSE);
#else
			rc = read_attr(*cib, XML_CIB_TAG_STATUS,
				uuid, NULL, NULL, NULL, name, &value, FALSE);
#endif
			dbg_printf(3, "%s: cmd=%c, rc=%d, value=%s\n",
				__FUNCTION__, cmd, rc, value);
			if (rc == cib_ok) {
				if (cmd == 'U' && !g_strcmp0(value, ATTR_VALUE)) {
					ret = TRUE;
					break;
				}
			} else if (rc == cib_NOTEXISTS) {
				if (cmd == 'D') {
					ret = TRUE;
					break;
				}
			} else {
				break;
			}
			crm_free(value);
		}
		crm_free(value);
	}
out:
	crm_free(name);
	return ret;
}

/*
 * ref. pacemaker/tools/crm_resource.c
 */
static enum cib_errors
find_meta_attr(const char *rid, const char *name, char **id)
{
	char *xpath;
	xmlNode *xml = NULL;
	const char *p;
	enum cib_errors rc;

	dbg_printf(5, "%s\n", __FUNCTION__);

	xpath = g_strdup_printf("%s/*[@id=\"%s\"]/%s/nvpair[@name=\"%s\"]",
		get_object_path("resources"), rid, XML_TAG_META_SETS, name);
	dbg_printf(3, "%s: query=%s\n", __FUNCTION__, xpath);

	rc = (*cib)->cmds->query(*cib, xpath, &xml,
		cib_sync_call|cib_scope_local|cib_xpath);
	if (rc != cib_ok) {
		if (rc != cib_NOTEXISTS) {
			syslog(LOG_NOTICE, "failed to query to cib: %s\n",
				cib_error2string(rc));
			printf("failed to query to cib: %s\n",
				cib_error2string(rc));
		}
		crm_free(xpath);
		return rc;
	}
	crm_log_xml_debug(xml, "Match");

	p = crm_element_value(xml, XML_ATTR_ID);
	if (p)
		*id = crm_strdup(p);
	crm_free(xpath);
	free_xml(xml);
	return rc;
}

/*
 * ref. pacemaker/tools/crm_resource.c
 */
static gboolean
set_rsc_role(const char *rid, const char *value)
{
	resource_t *rsc;
	char *id = NULL;
	xmlNode *top = NULL, *obj = NULL;
	enum cib_errors rc;
	const char *name = XML_RSC_ATTR_TARGET_ROLE;

	dbg_printf(5, "%s\n", __FUNCTION__);

	rsc = pe_find_resource(data_set.resources, rid);
	if (!rsc)
		return FALSE;

	rc = find_meta_attr(rid, name, &id);
	if (rc == cib_ok) {
		dbg_printf(3, "%s: Found a match for name=%s: id=%s\n",
			__FUNCTION__, name, id);
	} else if (rc == cib_NOTEXISTS) {
		char *set;
		set = crm_concat(rid, XML_TAG_META_SETS, '-');
		id = crm_concat(set, name, '-');
		top = create_xml_node(NULL, crm_element_name(rsc->xml));
		crm_xml_add(top, XML_ATTR_ID, rid);
		obj = create_xml_node(top, XML_TAG_META_SETS);
		crm_xml_add(obj, XML_ATTR_ID, set);
		crm_free(set);
	} else {
		return FALSE;
	}

	obj = create_xml_node(obj, XML_CIB_TAG_NVPAIR);
	if (!top)
		top = obj;
	crm_xml_add(obj, XML_ATTR_ID, id);
	crm_xml_add(obj, XML_NVPAIR_ATTR_NAME, name);
	crm_xml_add(obj, XML_NVPAIR_ATTR_VALUE, value);

	dbg_printf(1, "%s: Update meta-attr %s=%s for %s\n",
		__FUNCTION__, name, value, rid);
	crm_log_xml_debug(top, "Update");

	rc = (*cib)->cmds->modify(*cib, XML_CIB_TAG_RESOURCES, top, cib_sync_call);
	if (rc != cib_ok) {
		syslog(LOG_NOTICE,
			"failed to modify to cib: %s\n", cib_error2string(rc));
		printf("failed to modify to cib: %s\n", cib_error2string(rc));
	}
	free_xml(top);
	crm_free(id);
	return rc == cib_ok ? TRUE : FALSE;
}

static gboolean
start_resource(const char *rid)
{
	gboolean updated_cib = FALSE;
	int i = 0;

	dbg_printf(5, "%s\n", __FUNCTION__);

	if (!rid)
		return FALSE;

	printf("Starting domain %s(resource)\n", rid);

check:
	if (i >= READ_CIB_RETRY)
		return FALSE;
	switch (get_rsc_status(rid, NULL, NULL)) {
	case RS_STARTED:
		dbg_printf(2, "%s: Resource %s started\n", __FUNCTION__, rid);
		return TRUE;
	case RS_STOPPED:
		if (updated_cib == FALSE) {
			if (set_rsc_role(rid, RSC_ROLE_STARTED_S) == FALSE)
				return FALSE;
			updated_cib = TRUE;
		} else {
			i++;
		}
		dbg_printf(4, "%s: waiting..[%d]\n", __FUNCTION__, i);
		sleep(1);
		goto check;
	default:
		return FALSE;
	}
}

static gboolean
stop_resource(const char *rid)
{
	char *node = NULL, *uuid = NULL;
	gboolean updated_cib = FALSE;
	gboolean ret = FALSE;
	int i = 0;

	dbg_printf(5, "%s\n", __FUNCTION__);

	if (!rid)
		return FALSE;

	printf("Destroying domain %s(resource)\n", rid);

check:
	if (i >= READ_CIB_RETRY)
		goto rollback;
	switch (get_rsc_status(rid, &node, &uuid)) {
	case RS_STARTED:
		if (updated_cib == FALSE) {
			if (update_status_attr('U', rid, node, uuid, TRUE) == FALSE)
				goto out;
			if (set_rsc_role(rid, RSC_ROLE_STOPPED_S) == FALSE)
				goto rollback;
			updated_cib = TRUE;
		} else {
			i++;
		}
		dbg_printf(4, "%s: waiting..[%d]\n", __FUNCTION__, i);
		sleep(1);
		goto check;
	case RS_STOPPED:
		dbg_printf(2, "%s: Resource %s stopped\n", __FUNCTION__, rid);
		if (updated_cib == FALSE)
			ret = TRUE;
		else
			ret = update_status_attr('D', rid, node, uuid, TRUE);
		goto out;
	default:
		goto out;
	}
rollback:
	update_status_attr('D', rid, node, uuid, FALSE);
out:
	if (node) crm_free(node);
	if (uuid) crm_free(uuid);
	return ret;
}

static int
char2level(const char *str)
{
	dbg_printf(5, "%s\n", __FUNCTION__);

	if (!str)
		return 0;
	if (safe_str_eq(str, "emerg")) return LOG_EMERG;
	else if (safe_str_eq(str, "alert")) return LOG_ALERT;
	else if (safe_str_eq(str, "crit")) return LOG_CRIT;
	else if (safe_str_eq(str, "err") ||
		 safe_str_eq(str, "error")) return LOG_ERR;
	else if (safe_str_eq(str, "warning") ||
		 safe_str_eq(str, "warn")) return LOG_WARNING;
	else if (safe_str_eq(str, "notice")) return LOG_NOTICE;
	else if (safe_str_eq(str, "info")) return LOG_INFO;
	else if (safe_str_eq(str, "debug")) return LOG_DEBUG;
	else if (safe_str_eq(str, "debug2")) return LOG_DEBUG + 1;
	else if (safe_str_eq(str, "debug3")) return LOG_DEBUG + 2;
	else if (safe_str_eq(str, "debug4")) return LOG_DEBUG + 3;
	else if (safe_str_eq(str, "debug5")) return LOG_DEBUG + 4;
	else if (safe_str_eq(str, "debug6")) return LOG_DEBUG + 5;
	return 0;
}

static void
reset_lib_log(unsigned int level)
{
	dbg_printf(5, "%s\n", __FUNCTION__);

	cl_log_set_entity(BACKEND_NAME);
	set_crm_log_level(level);
}


static int
pf_null(const char *rid, void *priv)
{
	dbg_printf(5, "%s: Resource %s\n", __FUNCTION__, rid);

	printf("NULL operation: returning failure\n");
	return 1;
}


static int
pf_off(const char *rid, const char *src, uint32_t seqno, void *priv)
{
	struct pf_info *info = (struct pf_info *)priv;
	int ret;

	dbg_printf(5, "%s: Resource %s\n", __FUNCTION__, rid);

	VALIDATE(info);
	reset_lib_log(info->loglevel);
	cib = &info->cib;

	ret = stop_resource(rid) == TRUE ? 0 : 1;
	free_dataset();
	return ret;
}


static int
pf_on(const char *rid, const char *src, uint32_t seqno, void *priv)
{
	struct pf_info *info = (struct pf_info *)priv;
	int ret;

	dbg_printf(5, "%s: Resource %s\n", __FUNCTION__, rid);

	VALIDATE(info);
	reset_lib_log(info->loglevel);
	cib = &info->cib;

	ret = start_resource(rid) == TRUE ? 0 : 1;
	free_dataset();
	return ret;
}


static int
pf_devstatus(void *priv)
{
	dbg_printf(5, "%s\n", __FUNCTION__);

	if (priv)
		return 0;
	return 1;
}

static int
pf_status(const char *rid, void *priv)
{
	struct pf_info *info = (struct pf_info *)priv;
	enum rsc_status rstat;

	dbg_printf(5, "%s: Resource %s\n", __FUNCTION__, rid);

	VALIDATE(info);
	reset_lib_log(info->loglevel);
	cib = &info->cib;

	rstat = get_rsc_status(rid, NULL, NULL);
	dbg_printf(3, "%s: get_rsc_status [%d]\n", __FUNCTION__, rstat);
	free_dataset();

	switch (rstat) {
	case RS_STARTED:
		return RESP_SUCCESS;
	case RS_STOPPED:
		return RESP_OFF;
	case RS_UNDEFINED:
	case RS_GETERROR:
	default:
		return RESP_FAIL;
	}
}


static int
pf_reboot(const char *rid, const char *src, uint32_t seqno, void *priv)
{
	struct pf_info *info = (struct pf_info *)priv;
	int ret = 1;

	dbg_printf(5, "%s: Resource %s\n", __FUNCTION__, rid);

	VALIDATE(info);
	reset_lib_log(info->loglevel);
	cib = &info->cib;

	if (stop_resource(rid) == TRUE)
		ret = start_resource(rid) == TRUE ? 0 : ret;
	free_dataset();
	return ret;
}


/*
 * Not implemented, because it is not called from the STONITH plug-in.
 */
static int
pf_hostlist(hostlist_callback callback, void *arg, void *priv)
{
	struct pf_info *info = (struct pf_info *)priv;

	dbg_printf(5, "%s\n", __FUNCTION__);

	VALIDATE(info);
	return 1;
}


static int
pf_init(backend_context_t *c, config_object_t *conf)
{
	struct pf_info *info = NULL;
	int level = 0;
	char value[256];
	char key[32];

	dbg_printf(5, "%s\n", __FUNCTION__);

#ifdef _MODULE
	if (sc_get(conf, "fence_virtd/@debug", value, sizeof(value)) == 0)
		dset(atoi(value));
#endif
	sprintf(key, "backends/%s/@pmlib_loglevel", BACKEND_NAME);
	if (sc_get(conf, key, value, sizeof(value)) == 0) {
		level = char2level(value);
		crm_log_init(BACKEND_NAME, level, FALSE, FALSE, 0, NULL);
		cl_log_enable_stdout(TRUE);
	}

	info = malloc(sizeof(*info));
	if (!info)
		return -1;

	memset(info, 0, sizeof(*info));
	info->magic = MAGIC;
	info->loglevel = level;
	*c = (void *)info;
	return 0;
}


static int
pf_shutdown(backend_context_t c)
{
	struct pf_info *info = (struct pf_info *)c;

	dbg_printf(5, "%s\n", __FUNCTION__);

	VALIDATE(info);
	reset_lib_log(info->loglevel);
	cib = &info->cib;

	disconnect_cib();
	free(info);
	return 0;
}


static fence_callbacks_t pf_callbacks = {
	.null = pf_null,
	.off = pf_off,
	.on = pf_on,
	.reboot = pf_reboot,
	.status = pf_status,
	.devstatus = pf_devstatus,
	.hostlist = pf_hostlist
};

static backend_plugin_t pf_plugin = {
	.name = BACKEND_NAME,
	.version = VERSION,
	.callbacks = &pf_callbacks,
	.init = pf_init,
	.cleanup = pf_shutdown,
};


#ifdef _MODULE
double
BACKEND_VER_SYM(void)
{
	return PLUGIN_VERSION_BACKEND;
}

const backend_plugin_t *
BACKEND_INFO_SYM(void)
{
	return &pf_plugin;
}
#else
static void __attribute__((constructor))
pf_register_plugin(void)
{
	plugin_reg_backend(&pf_plugin);
}
#endif
