#include "ipc-connect-wait.c"
#include <assert.h>
#include <stdalign.h>
#include <sys/mman.h>
#include <sys/wait.h>
#define main abi_main
#include "ipc-probe-abi.c"
#undef main
int main(void) {
    assert(!active);exercise();syscall_fn real=next_syscall;next_syscall=NULL;exercise();next_syscall=real;
    struct timespec t={0,500000000};assert(shape(SYS_futex,FUTEX_WAIT,0,&t,0,0));
    assert(!shape(SYS_getpid,FUTEX_WAIT,0,&t,0,0));assert(!shape(SYS_futex,FUTEX_WAIT_PRIVATE,0,&t,0,0));assert(!shape(SYS_futex,FUTEX_WAIT,1,&t,0,0));assert(!shape(SYS_futex,FUTEX_WAIT,0,&t,1,0));
    t.tv_nsec--;assert(!shape(SYS_futex,FUTEX_WAIT,0,&t,0,0));t.tv_nsec++;t.tv_sec=1;assert(!shape(SYS_futex,FUTEX_WAIT,0,&t,0,0));
    struct stat s={0};struct statfs v={0};s.st_mode=S_IFREG|0700;s.st_uid=1000;s.st_nlink=1;s.st_size=2097152;v.f_type=TMPFS_MAGIC;assert(shared_file_contract(&s,&v));
    s.st_uid=0;assert(!shared_file_contract(&s,&v));s.st_uid=1000;s.st_nlink=2;assert(!shared_file_contract(&s,&v));s.st_nlink=1;s.st_size++;assert(!shared_file_contract(&s,&v));s.st_size--;s.st_mode=S_IFREG|0777;assert(!shared_file_contract(&s,&v));s.st_mode=S_IFREG|0700;v.f_type=0xef53;assert(!shared_file_contract(&s,&v));
    alignas(16) uintptr_t frames[3][2];chrome_base=0x10000000;uintptr_t pc=chrome_base+0x60420;
    frames[0][0]=(uintptr_t)frames[1];frames[0][1]=pc;frames[1][0]=(uintptr_t)frames[2];frames[1][1]=chrome_base+0x63a98;frames[2][0]=0;frames[2][1]=chrome_base+0x5b368;
    assert(connect_frames((uintptr_t)frames,pc));frames[1][1]++;assert(!connect_frames((uintptr_t)frames,pc));frames[1][1]--;frames[1][0]=(uintptr_t)frames;assert(!connect_frames((uintptr_t)frames,pc));assert(!connect_frames(1,pc));
    assert(!shared_wait_address((uintptr_t)frames));assert(!verify_chrome((uintptr_t)exercise));
    active=1;constructor_pid=getpid();int word=1;struct timespec wait={0,500000000};errno=0;
    assert(syscall(SYS_futex,(long)(uintptr_t)&word,(long)FUTEX_WAIT,0L,(long)(uintptr_t)&wait,0L,0L)==-1 && errno==EAGAIN);active=0;
    puts("{\"status\":\"pass\",\"test\":\"shape, owner/links/mode/filesystem, actual bounded frame walk, unrelated caller refusal, raw syscall fallback ABI\"}");return 0;
}