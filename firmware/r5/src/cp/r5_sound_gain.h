#ifndef R5_SOUND_GAIN_H
#define R5_SOUND_GAIN_H
typedef unsigned int r5ss_gain_u32;
/* Private identity only. Native registry/volume/path and descriptor are never
 * written. Original primary clear covers this32B after completion state. */
struct r5ss_gain_binding {
 volatile r5ss_gain_u32 version;
 r5ss_gain_u32 tag,serial,lo,hi,bytes,valid,reserved;
};
int r5ss_cp_gain_bind(const unsigned char *,const r5ss_gain_u32 *,r5ss_gain_u32);
r5ss_gain_u32 r5ss_cp_gain_scalar(r5ss_gain_u32,r5ss_gain_u32,
                                 const volatile r5ss_gain_u32 *,r5ss_gain_u32);
#endif
