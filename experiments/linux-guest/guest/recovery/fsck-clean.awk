# Pinned e2fsck1.47.2, LC_ALL=C, full -fn scan. Exit0 alone is insufficient:
# PR_NO_OK count problems can print Fix? no without setting the error exit bit.
# Accept only one banner, the five ordered passes and one ordinary summary.
BEGIN { pass = 0; banner = 0; summary = 0; bad = 0 }
/^$/ { next }
/^e2fsck 1\.47\.2 \(1-Jan-2025\)$/ { if (banner++) bad=1; next }
/^Pass 1: Checking inodes, blocks, and sizes$/ { if (pass!=0) bad=1; pass=1; next }
/^Pass 2: Checking directory structure$/ { if (pass!=1) bad=1; pass=2; next }
/^Pass 3: Checking directory connectivity$/ { if (pass!=2) bad=1; pass=3; next }
/^Pass 4: Checking reference counts$/ { if (pass!=3) bad=1; pass=4; next }
/^Pass 5: Checking group summary information$/ { if (pass!=4) bad=1; pass=5; next }
/^\/dev\/vd[ab]: [0-9]+\/[0-9]+ files \([0-9.]+% non-contiguous\), [0-9]+\/[0-9]+ blocks$/ {
    if (pass!=5 || summary++) bad=1
    next
}
{ bad=1 }
END { exit (bad || banner!=1 || pass!=5 || summary!=1) }
