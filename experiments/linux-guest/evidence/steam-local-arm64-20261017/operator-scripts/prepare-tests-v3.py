from pathlib import Path
task=Path(__file__).parent
s=(task/'ipc-probe-unit.c').read_text().replace('"ipc-connect-wait.c"','"ipc-connect-wait-v3.c"')
s=s.replace('int main(void) {','#if defined(__aarch64__)\n#define main clone_abi_main\n#include "ipc-clone-stack.c"\n#undef main\n#endif\nint main(void) {')
needle='    puts("{\\"status\\":\\"pass\\",\\"test\\":\\"shape'
assert s.count(needle)==1
s=s.replace(needle,'#if defined(__aarch64__)\n    assert(clone_abi_main()==0);real=next_syscall;next_syscall=NULL;assert(clone_abi_main()==0);next_syscall=real;\n#endif\n'+needle)
(task/'ipc-probe-unit-v3.c').write_text(s)
s=(task/'build-test-ipc-probe-v2.py').read_text().replace('ipc-probe-tests-build-v2','ipc-probe-tests-build-v3').replace('ipc-probe-build-v2','ipc-probe-build-v3').replace('ipc-connect-wait.c','ipc-connect-wait-v3.c').replace('ipc-probe-unit.c','ipc-probe-unit-v3.c')
(task/'build-test-ipc-probe-v3.py').write_text(s)
print('prepared v3 unit and native/ARM ABI builds; includes real and raw clone-stack paths')
