#include "shm-zero-init.c"
#include <assert.h>
#include <sys/mman.h>

static void check_bytes(const unsigned char *p, size_t n, unsigned char expected) {
    for (size_t i = 0; i < n; i++) assert(((const volatile unsigned char *)p)[i] == expected);
}

int main(void) {
    assert(getuid() == 1000);
    assert(stream_name("/dev/shm/u1000-Shm_12aBcD34"));
    assert(!stream_name("/dev/shm/u1000-Shm_12aBcD34 (deleted)"));
    assert(!stream_name("/tmp/u1000-Shm_12aBcD34"));
    struct stat shape = {.st_mode = S_IFREG | 0700, .st_uid = 1000, .st_nlink = 1, .st_size = STREAM_BYTES};
    struct statfs fs = {.f_type = TMPFS_MAGIC};
    assert(file_contract(&shape, &fs));
    shape.st_uid = 0; assert(!file_contract(&shape, &fs)); shape.st_uid = 1000;
    shape.st_nlink = 2; assert(!file_contract(&shape, &fs)); shape.st_nlink = 1;
    shape.st_blocks = 8; assert(!file_contract(&shape, &fs)); shape.st_blocks = 0;
    char path[128]; snprintf(path, sizeof(path), "/dev/shm/u1000-Shm_%08x", (unsigned)getpid());
    int fd = open(path, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0700);
    assert(fd >= 0 && fchmod(fd, 0700) == 0 && ftruncate(fd, STREAM_BYTES) == 0);
    void *p = mmap(NULL, STREAM_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    assert(p != MAP_FAILED && already_zero(p, STREAM_BYTES, NULL));
    assert(!already_zero((char *)p + 4096, STREAM_BYTES - 4096, NULL));
    assert(!already_zero(p, STREAM_BYTES - 1, NULL));
    assert(fchmod(fd, 0600) == 0 && !already_zero(p, STREAM_BYTES, NULL));
    assert(fchmod(fd, 0700) == 0 && already_zero(p, STREAM_BYTES, NULL));
    check_bytes(p, STREAM_BYTES, 0);
    memset(p, 0xa5, STREAM_BYTES); check_bytes(p, STREAM_BYTES, 0xa5);
    assert(!already_zero(p, STREAM_BYTES, NULL));
    memset(p, 0, STREAM_BYTES); check_bytes(p, STREAM_BYTES, 0);
    void *private = mmap(NULL, STREAM_BYTES, PROT_READ | PROT_WRITE, MAP_PRIVATE, fd, 0);
    assert(private != MAP_FAILED && !already_zero(private, STREAM_BYTES, NULL));
    assert(munmap(private, STREAM_BYTES) == 0 && munmap(p, STREAM_BYTES) == 0);
    assert(close(fd) == 0 && unlink(path) == 0);
    puts("SHM_ZERO_UNIT_PASS: real tmpfs holes, contents, existing data, permissions, private/offset/size and ownership guards");
}
