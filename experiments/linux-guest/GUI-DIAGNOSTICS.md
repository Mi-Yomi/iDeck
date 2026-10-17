# Desktop reports when startup is blocked

The Desktop screen always has **Share report** and **Diagnostics** in its top
safe-area bar, alongside Recover disk before an attempt or Stop Linux afterwards.
Report actions are outside the guest input controls and their scrolling panel.
Only VM actions depend on runtime state. The short status above the
display is limited to three lines; Diagnostics shows the full status and errors.
Opening reports releases held guest input and dismisses the guest keyboard.

Share report offers the current session `.md` file. If it was not created, the
current startup-journal `.md` is used. If neither is available, Diagnostics opens
and shows the export error or absence of reports. It does not silently substitute
an older attempt. Diagnostics lists saved startup attempts with explicit MD share
actions, refresh, and an optional recognized-native-log-signature summary per
selected attempt. These actions do not start JIT or a VM. Arbitrary log text and
user-file contents are excluded from the MD exports.

For an existing disk, the ordinary preboot validator records four fields from its
same bounded1024-byte superblock read while holding its existing exclusive lock:

| Field | Exported value |
| --- | --- |
| RECOVER bit | SET/CLEAR, feature_incompat bit0x4 |
| state | Raw unsigned16-bit value at0x3a |
| last_orphan | Raw unsigned32-bit value at0xe8 |
| error_count | Raw unsigned32-bit value at0x194 |

Observation occurs after magic/checksum/UUID/features validation. A failed earlier
guard leaves these fields UNKNOWN/absent. The dirty guard still requires RECOVER
clear, state1, last_orphan0 and error_count0. A refusal does not mount, recreate or
repair the disk. The durable failure code is needsRecovery, rather than unknown.
These observations do not prove a cause or replace offline filesystem review.
An older IPA did not capture these fields; updating cannot reconstruct old values.

## Device check for the next coordinated build

Use the existing private GUI payload and the same app identity/storage; no new
guest payload is needed. Keep the existing owner disk intact.

1. Open Desktop before Start. In landscape and portrait, verify both report actions
   remain visible. Open Diagnostics, read full status, share an explicitly selected
   saved MD and dismiss the sheet. This must not start Linux/JIT.
2. On the already refused disk, make one normal Start desktop attempt. Its original
   clean-validator must still refuse needsRecovery; the workflow then selects a
   separate clone-only recovery VM before native entry. Confirm backup/work stages,
   or an explicit low-space/ownership failure. Share report must remain accessible
   without scrolling F keys; session and current startup MD should show the same
   four original observations. Export both; do not infer values in advance.
3. Verify saved older attempts are separately selectable and export failures/no
   report are visible. Reports must not include file contents, console commands,
   arbitrary native log text or arbitrary Error descriptions.
4. On a separately authorized clean test installation, check the top bar with the
   guest keyboard shown and after dismissing it. Opening/closing reports must not
   leave held keys/buttons. Continue the existing two-boot/two-clean-Stop device
   acceptance; the owner's first GUI/input report alone does not complete it.

UIKit layout, system sharing, Apple compilation and this device checklist have
not been run by the cloud executor. Python source guards and offline source staging
are not substitutes for those checks. No CI is dispatched by this task.

## Disk recovery and export

The internal verified backup, recovery and fresh-process activation are described
in [GUI-RECOVERY.md](GUI-RECOVERY.md). No owner disk was accessed by this executor.
Unknown fsck output still fails closed. The scoped summary-counter method now
passes two old-seed host cycles; current9c4d and device remain unverified. The old
acceptance is withdrawn. A new suffix, body/header scope verification where used,
and SCAN_CLEAN are required in addition to code0 and a clean superblock.
There is no raw disk share/export, general repair or reset button. A future raw
exporter must establish that QEMU cannot still write, validate the source
identity and hold an exclusive lock for the entire bounded copy, check destination
space, and verify/synchronize its output before offering a share. A disabled Stop
button or ready=false alone proves none of this; a returned main loop also retains
its owner thread and disk lock in the current lifecycle. It must preserve the
source on every failure and must not introduce cleanup/unregister/unlock as a
shortcut. Recovery operates on an unmounted separate copy, with original/backup
preserved; activation waits for a new app process and revalidated locks/hashes.
