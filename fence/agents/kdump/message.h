/* -*- mode: C; c-basic-offset: 4; indent-tabs-mode: nil -*-
 *
 * Copyright (c) Ryan O'Hara (rohara@redhat.com)
 * Copyright (c) Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 *
 */

#ifndef _FENCE_KDUMP_MESSAGE_H
#define _FENCE_KDUMP_MESSAGE_H

#define FENCE_KDUMP_MAGIC 0x1B302A40

#define FENCE_KDUMP_MSGV1 0x1

typedef struct __attribute__ ((packed)) fence_kdump_msg {
    uint32_t magic;
    uint32_t version;
} fence_kdump_msg_t;

static inline void
init_message (fence_kdump_msg_t *msg)
{
    msg->magic   = FENCE_KDUMP_MAGIC;
    msg->version = FENCE_KDUMP_MSGV1;
}

#endif /* _FENCE_KDUMP_MESSAGE_H */
