#include "sd_native_persist.h"

static int persist_read_ops(const struct r5_persist_ops *ops) {
    return ops && ops->open_read && ops->read_file && ops->close_file;
}
static int persist_disjoint(const void *a, size_t an, const void *b, size_t bn) {
    uintptr_t av=(uintptr_t)a,bv=(uintptr_t)b;
    return av>=bv ? av-bv>=bn : bv-av>=an;
}

int r5_load_persisted_look(const struct r5_persist_ops *ops,
    struct r5_look_set *out, uint8_t *scratch, size_t capacity) {
    uintptr_t handle=0;
    size_t used=0,actual,i;
    int status,closed;
    if (!persist_read_ops(ops) || !out || !scratch || capacity<R5_LOOK_MAX+1 ||
        !persist_disjoint(out,sizeof(*out),scratch,R5_LOOK_MAX+1)) return R5_INVALID;
    status=ops->open_read(ops->context,R5_LOOK_STORE,&handle);
    if (status==1) return R5_ABSENT;
    if (status) return R5_IO_ERROR;
    do {
        size_t wanted=R5_LOOK_MAX+1-used;
        if (wanted>512) wanted=512;
        actual=0;
        status=ops->read_file(ops->context,handle,scratch+used,wanted,&actual);
        if (status || actual>wanted) {status=R5_IO_ERROR;break;}
        used+=actual;
    } while (actual && used<R5_LOOK_MAX+1);
    closed=ops->close_file(ops->context,handle);
    if (status || closed) return R5_IO_ERROR;
    if (used>R5_LOOK_MAX) return R5_INVALID;
    /* Decoder performs a complete validation pass before any writes. Preserve
     * the caller on invalid input, then clear unlisted slots after success. */
    status=r5_decode_look_file(scratch,used,out);
    if (status!=R5_IMPORTED) return status;
    out->valid_mask=(uint32_t)scratch[24] | (uint32_t)scratch[25]<<8 |
        (uint32_t)scratch[26]<<16 | (uint32_t)scratch[27]<<24;
    for (i=0;i<R5_LOOK_SLOTS;i++) if (!(out->valid_mask & (1u<<i))) {
        uint8_t *p=(uint8_t *)&out->look[i];
        size_t j;
        for (j=0;j<sizeof(out->look[i]);j++) p[j]=0;
    }
    return R5_IMPORTED;
}

int r5_publish_staged_look(const struct r5_persist_ops *ops,
    const struct r5_look_set *set, uint8_t *scratch, size_t capacity) {
    uint8_t chunk[128];
    uintptr_t handle=0,directory=0;
    size_t length,used=0,actual,i;
    int status,closed,result=R5_PUBLISHED;
    if (!persist_read_ops(ops) || !ops->open_directory || !ops->rename_file ||
        !ops->sync_directory) return R5_PUBLISH_INVALID;
    length=r5_encode_look_file(set,scratch,capacity);
    if (!length) return R5_PUBLISH_INVALID;
    status=ops->open_read(ops->context,R5_LOOK_PENDING,&handle);
    if (status) return R5_PUBLISH_IO_ERROR;
    /* Bound even an adversarial short-reader: at most length+1 calls, 7329
     * bytes. One extra byte distinguishes exact content from trailing data. */
    do {
        size_t wanted=length+1-used;
        if (wanted>sizeof(chunk)) wanted=sizeof(chunk);
        actual=0;
        status=ops->read_file(ops->context,handle,chunk,wanted,&actual);
        if (status || actual>wanted) {result=R5_PUBLISH_IO_ERROR;break;}
        if (used+actual>length) {result=R5_PUBLISH_MISMATCH;break;}
        for (i=0;i<actual;i++) if (chunk[i]!=scratch[used+i]) {
            result=R5_PUBLISH_MISMATCH;break;
        }
        if (result!=R5_PUBLISHED) break;
        used+=actual;
    } while (actual);
    closed=ops->close_file(ops->context,handle);
    if (closed) return R5_PUBLISH_IO_ERROR;
    if (result!=R5_PUBLISHED) return result;
    if (used!=length) return R5_PUBLISH_MISMATCH;
    if (ops->open_directory(ops->context,R5_LOOK_DIRECTORY,&directory)) return R5_PUBLISH_IO_ERROR;
    status=ops->rename_file(ops->context,R5_LOOK_PENDING,R5_LOOK_STORE);
    if (status) result=R5_PUBLISH_UNCERTAIN;
    else if (ops->sync_directory(ops->context,directory)) result=R5_PUBLISH_UNCERTAIN;
    if (ops->close_file(ops->context,directory) && result==R5_PUBLISHED)
        result=R5_PUBLISHED_CLOSE_ERROR;
    return result;
}
