#include "shm-zero-init.c"
#include <assert.h>
#include <linux/futex.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>

static int64_t monotonic_ns(void) {
    struct timespec now; assert(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (int64_t)now.tv_sec * 1000000000LL + now.tv_nsec;
}

static void wait_value(int *word, int expected, int wanted) {
    int64_t deadline = monotonic_ns() + 5000000000LL;
    while (__atomic_load_n(word, __ATOMIC_ACQUIRE) != wanted) {
        int64_t remaining = deadline - monotonic_ns();
        assert(remaining > 0);
        struct timespec limit = {.tv_sec = remaining / 1000000000LL, .tv_nsec = remaining % 1000000000LL};
        long r = syscall(SYS_futex, word, FUTEX_WAIT, expected, &limit, NULL, 0);
        assert(r == 0 || (r == -1 && (errno == EAGAIN || errno == EINTR)));
    }
}

static void wake_blocked_peer(int *word) {
    int64_t deadline = monotonic_ns() + 2000000000LL;
    for (;;) {
        long r = syscall(SYS_futex, word, FUTEX_WAKE, 1, NULL, NULL, 0);
        assert(r >= 0);
        if (r == 1) return;
        assert(monotonic_ns() < deadline);
        struct timespec pause = {.tv_nsec = 1000000}; nanosleep(&pause, NULL);
    }
}

static void publish(int *word, int value) {
    __atomic_store_n(word, value, __ATOMIC_RELEASE);
    assert(syscall(SYS_futex, word, FUTEX_WAKE, 1, NULL, NULL, 0) >= 0);
}

int main(void) {
    assert(getuid() == 1000);
    char path[128];
    snprintf(path, sizeof(path), "/dev/shm/u1000-Shm_%08x", (unsigned)getpid());
    int fd = open(path, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0700);
    assert(fd >= 0 && fchmod(fd, 0700) == 0 && ftruncate(fd, STREAM_BYTES) == 0);
    unsigned char *parent = mmap(NULL, STREAM_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    assert(parent != MAP_FAILED && already_zero(parent, STREAM_BYTES, NULL));
    int ready[2]; assert(pipe2(ready, O_CLOEXEC) == 0);
    pid_t child = fork(); assert(child >= 0);
    const size_t tail = STREAM_BYTES - 8192;
    if (!child) {
        close(ready[0]);
        unsigned char *peer = mmap(NULL, STREAM_BYTES, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        assert(peer != MAP_FAILED && peer != parent && munmap(parent, STREAM_BYTES) == 0);
        assert(*(volatile int *)peer == 0);
        assert(*(volatile unsigned char *)(peer + tail) == 0);
        assert(write(ready[1], "r", 1) == 1); close(ready[1]);
        wait_value((int *)peer, 0, 1);
        for (size_t i = 0; i < 8192; i++) assert(((volatile unsigned char *)peer)[tail + i] == 0xa5);
        peer[tail] = 0x5a;
        publish((int *)peer, 2);
        assert(munmap(peer, STREAM_BYTES) == 0); close(fd); _exit(0);
    }
    close(ready[1]); char byte;
    assert(read(ready[0], &byte, 1) == 1 && byte == 'r'); close(ready[0]);
    wake_blocked_peer((int *)parent);
    memset(parent + tail, 0xa5, 8192);
    publish((int *)parent, 1);
    wait_value((int *)parent, 1, 2);
    assert(*(volatile unsigned char *)(parent + tail) == 0x5a);
    int status; assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    assert(!already_zero(parent, STREAM_BYTES, NULL));
    assert(munmap(parent, STREAM_BYTES) == 0 && close(fd) == 0 && unlink(path) == 0);
    puts("SHM_ZERO_IPC_PASS: distinct process mappings, untouched holes, bidirectional payload visibility and observed blocked shared futex wake");
}
