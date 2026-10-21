/* Native AP text-label seam only. No RO writes, metadata changes or colour hooks.
 * uint32 resource -> stable imported ASCII name after final CP seal acknowledgment.
 * Original TextSprite overload remains the fallback for all other resources.
 */
typedef unsigned u32;
extern const char *r5_native12_name(unsigned number);
extern void name_id(void *sprite, u32 resource);
extern void name_char(void *sprite, const char *text);
unsigned r5_native12_number_for_resource(u32 resource) {
    switch (resource) {
    case 0x021c6e0d: return 1; /* ST */
    case 0x021c6e10: return 2; /* PT */
    case 0x021c6e14: return 3; /* NT */
    case 0x021c6e19: return 4; /* VV */
    case 0x021c6e0e: return 5; /* VV2 */
    case 0x021c6e0c: return 6; /* FL */
    case 0x021c6e0b: return 7; /* FL2 */
    case 0x021c6e0a: return 8; /* FL3 */
    case 0x021c6e11: return 9; /* IN */
    case 0x021c6e12: return 10; /* SH */
    case 0x021c6e15: return 11; /* BW */
    case 0x021c6e13: return 12; /* SE */
    default: return 0;
    }
}
void r5_native12_text_label(void *sprite, u32 resource) {
    unsigned n = r5_native12_number_for_resource(resource);
    const char *name = n ? r5_native12_name(n) : (const char *)0;
    if (name) name_char(sprite, name);
    else name_id(sprite, resource);
}
