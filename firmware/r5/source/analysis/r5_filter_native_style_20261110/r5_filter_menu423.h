#ifndef R5_FILTER_MENU423_H
#define R5_FILTER_MENU423_H
#include <stdint.h>
#define R5_FILTER_MENU_ID 0x635u
#define R5_FILTER_ROW_FIRST 0x1600u
#define R5_FILTER_ROW_COUNT 13u
#define R5_FILTER_TITLE_RESOURCE 0x02ff4230u
#define R5_FILTER_SHORT_RESOURCE 0x02ff4300u
#define R5_FILTER_FULL_RESOURCE 0x02ff4400u
extern unsigned char r5_filter_menu_descriptor[0xc0];
extern unsigned char r5_filter_menu_rows[R5_FILTER_ROW_COUNT][0x80];
/* Called only from the original registry constructor call sites. */
void r5_filter_menu_register(void *,const void *,const void *);
void r5_filter_rows_register(void *,const void *,const void *);
/* Same virtual-method ABI as the original native menu utilities. */
unsigned r5_filter_menu_normalize(void *,unsigned);
unsigned r5_filter_row_normalize(void *,unsigned);
unsigned r5_filter_row_available(void *,unsigned);
unsigned r5_filter_row_available_direct(void *,unsigned);
unsigned r5_filter_row_parent(void *,unsigned);
unsigned r5_filter_menu_selected(void);
void r5_filter_menu_select(unsigned);
const char *r5_filter_menu_text(unsigned);
/* Replaces only the resource-overload call at 0x1885b38. */
void r5_filter_menu_name_draw(void *,unsigned);
#endif
