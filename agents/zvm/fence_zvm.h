/*
 * fence_zvm.h: SMAPI interface for z/VM Guests
 *
 * Copyright (C) 2012 Sine Nomine Associates
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.  If not, see
 * <http://www.gnu.org/licenses/>.
 *
 * Authors:
 * Neale Ferguson <neale@sinenomine.net>
 *
 */

#ifndef FENCE_ZVM_H
# define FENCE_ZVM_H

# include <sys/types.h>

# define SMAPI_TARGET	"OVIRTADM"
# define SMAPI_MAXCPU   96

/*
 * Return codes
 */
# define RC_OK				  0	/* Request successful */
# define RC_WNG				  4	/* Warning */
# define RC_ERR				  8	/* Error */
# define RCERR_SYNTAX			 24	/* Function parameter syntax error */
# define RCERR_FILE_NOT_FOUND		 28	/* File not found */
# define RCERR_FILE_CANNOT_BE_UPDATED	 36	/* Name list file cannot be updated */
# define RCERR_AUTH			100	/* Request not authorized by ESM  */
# define RCERR_NO_AUTHFILE		104	/* Authorization file not found */
# define RCERR_AUTHFILE_RO		106	/* Authorization file cannot be updated */
# define RCERR_EXISTS			108	/* Authorization file entry already exists */
# define RCERR_NO_ENTRY			112	/* Authorization file entry does not exist */
# define RCERR_USER_PW_BAD		120	/* Authentication error: Userid or pwd invalid */
# define RCERR_PW_EXPIRED		128	/* Authentication error: password expired */
# define RCERR_ESM			188	/* ESM failure */
# define RCERR_PW_CHECK			192	/* Internal error: can't authenticate user or pwd */
# define RCERR_DMSCSL			196	/* Internal Callable Services error */
# define RCERR_IMAGEOP			200	/* Image Operation error */
# define RCERR_LIST			200	/* Bad rc for list or list function */
# define RCERR_IMAGEDEVU		204	/* Image Device Usage error */
# define RCERR_IMAGEDISKU		208	/* Image Disk Usage error */
# define RCERR_IMAGECONN		212	/* Image Connectivity Definition error */
# define RCERR_IMAGECPU			216	/* Image CPU definition error */
# define RCERR_VOLUME			300	/* Image Volume function error */
# define RCERR_INTERNAL			396	/* Internal product-specific error */
# define RCERR_IMAGE_NAME		400	/* Image Name error */
# define RCERR_IMAGEDEF			400	/* Image Definition error */
# define RCERR_IMAGEDEVD		404	/* Image Device Definition error */
# define RCERR_IMAGEDISKD		408	/* Image Disk Definition error */
# define RCERR_IMAGECONND		412	/* Image Connectivity Definition error */
# define RCERR_PROTODEF			416	/* Prototype Definition error */
# define RCERR_DASD_DM			420	/* Volume/region name already defined or region in group */
# define RCERR_SEGMENT_DM		424	/* Segment definition errors */
# define RCERR_NOTIFY			428	/* Notification subscription errors */
# define RCERR_TAG			432	/* Local tag definition errors */
# define RCERR_PROFILED			436	/* Profile definition errors */
# define RCERR_POLICY_PW		444	/* Password policy error */
# define RCERR_POLICY_ACCT		448	/* Account number policy error */
# define RCERR_TASK			452	/* Task error */
# define RCERR_SCSI			456	/* SCSI error */
# define RCERR_DM			500	/* Directory Manager error */
# define RCERR_LIST_DM			504	/* Directory Manager list error */
# define RCERR_ASYNC_DM			592	/* Asynchronous Operation error */
# define RCERR_INTERNAL_DM		596	/* Internal Directory Manager error */
# define RCERR_SHSTOR			600	/* Shared Memory function error */
# define RCERR_VIRTUALNETWORKD		620	/* Vswitch function error */
# define RCERR_VMRM			800	/* Error from VMRM functions */
# define RCERR_SERVER			900	/* Socket-Server error */

/*
 * Syntax error reason codes
 */
# define RS_NONE			  0
# define RS_TOOMANY			  0
# define RS_TANY			  0 
# define RS_TBIN			  2
# define RS_UNSIGNEDINT			 10
# define RS_TNUM			 10
# define RS_UNSUPPORTED			 11
# define RS_SHORT			 14
# define RS_LESSTHANMIN			 15
# define RS_HEX				 16
# define RS_THEX			 16
# define RS_THEXHY			 17
# define RS_LONG			 13
# define RS_MORETHANMAX			 18
# define RS_UNRECOG			 19
# define RS_CONFLICTING			 23
# define RS_UNSPECIFIED			 24
# define RS_EXTRANEOUS			 25
# define RS_ALPHABETIC			 26
# define RS_TALPHA			 26
# define RS_FUNCTIONNAME		 27
# define RS_TALPHA_			 27
# define RS_ALPHANUMERIC		 36
# define RS_TNUMALPHA			 36
# define RS_ALPHANUMERIC_		 37
# define RS_TNUMALPHAHY			 37
# define RS_TLIST			 38 
# define RS_DIRMAINTFILE		 42
# define RS_TFILE			 42 
# define RS_DIRMAINTFILE_		 43
# define RS_TFILE_			 43 
# define RS_DIRMAINTFILE_EQ		 44
# define RS_TFILE_EQ			 44 
# define RS_UNEXPECTED_END		 88
# define RS_NON_BREAKING_CHAR		 99
# define RS_TNONBLANK			 99

/*
 * Non-syntax related reason codes
 */
# define RS_NONE			  0	/* Request successful */
# define RS_INVALID_USER		  2	/* Invalid user */
# define RS_INVALID_DEVICE		  2	/* invalid device */
# define RS_NO_OSAS			  4 	/* No OSAs exist */
# define RS_INVALID_OP			  3 	/* Invalid LAN operation */
# define RS_INVALID_PRO			  4 	/* Invalid LAN promiscuity */
# define RS_NO_DEV			  4 	/* No IPL device */
# define RS_DEFERRED_SERVER		  4 	/* Authorization deferred to server */
# define RS_DUP_NAME			  4 	/* Duplicate tag name */
# define RS_EXISTS			  4 	/* Device already exists*/
# define RS_IN_USE			  4 	/* Image Disk already in use */
# define RS_IVS_NAME_USED		  4 	/* Group/region/volume already defined */
# define RS_LOADDEV_NOT_FOUND		  4 	/* LOADDEV statement not found */
# define RS_NO_PARTNER			  4 	/* Partner image not found */
# define RS_NO_UPDATES			  4 	/* Directory manager not accepting update*/
# define RS_NOT_FOUND			  4 	/* Image/Task Not Found */
# define RS_NOTIFY_DUPLICATE		  4 	/* Duplicate subscription */
# define RS_SEG_NAME_DUPLICATE		  4 	/* Segment name already used */
# define RS_AFFINITY_SUPPRESSED		  4	/* CPU defined but affinity suppressed */
# define RS_WORK_OUTSTANDING		  4	/* Image_Defintion_* asynch */
# define RS_UNRESTRICTED_LAN		  5 	/* LAN is unrestricted */
# define RS_NO_USERS			  6 	/* No users authorized for LAN */
# define RS_ADAPTER_NOT_EXIST		  8 	/* Adapter does not exist */
# define RS_ALREADY_ACTIVE		  8 	/* Image already active */
# define RS_AUTHERR_CONNECT		  8 	/* Not authorized to connect */
# define RS_AUTHERR_ESM			  8 	/* Request not authorized by an ESM */
# define RS_BAD_RANGE			  8 	/* Bad page range */
# define RS_DEV_NOT_FOUND		  8 	/* Device not found */
# define RS_IVS_NAME_NOT_USED		  8 	/* Group/region/volume is not defined */
# define RS_NAME_EXISTS			  8 	/* Image Name already defined */
# define RS_NO_MEASUREMENT_DATA		  8 	/* No VMRM measurement query data */
# define RS_NOT_AVAILABLE		  8 	/* Directory manager not available */
# define RS_NOT_DEFINED			  8 	/* Image Device/Volume/Region/Group/Tag name not defined */
# define RS_NOT_EXIST			  8 	/* Device does not exist */
# define RS_NOTIFY_NOT_FOUND		  8 	/* No matching entries */
# define RS_NOT_IN_USE			  8 	/* Image disk not in use */
# define RS_OFFLINE			  8 	/* Successful; Object directory offline */
# define RS_SEG_NAME_NOT_FOUND		  8 	/* Segment name not used */
# define RS_WORKER_NOT_FOUND		  8 	/* Worker server not found */
# define RS_DEV_NOT_AVAIL_TO_ATTACH	 10  	/* Device not found */
# define RS_TOO_MANY_PARM		 10 	/* Too many parms in parameter list */
# define RS_TOO_FEW_PARM		 11 	/* Too few parms in parameter list */
# define RS_ALREADY_LOCKED		 12 	/* Image definition already locked */
# define RS_AUTHERR_DM			 12 	/* Request not authorized by Directory Manager */
# define RS_BUSY			 12 	/* Image device is busy */
# define RS_DUP_ORDINAL			 12 	/* Duplicate tag ordinal */
# define RS_FUNCTION_NOT_VALID		 12 	/* Not a valid SMAPI function */
# define RS_IVS_NAME_NOT_INCLUDED	 12 	/* Name not included (ISR,ISQ)*/
# define RS_LAN_NOT_EXIST		 12 	/* LAN does not exist */
# define RS_LOCKED			 12 	/* Image definition is locked */
# define RS_NAMESAVE_EXISTS		 12 	/* Namesave statementt already in directory*/
# define RS_NEW_LIST 			 12 	/* Successful new list created */
# define RS_NOT_ACTIVE			 12 	/* Image not active */
# define RS_NOT_INCLUDED		 12 	/* Region not included in group */
# define RS_NOT_LOGGED_ON		 12 	/* User not logged on */
# define RS_DEV_NOT_VOLUME		 12 	/* Device not a volume */
# define RS_UPDATE_SYNTAX_ERROR		 12 	/* Errors in configuration update buffer */
# define RS_FREE_MODE_NOT_AVAIL		 14 	/* Free mode not available */
# define RS_AUTHERR_SERVER		 16 	/* Request not authorized by server */
# define RS_BEING_DEACT			 16 	/* Image being deactivated */
# define RS_CANNOT_ACCESS_DATA		 16 	/* Cannot access configuration or VMRM measurement data */
# define RS_CANNOT_DELETE		 16 	/* Cannot delete image definition */
# define RS_CANNOT_REVOKE		 16 	/* Cannot revoke tag definition */
# define RS_CANNOT_SHARE		 16 	/* Image disk cannot be shared */
# define RS_DEV_NOT_ONLINE		 16 	/* Device not online */
# define RS_LIST_DESTROYED		 16 	/* Successful no more entries: list destroyed */
# define RS_NO_MATCH			 16 	/* Parameters don't match existing directory statement */
# define RS_NO_SHARING			 16 	/* Image disk sharing not allowed by target image definition */
# define RS_NOSAVE			 16 	/* Could not save segment */
# define RS_PTS_ENTRY_NOT_VALID		 16  	/* Parser entry not valid */
# define RS_TAG_LONG			 16 	/* Tag too long */
# define RS_VOLID_NOT_FOUND		 18 	/* Volid not found */
# define RS_IS_CONNECTED		 20 	/* Device already connected */
# define RS_NOT_AUTHORIZED		 20 	/* Not authorized for function */
# define RS_OWNER_NOT_ACTIVE		 20 	/* Owner of reqested LAN not active */
# define RS_PARM_LIST_NOT_VALID		 20 	/* Parameter list not valid */
# define RS_PW_FORMAT_NOT_SUPPORTED	 20 	/* Directory manager does not support password format */
# define RS_SHARE_DIFF_MODE		 20 	/* Image disk shared in different mode */
# define RS_VOLID_IN_USE		 20 	/* Volid is in use */
# define RS_TARGET_IMG_NOT_AUTH		 20 	/* Target Image not authorized to issue the command */
# define RS_PDISKS_SAME			 22 	/* Parm disk 1 and 2 are same */
# define RS_CONFLICTING_PARMS		 24 	/* Conflicting storage parameters */
# define RS_LAN_NAME_EXISTS		 24 	/* Same name as an existing LAN */
# define RS_LIST_NOT_FOUND		 24 	/* List not found */
# define RS_NO_SPACE			 24 	/* Image disk space not available */
# define RS_NOT_LOCKED			 24 	/* Image name is not locked  */
# define RS_PARM_DISK_LINK_ERR		 24 	/* Error linking parm disk (1 or 2)*/
# define RS_SFS_ERROR			 24 	/* Shared File System error */
# define RS_TYPE_NOT_SAME		 24 	/* Image device type not same as source */
# define RS_UPDATE_WRITE_ERROR		 24 	/* Configuration update could not write files */
# define RS_TAPE_NOT_ASSIGNED		 24 	/* Tape not assigned */
# define RS_VCPU_ALREADY_EXISTS		 24 	/* Virtual CPU already defined */
# define RS_VCPU_OUT_OF_RANGE		 28 	/* CPU beyond range defined in directory */
# define RS_DEV_INCOMPATIBLE		 28 	/* Incorrect device type */
# define RS_EMPTY			 28 	/* Return buffer is empty */
# define RS_FILE_NOT_FOUND		 28 	/* File not found */
# define RS_NO_MATCH_ON_SEARCH		 28 	/* No entries match search criteria */
# define RS_NOT_ALL			 28 	/* Some images in list not activated */
# define RS_OUTPUT_NOT_VALID		 28 	/* Output from function not valid */
# define RS_PARM_DISK_NOT_RW		 28 	/* Parm Disk (1 or 2) not R/W */
# define RS_PW_NEEDED			 28 	/* Image Disk does not have required password */
# define RS_SEGMENT_NOT_FOUND		 28 	/* Shared Storage Segment not found */
# define RS_SIZE_NOT_SAME		 28 	/* Image device size not same as source */
# define RS_DEV_NOT_SHARED		 28 	/* Device not shared */
# define RS_BAD_PW			 32 	/* Incorrect password specified for image disk */
# define RS_NOT_CONNECTED		 32 	/* Device not connected */
# define RS_NOT_IN_LIST			 32 	/* Name was not in list */
# define RS_SOME_NOT_DEACT		 32 	/* Some Images in list not deactivated */
# define RS_UPDATE_PROCESS_ERROR	 32 	/* Configuration update internal processer */
# define RS_SYS_CONF_NOT_FOUND		 32 	/* System configuration file not found on PARM disk */
# define RS_DEV_NOT_RESERVED		 32 	/* Device not reserved */
# define RS_REQRESP_NOT_VALID		 32 	/* Internal request error */
# define RS_SYS_CONF_BAD_DATA		 34 	/* Syntax Errors with original system configuration */
# define RS_IVS_NAME_NOT_DASD		 36 	/* Name not DASD (for ISD) */
# define RS_LENGTH_NOT_VALID		 36 	/* Length on input/output not valid */
# define RS_NAME_IN_LIST		 36 	/* Name is already in list  */
# define RS_NO_VOLUME			 36 	/* No such DASD vol mounted on system; Unable to determine dev type */
# define RS_SOME_NOT_RECYC		 36 	/* Some images in list not recycled */
# define RS_SYS_CONF_SYNTX_ERR		 36 	/* Syntax errors with system configuration update*/
# define RS_TIME_NOT_VALID		 36 	/* Force time for deactvation not valid */
# define RS_VSWITCH_EXISTS		 36 	/* VSwitch already exists */
# define RS_DEV_IO_ERROR		 36 	/* Device I/O error */
# define RS_NO_DIR_AUTH_TO_LINK		 36 	/* No directory authority to link */
# define RS_CPDISK_MODE_NOT_AVAIL	 38 	/* CP disk modes not available */
# define RS_PARM_DISK_FULL		 40 	/* Parm Disk (1 or 2) is full */
# define RS_VSWITCH_NOT_EXISTS		 40 	/* VSwitch doesn't exist */
# define RS_NWDEV_NOT_DETACHED		 40 	/* Device not detached */
# define RS_MULTIPLE			 40 	/* Multiple - multiple what? */
# define RS_SOCKET			 40 	/* Socket error */
# define RS_TYPE_NOT_SUPPORTED		 40	/* CPU type not supported on your system */
# define RS_PDISK_ACC_NOT_ALLOWED	 42 	/* Parm Disk 1 or 2 - access not allowed */
# define RS_ALREADY_AUTH		 44 	/* Image already granted */
# define RS_PDISK_PW_NOT_SUPPLIED	 44 	/* Parm Disk (1 or 2) password not supplied */
# define RS_DASD_IN_USE			 44 	/* DASD in use */
# define RS_IS_DISCONNECTED		 48 	/* Disconnected */
# define RS_PDISK_PW_INCORRECT		 46 	/* Parm Disk (1 or 2) password is incorrect */
# define RS_PARM_DISK_NOT_IN_SRVR_DIR    48 	/* Parm Disk (1 or 2) is not in server's user directory */
# define RS_VLAN_NOT_FOUND		 48 	/* vLAN not found */
# define RS_MAX_CONN			 52 	/* Max connections reached */
# define RS_CPRELEASE_ERROR		 50 	/* CPRELEASE error for Parm Disk (1 or 2) */
# define RS_CPACCESS_ERROR		 52 	/* CPACCESS error for Parm Disk (1 or 2) */
# define RS_DEF_VSWITCH_EXISTS		 54 	/* DEFINE exists in System Config */
# define RS_GRANT_EXISTS		 56 	/* GRANT exists in System Config */
# define RS_REVOKE_FAILED		 58 	/* MODIFY does not exist in System Config */
# define RS_DEF_VSWITCH_NOT_EXIST	 60 	/* DEFINE does not exist in System config */
# define RS_VSWITCH_CONFLICT		 62 	/* VSwitch conflict for set API */
# define RS_DEF_MOD_MULTI_FOUND		 64 	/* Multiple Define or Modify statements found */
# define RS_DEF_MOD_MULTI_ERASED	 66 	/* Multiple Define or Modify statements erased */
# define RS_DATABASE			 68 	/* Unable to access database */
# define RS_UNKNOWN			 96 	/* Connect request failed for unknown reason */
# define RS_RETRY			 99 	/* Suggest retry API call */
# define RS_ASYNC_OP_SUCCEEDED		100 	/* Asynch operation succeeded */
# define RS_ASYNC_OP_IN_PROGRESS	104 	/* Asynch operation in progress */
# define RS_ASYNC_OP_FAILED		108 	/* Asynch operation failed */ 
# define RS_CLASS_S_ALREADY_DEFINED	299 	/* DEFSEG class S file exists */
# define RS_NOT_YET_AVAILABLE		999 	/* Function not yet available */
# define RS_DEVNO_REQUIRES_FREE_DISK	1157 	/* DEVNO parameter requires the device to be a free volume*/
# define RS_INVALID_LANID		2783 	/* invalid LAN id */
# define RS_INVALID_LAN_PARM		2795 	/* LAN parameter for this LAN id */ 
# define RS_RELOCATION_ERRORS		3000 	/* Relocation error(s) encountered */
# define RS_NO_RELOCATION_ACTIVE	3001 	/* No active relocations found */
# define RS_INVALID_PARAMETER		3002 	/* Invalid parameter name */
# define RS_INVALID_OPERAND		3003 	/* Invalid parameter operand */
# define RS_MISSING_PARAMETER		3004 	/* Missing parameter */
# define RS_NOT_IN_SSI			3005 	/* System not in an SSI */
# define RS_SSI_UNSTABLE		3006 	/* SSI is not in a stable state */
# define RS_SSI_CPOWNED_CONFLICT	3007 	/* The volume or slot is not on all systems in SSI */
# define RS_NOT_SSI_MEMBER		3008 	/* Not a member of an SSI cluster */
# define RS_REPAIR_IPL_PARAM		3009 	/* IPLed with the REPAIR IPL param */
# define RS_RELOCATION_MODIFY_ERROR	3010 	/* VMRELOCATE Modify error */
# define RS_NO_SLOTS_AVAILABLE		3011 	/* No unique CP_OWNED slot available on system and in config */
# define RS_VOLUME_NOT_FOUND		3012 	/* VOLUME cannot be found */
# define RS_VOLUME_OFFLINE		3013 	/* The volume is offline */
# define RS_SHARE_UNSUPPORTED		3014 	/* Volume does not support sharing */

/*
 * API functional level
 */
# define RS_530  			  0	/* 5.3.0 level */
# define RS_540				540	/* 5.4.0 level */
# define RS_610				610	/* 6.1.0 level */
# define RS_611				611	/* 6.1.1 level */
# define RS_620				620	/* 6.2.0 level */
# define RS_621				621	/* 6.2.1 level */
# define RS_630				630	/* 6.3.0 level */

/*
 * SMAPI Operations
 */
# define Asynchronous_Notification_Disable_DM			"Asynchronous_Notification_Disable_DM"
# define Asynchronous_Notification_Enable_DM			"Asynchronous_Notification_Enable_DM"
# define Asynchronous_Notification_Query_DM			"Asynchronous_Notification_Query_DM"
# define Authorization_List_Add					"Authorization_List_Add"
# define Authorization_List_Query				"Authorization_List_Query"
# define Authorization_List_Remove				"Authorization_List_Remove"
# define Check_Authentication					"Check_Authentication"
# define Delete_ABEND_Dump					"Delete_ABEND_Dump"
# define Directory_Manager_Local_Tag_Define_DM			"Directory_Manager_Local_Tag_Define_DM"
# define Directory_Manager_Local_Tag_Delete_DM			"Directory_Manager_Local_Tag_Delete_DM"
# define Directory_Manager_Local_Tag_Query_DM			"Directory_Manager_Local_Tag_Query_DM"
# define Directory_Manager_Local_Tag_Set_DM			"Directory_Manager_Local_Tag_Set_DM"
# define Directory_Manager_Search_DM				"Directory_Manager_Search_DM"
# define Directory_Manager_Task_Cancel_DM			"Directory_Manager_Task_Cancel_DM"
# define Event_Stream_Add					"Event_Stream_Add"
# define Event_Subscribe					"Event_Subscribe"
# define Event_Unsubscribe					"Event_Unsubscribe"
# define Image_Activate						"Image_Activate"
# define Image_Active_Configuration_Query			"Image_Active_Configuration_Query"
# define Image_CPU_Define					"Image_CPU_Define"
# define Image_CPU_Define_DM					"Image_CPU_Define_DM"
# define Image_CPU_Delete					"Image_CPU_Delete"
# define Image_CPU_Delete_DM					"Image_CPU_Delete_DM"
# define Image_CPU_Query					"Image_CPU_Query"
# define Image_CPU_Query_DM					"Image_CPU_Query_DM"
# define Image_CPU_Set_Maximum_DM				"Image_CPU_Set_Maximum_DM"
# define Image_Create_DM					"Image_Create_DM"
# define Image_Deactivate					"Image_Deactivate"
# define Image_Definition_Async_Updates				"Image_Definition_Async_Updates"
# define Image_Definition_Create_DM				"Image_Definition_Create_DM"
# define Image_Definition_Delete_DM				"Image_Definition_Delete_DM"
# define Image_Definition_Query_DM				"Image_Definition_Query_DM"
# define Image_Definition_Update_DM				"Image_Definition_Update_DM"
# define Image_Delete_DM					"Image_Delete_DM"
# define Image_Device_Dedicate					"Image_Device_Dedicate"
# define Image_Device_Dedicate_DM				"Image_Device_Dedicate_DM"
# define Image_Device_Reset					"Image_Device_Reset"
# define Image_Device_Undedicate				"Image_Device_Undedicate"
# define Image_Device_Undedicate_DM				"Image_Device_Undedicate_DM"
# define Image_Disk_Copy					"Image_Disk_Copy"
# define Image_Disk_Copy_DM					"Image_Disk_Copy_DM"
# define Image_Disk_Create					"Image_Disk_Create"
# define Image_Disk_Create_DM					"Image_Disk_Create_DM"
# define Image_Disk_Delete					"Image_Disk_Delete"
# define Image_Disk_Delete_DM					"Image_Disk_Delete_DM"
# define Image_Disk_Query					"Image_Disk_Query"
# define Image_Disk_Share					"Image_Disk_Share"
# define Image_Disk_Share_DM					"Image_Disk_Share_DM"
# define Image_Disk_Unshare					"Image_Disk_Unshare"
# define Image_Disk_Unshare_DM					"Image_Disk_Unshare_DM"
# define Image_IPL_Delete_DM					"Image_IPL_Delete_DM"
# define Image_IPL_Query_DM					"Image_IPL_Query_DM"
# define Image_IPL_Set_DM					"Image_IPL_Set_DM"
# define Image_Lock_DM						"Image_Lock_DM"
# define Image_Name_Query_DM					"Image_Name_Query_DM"
# define Image_Password_Set_DM					"Image_Password_Set_DM"
# define Image_Query_Activate_Time				"Image_Query_Activate_Time"
# define Image_Query_DM						"Image_Query_DM"
# define Image_Recycle						"Image_Recycle"
# define Image_Replace_DM					"Image_Replace_DM"
# define Image_SCSI_Characteristics_Define_DM			"Image_SCSI_Characteristics_Define_DM"
# define Image_SCSI_Characteristics_Query_DM			"Image_SCSI_Characteristics_Query_DM"
# define Image_Status_Query					"Image_Status_Query"
# define Image_Unlock_DM					"Image_Unlock_DM"
# define Image_Volume_Add					"Image_Volume_Add"
# define Image_Volume_Delete					"Image_Volume_Delete"
# define Image_Volume_Share					"Image_Volume_Share"
# define Image_Volume_Space_Define_DM				"Image_Volume_Space_Define_DM"
# define Image_Volume_Space_Define_Extended_DM			"Image_Volume_Space_Define_Extended_DM"
# define Image_Volume_Space_Query_DM				"Image_Volume_Space_Query_DM"
# define Image_Volume_Space_Query_Extended_DM			"Image_Volume_Space_Query_Extended_DM"
# define Image_Volume_Space_Remove_DM				"Image_Volume_Space_Remove_DM"
# define Metadata_Delete					"Metadata_Delete"
# define Metadata_Get						"Metadata_Get"
# define Metadata_Set						"Metadata_Set"
# define Name_List_Add						"Name_List_Add"
# define Name_List_Destroy					"Name_List_Destroy"
# define Name_List_Query					"Name_List_Query"
# define Name_List_Remove					"Name_List_Remove"
# define Page_or_Spool_Volume_Add				"Page_or_Spool_Volume_Add"
# define Process_ABEND_Dump					"Process_ABEND_Dump"
# define Profile_Create_DM					"Profile_Create_DM"
# define Profile_Delete_DM					"Profile_Delete_DM"
# define Profile_Lock_DM					"Profile_Lock_DM"
# define Profile_Query_DM					"Profile_Query_DM"
# define Profile_Replace_DM					"Profile_Replace_DM"
# define Profile_Unlock_DM					"Profile_Unlock_DM"
# define Prototype_Create_DM					"Prototype_Create_DM"
# define Prototype_Delete_DM					"Prototype_Delete_DM"
# define Prototype_Name_Query_DM				"Prototype_Name_Query_DM"
# define Prototype_Query_DM					"Prototype_Query_DM"
# define Prototype_Replace_DM					"Prototype_Replace_DM"
# define Query_ABEND_Dump					"Query_ABEND_Dump"
# define Query_All_DM						"Query_All_DM"
# define Query_API_Functional_Level				"Query_API_Functional_Level"
# define Query_Asynchronous_Operation_DM			"Query_Asynchronous_Operation_DM"
# define Query_Directory_Manager_Level_DM			"Query_Directory_Manager_Level_DM"
# define Response_Recovery					"Response_Recovery"
# define Shared_Memory_Access_Add_DM				"Shared_Memory_Access_Add_DM"
# define Shared_Memory_Access_Query_DM				"Shared_Memory_Access_Query_DM"
# define Shared_Memory_Access_Remove_DM				"Shared_Memory_Access_Remove_DM"
# define Shared_Memory_Create					"Shared_Memory_Create"
# define Shared_Memory_Delete					"Shared_Memory_Delete"
# define Shared_Memory_Query					"Shared_Memory_Query"
# define Shared_Memory_Replace					"Shared_Memory_Replace"
# define SSI_Query						"SSI_Query"
# define Static_Image_Changes_Activate_DM			"Static_Image_Changes_Activate_DM"
# define Static_Image_Changes_Deactivate_DM			"Static_Image_Changes_Deactivate_DM"
# define Static_Image_Changes_Immediate_DM			"Static_Image_Changes_Immediate_DM"
# define System_Config_Syntax_Check				"System_Config_Syntax_Check"
# define System_Disk_Accessibility				"System_Disk_Accessibility"
# define System_Disk_Add					"System_Disk_Add"
# define System_Disk_Query					"System_Disk_Query"
# define System_FCP_Free_Query					"System_FCP_Free_Query"
# define System_Performance_Threshold_Disable			"System_Performance_Threshold_Disable"
# define System_Performance_Threshold_Enable			"System_Performance_Threshold_Enable"
# define System_SCSI_Disk_Add					"System_SCSI_Disk_Add"
# define System_SCSI_Disk_Delete				"System_SCSI_Disk_Delete"
# define System_SCSI_Disk_Query					"System_SCSI_Disk_Query"
# define System_WWPN_Query					"System_WWPN_Query"
# define Virtual_Channel_Connection_Create			"Virtual_Channel_Connection_Create"
# define Virtual_Channel_Connection_Create_DM			"Virtual_Channel_Connection_Create_DM"
# define Virtual_Channel_Connection_Delete			"Virtual_Channel_Connection_Delete"
# define Virtual_Channel_Connection_Delete_DM			"Virtual_Channel_Connection_Delete_DM"
# define Virtual_Network_Adapter_Connect_LAN			"Virtual_Network_Adapter_Connect_LAN"
# define Virtual_Network_Adapter_Connect_LAN_DM			"Virtual_Network_Adapter_Connect_LAN_DM"
# define Virtual_Network_Adapter_Connect_Vswitch		"Virtual_Network_Adapter_Connect_Vswitch"
# define Virtual_Network_Adapter_Connect_Vswitch_DM		"Virtual_Network_Adapter_Connect_Vswitch_DM"
# define Virtual_Network_Adapter_Connect_Vswitch_Extended	"Virtual_Network_Adapter_Connect_Vswitch_Extended"
# define Virtual_Network_Adapter_Create				"Virtual_Network_Adapter_Create"
# define Virtual_Network_Adapter_Create_DM			"Virtual_Network_Adapter_Create_DM"
# define Virtual_Network_Adapter_Create_Extended		"Virtual_Network_Adapter_Create_Extended"
# define Virtual_Network_Adapter_Create_Extended_DM		"Virtual_Network_Adapter_Create_Extended_DM"
# define Virtual_Network_Adapter_Delete				"Virtual_Network_Adapter_Delete"
# define Virtual_Network_Adapter_Delete_DM			"Virtual_Network_Adapter_Delete_DM"
# define Virtual_Network_Adapter_Disconnect			"Virtual_Network_Adapter_Disconnect"
# define Virtual_Network_Adapter_Disconnect_DM			"Virtual_Network_Adapter_Disconnect_DM"
# define Virtual_Network_Adapter_Query				"Virtual_Network_Adapter_Query"
# define Virtual_Network_LAN_Access				"Virtual_Network_LAN_Access"
# define Virtual_Network_LAN_Access_Query			"Virtual_Network_LAN_Access_Query"
# define Virtual_Network_LAN_Create				"Virtual_Network_LAN_Create"
# define Virtual_Network_LAN_Delete				"Virtual_Network_LAN_Delete"
# define Virtual_Network_LAN_Query				"Virtual_Network_LAN_Query"
# define Virtual_Network_OSA_Query				"Virtual_Network_OSA_Query"
# define Virtual_Network_VLAN_Query_Stats			"Virtual_Network_VLAN_Query_Stats"
# define Virtual_Network_Vswitch_Create				"Virtual_Network_Vswitch_Create"
# define Virtual_Network_Vswitch_Create_Extended		"Virtual_Network_Vswitch_Create_Extended"
# define Virtual_Network_Vswitch_Delete				"Virtual_Network_Vswitch_Delete"
# define Virtual_Network_Vswitch_Delete_Extended		"Virtual_Network_Vswitch_Delete_Extended"
# define Virtual_Network_Vswitch_Query				"Virtual_Network_Vswitch_Query"
# define Virtual_Network_Vswitch_Query_Extended			"Virtual_Network_Vswitch_Query_Extended"
# define Virtual_Network_Vswitch_Query_Stats			"Virtual_Network_Vswitch_Query_Stats"
# define Virtual_Network_Vswitch_Set				"Virtual_Network_Vswitch_Set"
# define Virtual_Network_Vswitch_Set_Extended			"Virtual_Network_Vswitch_Set_Extended"
# define VMRELOCATE						"VMRELOCATE"
# define VMRELOCATE_Image_Attributes				"VMRELOCATE_Image_Attributes"
# define VMRELOCATE_Modify					"VMRELOCATE_Modify"
# define VMRELOCATE_Status					"VMRELOCATE_Status"
# define VMRM_Configuration_Query				"VMRM_Configuration_Query"
# define VMRM_Configuration_Update				"VMRM_Configuration_Update"
# define VMRM_Measurement_Query					"VMRM_Measurement_Query"

# define FORCE_IMMED	"IMMED"
# define FORCE_WITHIN	"WITHIN 99999"

/*
 * Standard fields in a response from SMAPI server
 */
typedef struct {
	uint32_t outLen;		/* Length of output data */
	uint32_t reqId;			/* Request ID to which response refers */
	uint32_t rc;			/* Return code */
	uint32_t reason;		/* Reason code */
} smapiOutHeader_t;

typedef struct {
	smapiOutHeader_t hdr;		/* Output header */
	uint32_t lArray;		/* Length of array output */
	char     array[0];		/* Start of array output */
} smapiArrayHeader_t;
 
/*
 * Structures returned from Image_Active_Configuration_Query
 */
typedef struct {
	smapiOutHeader_t hdr;
	int32_t memSize;
	uint8_t	memUnit;
# define SMAPI_MEMUNIT_KB	1
# define SMAPI_MEMUNIT_MB	2
# define SMAPI_MEMUNIT_GB	3
	uint8_t	shareType;	
# define SMAPI_SHRTYPE_R	1
# define SMAPI_SHRTYPE_A	2
	int32_t	lShare;
	char	share[0];
} __attribute__ ((__packed__)) zvm_actImgHdr_t;

typedef struct {
	char	share[5];
} zvm_actImgShr_t;

typedef struct {
	int32_t	nCPU;
	int32_t	lCPUArray;
	char	cpuArray[0];
} zvm_actImgCPUArr_t;

typedef struct {
	int32_t	lCPUStruct;
	char	cpuStruct[0];
} zvm_actImgCPUHdr_t;

typedef struct {
	int32_t	cpuNumber;
	int32_t	lCPUId;
	char	cpuId[16];
} zvm_actImgCPUId_t;

typedef struct {
	uint8_t	cpuState;
# define SMAPI_CPUSTATE_BASE	1
# define SMAPI_CPUSTATE_STOPPED	2
# define SMAPI_CPUSTATE_CHECK	3
# define SMAPI_CPUSTATE_ACTIVE	4
	int32_t	lDevArray;
	char	devArray[0];
} __attribute__ ((__packed__)) zvm_actImgCPUState_t;

typedef struct {
	int32_t	lDevStruct;
	char	devStruct[0];
} zvm_actImgDevHdr_t;

typedef struct {
	uint8_t	devType;
# define SMAPI_DEVTYPE_CONS	1
# define SMAPI_DEVTYPE_RDR	2
# define SMAPI_DEVTYPE_PUN	3
# define SMAPI_DEVTYPE_PRT	4
# define SMAPI_DEVTYPE_DASD	5
	int32_t	lDevAddr;
	uint8_t	devAddr[4];
} __attribute__ ((__packed__)) zvm_actImgDev_t;

typedef struct {
	int	 sd;
	int	 reason;
	uint32_t timeOut;
	uint32_t delay;
	char	 target[9];
	char	 authUser[9];
	char	 authPass[9];
	char	 node[9];
	char	 smapiSrv[128];
} zvm_driver_t;

int zvm_smapi_open(zvm_driver_t *);
int zvm_smapi_send(zvm_driver_t *, void *, uint32_t *, int32_t);
int zvm_smapi_recv(zvm_driver_t *, void **, int32_t *);
int zvm_smapi_close(zvm_driver_t *);
int zvm_smapi_imageActivate(zvm_driver_t *);
int zvm_smapi_imageActiveQuery(zvm_driver_t *);
int zvm_smapi_imageDeactivate(zvm_driver_t *);
int zvm_smapi_imageRecycle(zvm_driver_t *);
int zvm_smapi_imageQuery(zvm_driver_t *);

#endif /* FENCE_ZVM_H */
