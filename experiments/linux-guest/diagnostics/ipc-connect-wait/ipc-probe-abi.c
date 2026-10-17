#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <linux/futex.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
static void exercise(void) {
    errno=E2BIG;assert(syscall(SYS_getpid)==getpid());assert(errno==E2BIG);
    errno=0;assert(syscall(0x7fffffffL)==-1 && errno==ENOSYS);
    errno=0;assert(syscall(SYS_write,-1L,(long)(uintptr_t)"x",1L)==-1 && errno==EBADF);
    long memory=syscall(SYS_mmap,0L,4096L,(long)(PROT_READ|PROT_WRITE),(long)(MAP_PRIVATE|MAP_ANONYMOUS),-1L,0L);
    assert(memory!=-1);*(volatile unsigned char*)(uintptr_t)memory=0xa5;assert(*(volatile unsigned char*)(uintptr_t)memory==0xa5);assert(syscall(SYS_munmap,memory,4096L)==0);
    int word=1;struct timespec short_wait={0,3000000};
    errno=0;assert(syscall(SYS_futex,(long)(uintptr_t)&word,(long)FUTEX_WAIT_PRIVATE,0L,(long)(uintptr_t)&short_wait,0L,0L)==-1 && errno==EAGAIN);
    word=0;struct timespec start,end;clock_gettime(CLOCK_MONOTONIC,&start);
    errno=0;assert(syscall(SYS_futex,(long)(uintptr_t)&word,(long)FUTEX_WAIT_PRIVATE,0L,(long)(uintptr_t)&short_wait,0L,0L)==-1 && errno==ETIMEDOUT);
    clock_gettime(CLOCK_MONOTONIC,&end);long long ns=(long long)(end.tv_sec-start.tv_sec)*1000000000LL+end.tv_nsec-start.tv_nsec;assert(ns<2000000000LL);
    pid_t child=fork();assert(child>=0);if(child==0)_exit(syscall(SYS_getpid)==getpid()?0:1);
    int status;assert(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
}
int main(void) {
    const char *expected=getenv("IDECK_EXPECT_PRELOAD_LEAF");
    if(expected) {
        Dl_info information;assert(dladdr((void*)(uintptr_t)&syscall,&information) && information.dli_fname);
        const char *leaf=strrchr(information.dli_fname,'/');leaf=leaf?leaf+1:information.dli_fname;
        assert(!strcmp(leaf,expected));
    }
    exercise();puts("{\"status\":\"pass\",\"test\":\"external preload ABI: getpid, errno, invalid syscall, write, six-argument mmap, futex, fork\"}");return 0;}