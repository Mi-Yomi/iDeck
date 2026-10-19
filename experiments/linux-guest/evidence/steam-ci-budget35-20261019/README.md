# 35/30 minute CI budget and serial source review

Baseline `4f8f70bdfabdf2a8f1dbedc589b7b70f1ed1a4a2`.
`python-tests.log`: full regression,602 tests OK,5 SKIP. Budget tests cover
provider/internal consistency, elapsed preparation, no per-step reset,
expired-before-child refusal and timeout process-group termination/no success.

`qemu-source.json`: independent full size/SHA verification of the actual locked
QEMU10.0.12-utm archive, plus hashes of its regular virtio block and ARM virt
source members. No archive/source bytes are committed here. `linux-source.json`
records the upstream6.18.35 driver/UAPI files read for sysfs and ID-width review;
it is not a full Alpine kernel corresponding-source verification.

`verification.json`: parsed workflow and overlay checks, unchanged functional
cache/payload code, serial fail-closed regression scope and explicit limits.
No Apple/host-QEMU/device execution or CI dispatch/cancellation occurred.
Earlier package staging evidence applies to unchanged resource inputs.
Fresh remaining quota after the coordinator's run and paid OFF remain required.
