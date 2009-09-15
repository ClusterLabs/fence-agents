#ifndef _FENCE_VIRT_H
#define _FENCE_VIRT_H

#ifdef SYSCONFDIR
#define DEFAULT_CONFIG_FILE SYSCONFDIR "/fence_virt.conf"
#else
#define DEFAULT_CONFIG_FILE SYSCONFDIR "/etc/fence_virt.conf"
#endif

#endif
