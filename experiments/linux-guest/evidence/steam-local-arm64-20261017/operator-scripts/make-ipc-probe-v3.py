from pathlib import Path
import hashlib,json
task=Path(__file__).parent;s=(task/'ipc-connect-wait.c').read_text()
old='''/* Fixed integer-register ABI matches Linux syscall(number, up to six long
   arguments); no va_arg reads beyond a caller's actual arguments. */
__attribute__((visibility("default"),noinline))
long ideck_syscall(long,long,long,long,long,long,long) __asm__("syscall");'''
new=r'''/* AArch64 non-futex calls must tail-forward without a C stack frame:
 * clone/clone3 can return on a different child stack. The futex-only C path
 * cannot change stacks and retains the original caller LR/frame-chain gate.
 */
#if defined(__aarch64__)
__attribute__((visibility("hidden"),noinline,used))
long ideck_syscall(long,long,long,long,long,long,long) __asm__("ideck_checked_syscall");
__asm__(
".text\n.align 2\n.global syscall\n.type syscall,%function\n"
"syscall:\n.inst 0xd503245f\ncmp x0,#98\nb.eq ideck_checked_syscall\n"
"adrp x16,next_syscall\nldr x16,[x16,:lo12:next_syscall]\ncbz x16,.Lideck_raw_syscall\nbr x16\n"
".size syscall,.-syscall\n"
".Lideck_raw_syscall:\nmov x8,x0\nmov x0,x1\nmov x1,x2\nmov x2,x3\nmov x3,x4\nmov x4,x5\nmov x5,x6\nsvc #0\n"
"cmn x0,#4095\nb.cs .Lideck_raw_error\nret\n"
".Lideck_raw_error:\nstp x29,x30,[sp,#-32]!\nmov x29,sp\nneg w9,w0\nstr w9,[sp,#16]\n"
"bl __errno_location\nldr w9,[sp,#16]\nstr w9,[x0]\nmov x0,#-1\nldp x29,x30,[sp],#32\nret\n");
#else
/* Native x86 fixtures exercise the ordinary integer-register forwarding path;
 * the production stack-changing ABI regression is run in the AArch64 guest. */
__attribute__((visibility("default"),noinline))
long ideck_syscall(long,long,long,long,long,long,long) __asm__("syscall");
#endif'''
assert s.count(old)==1;s=s.replace(old,new)
(task/'ipc-connect-wait-v3.c').write_text(s)
build=(task/'build-ipc-probe-v2.py').read_text().replace("'ipc-probe-build-v2'","'ipc-probe-build-v3'").replace("'ipc-connect-wait.c'","'ipc-connect-wait-v3.c'")
(task/'build-ipc-probe-v3.py').write_text(build)
record={'old_source_sha256':hashlib.sha256((task/'ipc-connect-wait.c').read_bytes()).hexdigest(),'new_source_sha256':hashlib.sha256(s.encode()).hexdigest(),'change':'AArch64 stack-preserving tail trampoline for every non-futex syscall; same futex C gate/deadline/scope'}
(task/'probe-v3-change.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
