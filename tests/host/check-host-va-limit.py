#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# With the Madeira Converter Exception in LICENSE-EXCEPTION.md.
# Added for private iDeck-BCD, 2026-10-19.
"""Run production host-limit selection against controlled OS replies; no Wine/game.

The owner's map ended at 0x7180000000 while the hint walk advertised 0x8000000000.
Compile the actual get_host_addr_space_limit and user-limit clamp, with only the
OS query/mmap boundary mocked. This does not prove contiguous space for a game.
Run only after explicit authorization for compilation/test execution.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / "build/ntdll-unix/virtual_ios.c").read_text()


def production_function(declaration):
    start = source.index(declaration + "\n{")
    return source[start:source.index("\n}\n", start) + 3]


harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/types.h>
typedef uintptr_t UINT_PTR;
typedef unsigned int mach_msg_type_number_t;
typedef int *task_info_t;
typedef struct { uint64_t min_address, max_address; } task_vm_info_data_t;
#define TASK_VM_INFO 22
#define TASK_VM_INFO_REV2_COUNT 4
#define TASK_VM_INFO_COUNT 4
#define KERN_SUCCESS 0
static uintptr_t walk_stop, reply_min, reply_max;
static unsigned reply_count;
static int reply_status;
static size_t host_page_size = 16384, host_page_mask = 16383;
static void *host_addr_space_limit, *user_space_limit;
static unsigned mmap_calls;
static int mach_task_self(void) { return 1; }
static int task_info(int task, int flavor, task_info_t out, mach_msg_type_number_t *count) {
    (void)task; assert(flavor == TASK_VM_INFO);
    assert(*count == TASK_VM_INFO_COUNT);
    if (reply_status) return reply_status;
    task_vm_info_data_t *info = (task_vm_info_data_t *)out;
    info->min_address = reply_min; info->max_address = reply_max;
    *count = reply_count;
    return KERN_SUCCESS;
}
static void *fake_mmap(void *hint, size_t size, int prot, int flags, int fd, off_t offset) {
    (void)flags; (void)fd; (void)offset;
    assert(size == host_page_size && prot == PROT_NONE);
    mmap_calls++;
    if ((uintptr_t)hint == walk_stop) return hint;
    errno = ENOMEM; return MAP_FAILED;
}
static int fake_munmap(void *address, size_t size) {
    assert((uintptr_t)address == walk_stop && size == host_page_size); return 0;
}
static void ios_pool_va_warn(const char *operation, void *address, size_t size) {
    (void)operation; (void)address; (void)size;
}
#define mmap fake_mmap
#define munmap fake_munmap
''' + production_function("static void ios_clamp_user_space_limit( const char *when )") + \
    production_function("static void *get_host_addr_space_limit(void)") + r'''
static void check(uintptr_t stop, uintptr_t low, uintptr_t high,
                  unsigned count, int status, uintptr_t expected) {
    walk_stop = stop; reply_min = low; reply_max = high;
    reply_count = count; reply_status = status; mmap_calls = 0;
    host_addr_space_limit = get_host_addr_space_limit();
    assert(mmap_calls > 0 && mmap_calls < 64);
    assert((uintptr_t)host_addr_space_limit == expected);
    user_space_limit = (void *)0x7fffffff0000ULL;
    ios_clamp_user_space_limit("unit-fixture");
    assert((uintptr_t)user_space_limit == expected);
}
int main(void) {
    /* Owner's non-power-of-two range: old code returns 512 GiB, not 454 GiB. */
    check(0x4000000000ULL, 0x104ab4000ULL, 0x7180000000ULL, 4, 0, 0x7180000000ULL);
    /* Preserve the earlier fix for a walk that underestimated the map. */
    check(0x400000000ULL, 0x100000000ULL, 0xfc0000000ULL, 4, 0, 0xfc0000000ULL);
    check(0x4000000000ULL, 0x100000000ULL, 0x8000000000ULL, 4, 0, 0x8000000000ULL);
    /* Unavailable/revision-short/invalid geometry retains the old fallback. */
    check(0x4000000000ULL, 0x100000000ULL, 0x7180000000ULL, 4, 5, 0x8000000000ULL);
    check(0x4000000000ULL, 0x100000000ULL, 0x7180000000ULL, 3, 0, 0x8000000000ULL);
    check(0x4000000000ULL, 0, 0, 4, 0, 0x8000000000ULL);
    check(0x4000000000ULL, 0, 0xffffc000ULL, 4, 0, 0x8000000000ULL);
    check(0x4000000000ULL, 0x7180000000ULL, 0x7180000000ULL, 4, 0, 0x8000000000ULL);
    check(0x4000000000ULL, 0x7200000000ULL, 0x7180000000ULL, 4, 0, 0x8000000000ULL);
    check(0x4000000000ULL, 0x100000000ULL, 0x7180000001ULL, 4, 0, 0x8000000000ULL);
    puts("HOST_VA_LIMIT_PASS: production limit+clamp; lower/higher/equal kernel bounds and safe fallback");
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="bcd-host-va-limit-") as temp:
    c = Path(temp) / "host-va-limit.c"
    binary = Path(temp) / "host-va-limit"
    c.write_text(harness)
    subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", str(c), "-o", str(binary)], check=True, timeout=60)
    env = dict(os.environ)
    env.pop("MADEIRA_WIDE_USER_VA", None)
    subprocess.run([str(binary)], env=env, check=True, timeout=10)
