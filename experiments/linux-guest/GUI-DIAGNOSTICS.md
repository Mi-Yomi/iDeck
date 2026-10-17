# Desktop reports when startup is blocked

The Desktop screen always has **Share report**, **Diagnostics** and **Stop Linux**
in its top safe-area bar. Report actions are outside the guest input controls and
their scrolling panel. Only Stop depends on VM state. The short status above the
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
2. On the already refused disk, make one normal Start attempt. Confirm the existing
   needsRecovery refusal remains. Share report must be accessible without scrolling
   through F keys; its MD and the current startup MD should show the exact same
   four observations. Export both for review. Do not infer their values in advance.
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

## Disk preservation/export remains separate

There is deliberately no disk backup, repair or reset button in this change.
A future exporter must establish that QEMU cannot still write, validate the source
identity and hold an exclusive lock for the entire bounded copy, check destination
space, and verify/synchronize its output before offering a share. A disabled Stop
button or ready=false alone proves none of this; a returned main loop also retains
its owner thread and disk lock in the current lifecycle. It must preserve the
source on every failure and must not introduce cleanup/unregister/unlock as a
shortcut. Recovery should operate on a verified preserved copy in a separate,
explicit workflow. No owner disk has been accessed or repaired in this task.
