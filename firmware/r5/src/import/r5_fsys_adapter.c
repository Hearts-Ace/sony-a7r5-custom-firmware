#include "r5_fsys_adapter.h"

static int same(const char *a, const char *b) {
    unsigned i;
    if (!a || !b) return 0;
    for (i=0;i<sizeof(R5_LOOK_SD_FILE);i++) if (a[i]!=b[i]) return 0;
    return 1;
}

int r5_fsys_reader_init(struct r5_fsys_reader *r,
        const struct r5_fsys_api *api, char drive) {
    unsigned i;
    if (!r || !api || !api->open || !api->read || !api->close ||
            drive<'A' || drive>'Z') return R5_IO_ERROR;
    r->api=*api;r->handle=0;r->opened=0;r->remaining=0;
    r->calls_remaining=0;r->last_native_status=0;
    r->path[0]=drive;r->path[1]=':';r->path[2]='/';
    for (i=0;i<sizeof(R5_LOOK_SD_FILE);i++) r->path[3+i]=R5_LOOK_SD_FILE[i];
    return 0;
}

int r5_fsys_open_file(void *context, const char *name, uintptr_t *out) {
    struct r5_fsys_reader *r=context;
    uint64_t handle=0;
    int status;
    if (!r || !out || r->opened || !same(name,R5_LOOK_SD_FILE)) return R5_IO_ERROR;
    /* Mode 1 is the original AP SD cube-reader's read-only mode. */
    status=r->api.open(r->path,1,&handle);r->last_native_status=status;
    if (status) return R5_IO_ERROR;
    r->handle=handle;r->opened=1;r->remaining=R5_LOOK_MAX+1;
    r->calls_remaining=64;*out=(uintptr_t)handle;
    return 0;
}

int r5_fsys_read_file(void *context, uintptr_t handle, uint8_t *dst,
        size_t capacity, size_t *actual) {
    struct r5_fsys_reader *r=context;
    uint64_t count=0;
    size_t request;
    int status;
    if (!actual) return R5_IO_ERROR;
    *actual=0;
    if (!r || !r->opened || handle!=(uintptr_t)r->handle || !dst ||
            !capacity || !r->calls_remaining || !r->remaining) return R5_IO_ERROR;
    request=capacity;
    if (request>1024) request=1024;
    if (request>r->remaining) request=r->remaining;
    r->calls_remaining--;
    status=r->api.read(r->handle,dst,request,&count);r->last_native_status=status;
    if (status || count>request) return R5_IO_ERROR;
    r->remaining-=(size_t)count;*actual=(size_t)count;
    return 0;
}

int r5_fsys_close_file(void *context, uintptr_t handle) {
    struct r5_fsys_reader *r=context;
    int status;
    if (!r || !r->opened || handle!=(uintptr_t)r->handle) return R5_IO_ERROR;
    /* Invalidate locally before native close, so a failed close is not retried
     * against a possibly reused native handle. */
    r->opened=0;r->remaining=0;r->calls_remaining=0;
    status=r->api.close(r->handle);r->last_native_status=status;
    return status ? R5_IO_ERROR : 0;
}
