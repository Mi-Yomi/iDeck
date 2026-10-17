# Rejected V2 — regression input only

Do not use this library implementation for further Steam runs. Its C syscall
wrapper changes the AArch64 call frame even for stack-changing syscalls.
An actual custom-child-stack clone passes with libc, receives SIGSEGV through
V2, and passes through V3's stack-preserving tail entry. The old narrower ABI
tests missed this case. These source bytes are retained to bind historical
timing receipts and reproduce the failure; they are not a current safe fix.
