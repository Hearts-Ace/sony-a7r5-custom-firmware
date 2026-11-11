#ifndef R5_SOUND_MENU437_H
#define R5_SOUND_MENU437_H
#include <stdint.h>
/* 4.36 owns MID635 and rows1600..160c. Sound lives in its own range. */
#define R5SOUND_MENU_ID 0x636u
#define R5SOUND_MAX_FILES 60u
#define R5SOUND_ROW_FIRST 0x1610u
#define R5SOUND_ROW_COUNT (R5SOUND_MAX_FILES+1u)
#define R5SOUND_TITLE_RESOURCE 0x02ff4600u
#define R5SOUND_NAME_RESOURCE 0x02ff4601u
#define R5SOUND_HELP_RESOURCE 0x02ff4640u
#define R5SOUND_VOLUME_MENU_ID 0x637u
#define R5SOUND_VOLUME_ROW_FIRST 0x1650u
#define R5SOUND_VOLUME_ROW_COUNT 10u
#define R5SOUND_VOLUME_TITLE_RESOURCE 0x02ff4650u
#define R5SOUND_VOLUME_NAME_RESOURCE 0x02ff4651u
#define R5SOUND_VOLUME_HELP_RESOURCE 0x02ff465bu
extern unsigned char r5sound_menu_descriptor[0xc0];
extern unsigned char r5sound_menu_rows[R5SOUND_ROW_COUNT][0x80];
extern unsigned char r5sound_volume_descriptor[0xc0];
void r5sound_menu_register_extra(void *);
void r5sound_rows_register_extra(void *);
void r5sound_menu_catalog_changed(void);
unsigned r5sound_menu_row_available(unsigned);
unsigned r5sound_menu_selected(void);
void r5sound_menu_stage(unsigned);
int r5sound_menu_commit(unsigned);
const char *r5sound_menu_text(unsigned);
unsigned r5sound_volume_menu_get(void);
void r5sound_volume_menu_stage(unsigned);
int r5sound_volume_menu_commit(unsigned);
/* GUI thread only: consume worker completion/canceled preview once. */
unsigned r5sound_menu_gui_changed(void);
/* Storage/runtime owns this API. No callback here does IO or CP requests.
 * count excludes OFF; selected is the committed effective index, not pending.
 * Catalog names must remain valid and immutable while a native menu is open.
 * index0 is OFF, index1..count are stored WAVs. Requests enqueue only. */
unsigned r5sound_count(void);
const char *r5sound_name(unsigned);
unsigned r5sound_selected(void);
int r5sound_request(unsigned);
const char *r5sound_status(void);
unsigned r5sound_volume_get(void);
int r5sound_volume_blocked(void);
int r5sound_volume_enqueue(unsigned);
unsigned r5sound_revision(void);
#endif
