#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/magic.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/sysmacros.h>
#include <unistd.h>

/* Opt-in experiment: an all-hole tmpfs file already reads as zero. Only the
 * pinned Steam browser's first whole-stream zero can retain that lazy state.
 * Any failed identity, mapping or hole check uses ordinary libc memset.
 */
#define STREAM_BYTES (25U * 1024U * 1024U + 16U)
static const char browser[] = "/home/ideck/.local/share/Steam/steamrtarm64/steamwebhelper";
static const char digest[] = "0a849676a3ba0cc51ca23cba79be3df0546744fd92c2e2d628a1f71707a70a56";
static void *(*real_memset)(void *, int, size_t);
static pid_t owner;
static int enabled, log_fd = -1;
static atomic_uint events;
static struct stat verified_binary;
static struct stat log_identity;
static __thread int checking;

static void *ordinary(void *p, int c, size_t n) {
    if (real_memset) return real_memset(p, c, n);
    volatile unsigned char *b = p;
    for (size_t i = 0; i < n; i++) b[i] = (unsigned char)c;
    return p;
}

struct region {
    uintptr_t lo, hi;
    unsigned long offset, inode;
    unsigned major, minor;
    char permissions[5], path[512];
};

static int region_at(uintptr_t address, size_t bytes, struct region *r) {
    if (!address || bytes > UINTPTR_MAX - address) return 0;
    FILE *f = fopen("/proc/self/maps", "re");
    if (!f) return 0;
    char line[1024]; int found = 0;
    while (fgets(line, sizeof(line), f)) {
        unsigned long lo, hi, offset, inode; unsigned major, minor; char permissions[5]; int at = 0;
        if (sscanf(line, "%lx-%lx %4s %lx %x:%x %lu %n", &lo, &hi, permissions,
                   &offset, &major, &minor, &inode, &at) != 7) continue;
        if (lo <= address && address + bytes <= hi && at > 0) {
            r->lo = lo; r->hi = hi; r->offset = offset; r->inode = inode;
            r->major = major; r->minor = minor;
            ordinary(r->permissions, 0, sizeof(r->permissions));
            ordinary(r->path, 0, sizeof(r->path));
            memcpy(r->permissions, permissions, 4);
            size_t n = strcspn(line + at, "\r\n");
            if (n >= sizeof(r->path)) break;
            memcpy(r->path, line + at, n); found = 1; break;
        }
    }
    fclose(f); return found;
}

static int same_file(const struct stat *a, const struct stat *b) {
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino && a->st_size == b->st_size &&
           a->st_mode == b->st_mode && a->st_uid == b->st_uid && a->st_nlink == b->st_nlink &&
           a->st_mtim.tv_sec == b->st_mtim.tv_sec && a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
           a->st_ctim.tv_sec == b->st_ctim.tv_sec && a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
}

static int stream_name(const char *path) {
    const char prefix[] = "/dev/shm/u1000-Shm_";
    if (strncmp(path, prefix, sizeof(prefix) - 1)) return 0;
    const char *suffix = path + sizeof(prefix) - 1;
    if (strlen(suffix) != 8) return 0;
    return strspn(suffix, "0123456789abcdefABCDEF") == 8;
}

static int file_contract(const struct stat *s, const struct statfs *v) {
    return S_ISREG(s->st_mode) && (s->st_mode & 07777) == 0700 && s->st_uid == 1000 &&
           s->st_nlink == 1 && s->st_size == STREAM_BYTES && s->st_blocks == 0 &&
           v->f_type == TMPFS_MAGIC;
}

static int already_zero(void *address, size_t bytes, struct stat *result) {
    struct region r; struct stat before, after; struct statfs fs;
    if (bytes != STREAM_BYTES || !region_at((uintptr_t)address, bytes, &r) ||
        r.lo != (uintptr_t)address || r.offset || strcmp(r.permissions, "rw-s") || !stream_name(r.path)) return 0;
    int fd = open(r.path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return 0;
    int ok = fstat(fd, &before) == 0 && fstatfs(fd, &fs) == 0 && file_contract(&before, &fs) &&
             before.st_dev == makedev(r.major, r.minor) && before.st_ino == r.inode;
    if (ok) {
        errno = 0;
        ok = lseek(fd, 0, SEEK_DATA) == -1 && errno == ENXIO &&
             fstat(fd, &after) == 0 && same_file(&before, &after) && after.st_blocks == 0;
    }
    close(fd);
    if (ok && result) *result = before;
    return ok;
}

static int caller_matches(uintptr_t pc) {
    Dl_info info; struct region mapping; struct stat current;
    static const unsigned char call[] = {0xc1, 0x2a, 0xfe, 0x97, 0x60, 0xa2, 0x40, 0xf9};
    return dladdr((void *)pc, &info) && info.dli_fname && !strcmp(info.dli_fname, browser) &&
           pc - (uintptr_t)info.dli_fbase == 0x1407c0 && region_at(pc - 4, sizeof(call), &mapping) &&
           strchr(mapping.permissions, 'x') && !strcmp(mapping.path, browser) &&
           stat(browser, &current) == 0 && same_file(&verified_binary, &current) &&
           current.st_dev == makedev(mapping.major, mapping.minor) && current.st_ino == mapping.inode &&
           !memcmp((const void *)(pc - 4), call, sizeof(call));
}

static int verify_browser(void) {
    int fd = open(browser, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return 0;
    struct stat after; unsigned char *bytes = NULL; void *crypto = NULL; int ok = 0;
    if (fstat(fd, &verified_binary) || !S_ISREG(verified_binary.st_mode) || verified_binary.st_uid != 1000 ||
        verified_binary.st_nlink != 1 || verified_binary.st_size != 10326560) goto done;
    bytes = malloc((size_t)verified_binary.st_size);
    if (!bytes) goto done;
    size_t got = 0;
    while (got < (size_t)verified_binary.st_size) {
        ssize_t n = read(fd, bytes + got, (size_t)verified_binary.st_size - got);
        if (n <= 0) goto done;
        got += (size_t)n;
    }
    if (fstat(fd, &after) || !same_file(&verified_binary, &after)) goto done;
    crypto = dlopen("/usr/lib/aarch64-linux-gnu/libcrypto.so.3", RTLD_NOW | RTLD_LOCAL);
    if (!crypto) goto done;
    typedef unsigned char *(*sha_fn)(const unsigned char *, size_t, unsigned char *);
    sha_fn sha = (sha_fn)dlsym(crypto, "SHA256"); unsigned char hash[32]; char hex[65];
    if (!sha || !sha(bytes, got, hash)) goto done;
    for (unsigned i = 0; i < 32; i++) snprintf(hex + i * 2, 3, "%02x", hash[i]);
    ok = !strcmp(hex, digest);
done:
    if (crypto) dlclose(crypto);
    free(bytes); close(fd); return ok;
}

__attribute__((constructor)) static void setup(void) {
    int saved = errno;
    real_memset = (void *(*)(void *, int, size_t))dlsym(RTLD_NEXT, "memset");
    owner = getpid();
    char executable[512], arguments[8192]; ssize_t n = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
    if (n <= 0) goto done;
    executable[n] = 0;
    if (getuid() != 1000 || geteuid() != 1000 || strcmp(executable, browser)) goto done;
    int fd = open("/proc/self/cmdline", O_RDONLY | O_CLOEXEC);
    if (fd < 0) goto done;
    n = read(fd, arguments, sizeof(arguments)); close(fd);
    if (n <= 0 || n == (ssize_t)sizeof(arguments)) goto done;
    for (ssize_t i = 0; i + 7 < n; i++) if (!memcmp(arguments + i, "--type=", 7)) goto done;
    if (!verify_browser()) goto done;
    struct stat directory;
    if (lstat("/run/user/1000", &directory) || !S_ISDIR(directory.st_mode) ||
        directory.st_uid != 1000 || (directory.st_mode & 0777) != 0700) goto done;
    char path[128]; snprintf(path, sizeof(path), "/run/user/1000/ideck-shm-zero-%ld.jsonl", (long)owner);
    log_fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (log_fd < 0) goto done;
    if (fstat(log_fd, &log_identity) || !S_ISREG(log_identity.st_mode) || log_identity.st_uid != 1000 ||
        log_identity.st_nlink != 1 || (log_identity.st_mode & 0777) != 0600) goto done;
    char row[192]; int count = snprintf(row, sizeof(row), "{\"event\":\"ready\",\"pid\":%ld,\"browser_sha256\":\"%s\"}\n", (long)owner, digest);
    if (count <= 0 || (size_t)count >= sizeof(row) || write(log_fd, row, (size_t)count) != count) goto done;
    enabled = 1;
done:
    if (!enabled && log_fd >= 0) { close(log_fd); log_fd = -1; }
    errno = saved;
}

__attribute__((visibility("default"), noinline)) void *ideck_memset(void *, int, size_t) __asm__("memset");
void *ideck_memset(void *address, int value, size_t bytes) {
    if (!enabled || checking || (unsigned char)value != 0 || bytes != STREAM_BYTES || getpid() != owner)
        return ordinary(address, value, bytes);
    int saved = errno; checking = 1;
    uintptr_t pc = (uintptr_t)__builtin_extract_return_addr(__builtin_return_address(0));
    unsigned sequence = atomic_fetch_add_explicit(&events, 1, memory_order_relaxed);
    struct stat file; int caller = caller_matches(pc);
    int skip = sequence < 128 && caller && already_zero(address, bytes, &file);
    if (sequence < 128) {
        struct stat log;
        int log_valid = fstat(log_fd, &log) == 0 && S_ISREG(log.st_mode) && log.st_uid == 1000 &&
                        log.st_nlink == 1 && (log.st_mode & 0777) == 0600 &&
                        log.st_dev == log_identity.st_dev && log.st_ino == log_identity.st_ino;
        char row[256];
        int n = snprintf(row, sizeof(row), "{\"event\":\"stream_zero\",\"pid\":%ld,\"bytes\":%zu,\"caller_matched\":%s,\"already_zero\":%s,\"inode\":%lu}\n",
                         (long)owner, bytes, caller ? "true" : "false", skip ? "true" : "false", skip ? (unsigned long)file.st_ino : 0UL);
        if (!log_valid || n <= 0 || (size_t)n >= sizeof(row) || write(log_fd, row, (size_t)n) != n) skip = 0;
    }
    checking = 0; errno = saved;
    return skip ? address : ordinary(address, value, bytes);
}
