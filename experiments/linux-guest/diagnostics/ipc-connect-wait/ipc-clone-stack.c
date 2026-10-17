#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#if !defined(__aarch64__)
#error This test exercises the AArch64 link-register syscall ABI
#endif
extern long clone_stack_probe(void *stack_top);
__asm__(
".text\n.align 2\n.global clone_stack_probe\n.type clone_stack_probe,%function\n"
"clone_stack_probe:\n"
"stp x29,x30,[sp,#-32]!\nmov x29,sp\nstr x19,[sp,#16]\nmov x19,x0\n"
"mov x0,#220\nmov x1,#17\nmov x2,x19\nmov x3,#0\nmov x4,#0\nmov x5,#0\nmov x6,#0\n"
"bl syscall\ncbz x0,1f\nldr x19,[sp,#16]\nldp x29,x30,[sp],#32\nret\n"
"1: mov x10,sp\ncmp x10,x19\ncset w0,ne\nlsl w0,w0,#5\nmov x8,#93\nsvc #0\nbrk #0\n"
".size clone_stack_probe,.-clone_stack_probe\n");
int main(void) {
    const char *expected=getenv("IDECK_EXPECT_PRELOAD_LEAF");
    if(expected) {
        Dl_info d;
        if(!dladdr((void*)(uintptr_t)&syscall,&d) || !d.dli_fname)return 90;
        const char *leaf=strrchr(d.dli_fname,'/');leaf=leaf?leaf+1:d.dli_fname;
        if(strcmp(leaf,expected))return 91;
    }
    size_t size=65536;
    void *p=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(p==MAP_FAILED)return 92;
    long pid=clone_stack_probe((char*)p+size);
    if(pid<=0){printf("{\"clone_failed\":true,\"errno\":%d}\n",errno);return 93;}
    int status=0;
    if(waitpid((pid_t)pid,&status,0)!=pid)return 94;
    int ok=WIFEXITED(status) && WEXITSTATUS(status)==0;
    printf("{\"aarch64_custom_child_stack_preserved\":%s,\"raw_wait_status\":%d,\"child_exit\":%d,\"child_signal\":%d}\n",ok?"true":"false",status,WIFEXITED(status)?WEXITSTATUS(status):-1,WIFSIGNALED(status)?WTERMSIG(status):0);
    munmap(p,size);
    return ok?0:1;
}
