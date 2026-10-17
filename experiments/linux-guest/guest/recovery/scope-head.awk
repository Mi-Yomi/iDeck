# Compare exactly one4KiB primary block. Only global free counters and normal
# mount/unmount bookkeeping may change; all other bytes must remain identical.
FNR==1 { file++ }
{
    for (i=1;i<=NF;i++) {
        if ($i !~ /^[0-9]+$/ || $i<0 || $i>255) bad=1
        if (file==1) before[n++]=$i
        else if (file==2) after[m++]=$i
        else bad=1
    }
}
function u16(offset) { return before[1024+offset]+256*before[1025+offset] }
function u32(offset) { return u16(offset)+65536*u16(offset+2) }
function allowed(position,offset) {
    offset=position-1024
    return (offset>=12 && offset<20) || (offset>=44 && offset<54) ||
           (offset>=376 && offset<384) || (offset>=1020 && offset<1024)
}
END {
    if (bad || n!=4096) exit 1
    # Exact GUI features; no pending journal, orphan list, error state/history.
    if (u16(56)!=61267 || u16(58)!=1 || u32(96)!=194 || u32(232)!=0 || u32(404)!=0) exit 1
    if (eligible) { if (file!=1) exit 1; exit 0 }
    if (file!=2 || m!=4096) exit 1
    for (i=0;i<4096;i++) if (before[i]!=after[i] && !allowed(i)) exit 1
}
