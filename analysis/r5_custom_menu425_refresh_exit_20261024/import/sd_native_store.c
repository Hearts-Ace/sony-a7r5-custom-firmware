#include "sd_native_store.h"

int r5_stage_look_store(const struct r5_stage_ops *ops, const struct r5_look_set *set,
    uint8_t *scratch, size_t capacity) {
    uintptr_t handle=0;
    size_t length,used=0,actual;
    int status,failed=0;
    if (!ops || !ops->create_exclusive || !ops->write_file || !ops->sync_file ||
        !ops->close_file || !ops->unlink_file) return R5_STAGE_INVALID;
    length=r5_encode_look_file(set,scratch,capacity);
    if (!length) return R5_STAGE_INVALID;
    status=ops->create_exclusive(ops->context,R5_LOOK_PENDING,&handle);
    if (status) return status==2 ? R5_STAGE_BUSY : R5_STAGE_IO_ERROR;
    while (used<length) {
        actual=0;
        status=ops->write_file(ops->context,handle,scratch+used,length-used,&actual);
        if (status || !actual || actual>length-used) {failed=1;break;}
        used+=actual;
    }
    if (!failed && ops->sync_file(ops->context,handle)) failed=1;
    if (ops->close_file(ops->context,handle)) failed=1;
    if (!failed) return R5_STAGE_READY;
    return ops->unlink_file(ops->context,R5_LOOK_PENDING) ?
        R5_STAGE_CLEANUP_ERROR : R5_STAGE_IO_ERROR;
}
