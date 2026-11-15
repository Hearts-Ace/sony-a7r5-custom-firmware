#ifndef R5_FILTER_IO_H
#define R5_FILTER_IO_H
#include <stdint.h>
#include <stddef.h>
#include "r5_filter_file.h"
#define R5_LOOK_MAX R5F_MAX
#define R5_LOOK_STORE "/usr/data/lut/R5NATIVE.BIN"
#define R5_LOOK_PENDING "/usr/data/lut/R5NATIVE.NEW"
#define R5_LOOK_DIRECTORY "/usr/data/lut"
#define R5_LOOK_SD_FILE "R5NATIVE.BIN"
enum r5_result {R5_IMPORTED=0,R5_ABSENT=1,R5_INVALID=2,R5_IO_ERROR=3,R5_BUSY=4,R5_COMMIT_ERROR=5,R5_UNCHANGED=6};
#endif
