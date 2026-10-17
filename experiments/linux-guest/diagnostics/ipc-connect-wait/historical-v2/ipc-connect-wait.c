#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/futex.h>
#include <linux/magic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <unistd.h>

/* Private opt-in TCG probe. No client ELF modification or global preload.
 * Exactly one native-main-thread chromehtml connect-response wait may use a
 * local 5s timespec. All other syscall arguments and errno behavior pass through.
 * A failed identity/shape/frame/file/log check leaves the original wait intact.
 */
typedef long (*syscall_fn)(long, ...);
static syscall_fn next_syscall;
static pid_t constructor_pid;
static int active, extend_mode, log_fd=-1, module_verified;
static unsigned events,refusals;
static uintptr_t chrome_base;
static const char expected_chrome_sha[]="753ca9cb1aff9740a99c84e0d8a8a1270c2cb081fd1a414696da2a5e8c833ae7";
static const char chrome_path[]="/home/ideck/.local/share/Steam/steamrtarm64/chromehtml.so";
static const char native_path[]="/home/ideck/.local/share/Steam/steamrtarm64/steam";
static const char shared_path[]="/dev/shm/u1000-ValveIPCSharedObj-Steam";

static long raw_call(long n,long a,long b,long c,long d,long e,long f) {
#if defined(__aarch64__)
    register long x8 __asm__("x8")=n;
    register long x0 __asm__("x0")=a,x1 __asm__("x1")=b,x2 __asm__("x2")=c;
    register long x3 __asm__("x3")=d,x4 __asm__("x4")=e,x5 __asm__("x5")=f;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x8),"r"(x1),"r"(x2),"r"(x3),"r"(x4),"r"(x5) : "memory","cc");
    long r=x0;
#elif defined(__x86_64__)
    register long r10 __asm__("r10")=d,r8 __asm__("r8")=e,r9 __asm__("r9")=f;
    long r;
    __asm__ volatile("syscall" : "=a"(r) : "a"(n),"D"(a),"S"(b),"d"(c),"r"(r10),"r"(r8),"r"(r9) : "rcx","r11","memory","cc");
#else
#error Unsupported probe architecture
#endif
    if ((unsigned long)r >= (unsigned long)-4095L) { errno=(int)-r;return -1; }
    return r;
}
static long forward(long n,long a,long b,long c,long d,long e,long f) {
    return next_syscall ? next_syscall(n,a,b,c,d,e,f) : raw_call(n,a,b,c,d,e,f);
}

struct mapping { uintptr_t lo,hi; unsigned long off,ino; unsigned maj,min;char perm[5];char path[512]; };
static int mapped(uintptr_t address,size_t bytes,struct mapping *m) {
    if (!address || bytes>UINTPTR_MAX-address) return 0;
    FILE *f=fopen("/proc/self/maps","re");if (!f) return 0;
    char line[1024];int found=0;
    while (fgets(line,sizeof(line),f)) {
        unsigned long lo,hi,off,ino;unsigned maj,min;char perm[5];int at=0;
        if (sscanf(line,"%lx-%lx %4s %lx %x:%x %lu %n",&lo,&hi,perm,&off,&maj,&min,&ino,&at)!=7) continue;
        if ((uintptr_t)lo<=address && address+bytes<=(uintptr_t)hi) {
            memset(m,0,sizeof(*m));m->lo=lo;m->hi=hi;m->off=off;m->ino=ino;m->maj=maj;m->min=min;memcpy(m->perm,perm,5);
            if (at>0) { const char *p=line+at;while (*p==' ' || *p=='\t') p++;size_t n=strcspn(p,"\r\n");if(n>=sizeof(m->path))break;memcpy(m->path,p,n); }
            found=1;break;
        }
    }
    fclose(f);return found;
}
static int same_file(const struct stat *a,const struct stat *b) {
    return a->st_dev==b->st_dev && a->st_ino==b->st_ino && a->st_size==b->st_size &&
           a->st_mtim.tv_sec==b->st_mtim.tv_sec && a->st_mtim.tv_nsec==b->st_mtim.tv_nsec &&
           a->st_ctim.tv_sec==b->st_ctim.tv_sec && a->st_ctim.tv_nsec==b->st_ctim.tv_nsec;
}
static int shared_file_contract(const struct stat *s,const struct statfs *v) {
    return S_ISREG(s->st_mode) && s->st_uid==1000 && s->st_nlink==1 &&
           (s->st_mode&0777)==0700 && s->st_size==2*1024*1024 && v->f_type==TMPFS_MAGIC;
}
static int shared_wait_address(uintptr_t address) {
    struct mapping m;struct stat s;struct statfs v;
    if (address%4 || !mapped(address,4,&m) || strcmp(m.perm,"rw-s") || strcmp(m.path,shared_path))return 0;
    int fd=open(shared_path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)return 0;
    int ok=fstat(fd,&s)==0 && fstatfs(fd,&v)==0 && shared_file_contract(&s,&v) &&
           s.st_dev==makedev(m.maj,m.min) && s.st_ino==m.ino && m.off+address-m.lo+4<=(uintptr_t)s.st_size;
    close(fd);return ok;
}
static int verify_chrome(uintptr_t pc) {
    Dl_info d;struct mapping m;struct stat before,after;
    if (!dladdr((void*)pc,&d) || !d.dli_fname || strcmp(d.dli_fname,chrome_path) ||
        pc-(uintptr_t)d.dli_fbase!=0x60420 || !mapped(pc-4,8,&m) || strcmp(m.path,chrome_path) || !strchr(m.perm,'x')) return 0;
    int fd=open(chrome_path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)return 0;
    int ok=0;unsigned char *bytes=NULL;void *crypto=NULL;
    if(fstat(fd,&before) || !S_ISREG(before.st_mode) || before.st_uid!=1000 || before.st_nlink!=1 ||
       before.st_size!=2923856 || before.st_dev!=makedev(m.maj,m.min) || before.st_ino!=m.ino)goto done;
    bytes=malloc((size_t)before.st_size);if(!bytes)goto done;
    size_t got=0;while(got<(size_t)before.st_size){ssize_t n=read(fd,bytes+got,(size_t)before.st_size-got);if(n<=0)goto done;got+=(size_t)n;}
    if(fstat(fd,&after) || !same_file(&before,&after))goto done;
    crypto=dlopen("/usr/lib/aarch64-linux-gnu/libcrypto.so.3",RTLD_NOW|RTLD_LOCAL);if(!crypto)goto done;
    typedef unsigned char *(*sha_fn)(const unsigned char*,size_t,unsigned char*);
    sha_fn sha=(sha_fn)dlsym(crypto,"SHA256");unsigned char hash[32];char hex[65];
    if(!sha || !sha(bytes,got,hash))goto done;
    for(unsigned i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",hash[i]);
    if(strcmp(hex,expected_chrome_sha))goto done;
    /* Exact checked call opcode and following cmn; PT_LOAD for this pinned
       chromehtml has identical file/virtual offsets, verified independently. */
    const unsigned char signature[]={0xf5,0x71,0xff,0x97,0x1f,0x04,0x00,0x31};
    if(memcmp(bytes+0x6041c,signature,sizeof(signature)) || memcmp((const void*)(pc-4),signature,sizeof(signature)))goto done;
    chrome_base=(uintptr_t)d.dli_fbase;ok=1;
done:
    if(crypto)dlclose(crypto);
    free(bytes);close(fd);return ok;
}
static int connect_frames(uintptr_t fp,uintptr_t pc) {
    struct mapping stack;if(!mapped(fp,16,&stack) || stack.perm[0]!='r' || stack.perm[1]!='w')return 0;
    const uintptr_t expected[]={pc,chrome_base+0x63a98,chrome_base+0x5b368};uintptr_t prior=fp-16;
    for(unsigned i=0;i<3;i++) {
        if(fp%16 || fp<=prior || fp<stack.lo || fp>stack.hi-16)return 0;
        uintptr_t pair[2];memcpy(pair,(const void*)fp,sizeof(pair));if(pair[1]!=expected[i])return 0;
        prior=fp;fp=pair[0];
    }
    return 1;
}
static int shape(long n,long op,long value,const struct timespec *t,long unused1,long unused2) {
    return n==SYS_futex && op==FUTEX_WAIT && value==0 && t && t->tv_sec==0 && t->tv_nsec==500000000L && unused1==0 && unused2==0;
}
static int prepare_log(void) {
    if(log_fd>=0)return 1;
    struct stat d;if(lstat("/run/user/1000",&d) || !S_ISDIR(d.st_mode) || d.st_uid!=1000 || (d.st_mode&0777)!=0700)return 0;
    int parent=open("/run/user/1000",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if(parent<0)return 0;
    char name[80];snprintf(name,sizeof(name),"ideck-ipc-connect-%ld.jsonl",(long)constructor_pid);
    int fd=openat(parent,name,O_WRONLY|O_CREAT|O_EXCL|O_APPEND|O_NOFOLLOW|O_CLOEXEC,0600);close(parent);
    if(fd<0)return 0;
    struct stat s;
    if(fstat(fd,&s) || !S_ISREG(s.st_mode) || s.st_uid!=1000 || s.st_nlink!=1 || (s.st_mode&0777)!=0600){close(fd);return 0;}
    log_fd=fd;return 1;
}
static void emit_refusal(const char *reason) {
    if(refusals++>=16 || !prepare_log())return;
    char row[192];int n=snprintf(row,sizeof(row),"{\"event\":\"guard_refused\",\"pid\":%ld,\"reason\":\"%s\",\"wait_changed\":false}\n",(long)constructor_pid,reason);
    if(n>0 && (size_t)n<sizeof(row)){ssize_t written=write(log_fd,row,(size_t)n);(void)written;}
}
static int emit_before(unsigned seq,int milliseconds) {
    char row[512];int n=snprintf(row,sizeof(row),"{\"event\":\"before_connect_wait\",\"pid\":%ld,\"seq\":%u,\"original_ms\":500,\"effective_ms\":%d,\"caller_va\":\"0x60420\",\"caller_chain\":[\"0x63a98\",\"0x5b368\"],\"chromehtml_sha256\":\"%s\"}\n",(long)constructor_pid,seq,milliseconds,expected_chrome_sha);
    return n>0 && (size_t)n<sizeof(row) && write(log_fd,row,(size_t)n)==n;
}
static void emit_after(unsigned seq,long result,int error,long long ns) {
    char row[256];int n=snprintf(row,sizeof(row),"{\"event\":\"after_connect_wait\",\"pid\":%ld,\"seq\":%u,\"result\":%ld,\"errno\":%d,\"elapsed_ns\":%lld}\n",(long)constructor_pid,seq,result,error,ns);
    if(n>0 && (size_t)n<sizeof(row)){ssize_t written=write(log_fd,row,(size_t)n);(void)written;}
}
__attribute__((constructor)) static void setup(void) {
    int saved=errno;next_syscall=(syscall_fn)dlsym(RTLD_NEXT,"syscall");constructor_pid=getpid();
    char exe[512];ssize_t n=readlink("/proc/self/exe",exe,sizeof(exe)-1);
    if(n>0){exe[n]=0;active=getuid()==1000 && geteuid()==1000 && !strcmp(exe,native_path);}
    const char *mode=getenv("IDECK_IPC_WAIT_MODE");extend_mode=mode && !strcmp(mode,"extend-5000");
    if(active && prepare_log()) {
        char row[192];int length=snprintf(row,sizeof(row),"{\"event\":\"probe_loaded\",\"pid\":%ld,\"mode\":\"%s\",\"only_verified_connect_wait\":true}\n",(long)constructor_pid,extend_mode?"extend-5000":"observe");
        if(length>0 && (size_t)length<sizeof(row)){ssize_t written=write(log_fd,row,(size_t)length);(void)written;}
    }
    errno=saved;
}
/* Fixed integer-register ABI matches Linux syscall(number, up to six long
   arguments); no va_arg reads beyond a caller's actual arguments. */
__attribute__((visibility("default"),noinline))
long ideck_syscall(long,long,long,long,long,long,long) __asm__("syscall");
long ideck_syscall(long n,long a,long b,long c,long d,long e,long f) {
    int saved=errno;
    if(!active || getpid()!=constructor_pid || n!=SYS_futex || b!=FUTEX_WAIT || c!=0 || d==0 || e!=0 || f!=0 ||
       raw_call(SYS_gettid,0,0,0,0,0,0)!=constructor_pid || events>=64) {
        errno=saved;return forward(n,a,b,c,d,e,f);
    }
    uintptr_t pc=(uintptr_t)__builtin_return_address(0),fp=(uintptr_t)__builtin_frame_address(0);
    Dl_info di;if(!dladdr((void*)pc,&di) || pc-(uintptr_t)di.dli_fbase!=0x60420 || !di.dli_fname || strcmp(di.dli_fname,chrome_path)) {
        errno=saved;return forward(n,a,b,c,d,e,f);
    }
    struct mapping tm;struct timespec original;
    if(!mapped((uintptr_t)d,sizeof(original),&tm) || tm.perm[0]!='r') {errno=saved;return forward(n,a,b,c,d,e,f);}
    memcpy(&original,(const void*)(uintptr_t)d,sizeof(original));
    if(!shape(n,b,c,&original,e,f)) {errno=saved;return forward(n,a,b,c,d,e,f);}
    if(module_verified==0)module_verified=verify_chrome(pc)?1:-1;
    if(module_verified!=1){emit_refusal("module_identity");errno=saved;return forward(n,a,b,c,d,e,f);}
    if(!connect_frames(fp,pc)){emit_refusal("caller_frames");errno=saved;return forward(n,a,b,c,d,e,f);}
    if(!shared_wait_address((uintptr_t)a)){emit_refusal("shared_mapping");errno=saved;return forward(n,a,b,c,d,e,f);}
    if(!prepare_log()) {
        errno=saved;return forward(n,a,b,c,d,e,f);
    }
    unsigned seq=events++;int ms=extend_mode?5000:500;
    if(!emit_before(seq,ms)){errno=saved;return forward(n,a,b,c,d,e,f);}
    struct timespec replacement={5,0},start,end;
    clock_gettime(CLOCK_MONOTONIC,&start);errno=saved;
    long result=forward(n,a,b,c,extend_mode?(long)(uintptr_t)&replacement:d,e,f);int result_errno=errno;
    clock_gettime(CLOCK_MONOTONIC,&end);
    long long elapsed=(long long)(end.tv_sec-start.tv_sec)*1000000000LL+end.tv_nsec-start.tv_nsec;
    emit_after(seq,result,result==-1?result_errno:0,elapsed);errno=result_errno;return result;
}