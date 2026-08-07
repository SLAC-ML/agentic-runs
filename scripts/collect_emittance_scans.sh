#!/usr/bin/env bash
#
# Collect the quadrupole-scan files behind the FACET-II emittance evaluations
# into data/facet/emittance-scans/.
#
# This is the script that produced what is already in the repository. It is kept
# for provenance and for re-collection; you do not need to run it to use the
# data. It only works from inside SLAC.
#
#   ./scripts/collect_emittance_scans.sh          # collect
#   ./scripts/collect_emittance_scans.sh --list   # what the dumps reference
#
# On the control-room host these files total about 35 GB, because every scan
# point stores a full camera frame and its background. Copying that into a git
# repository is not sensible, so the stripping runs on the far side and only the
# fit inputs come back, about 14 MB. See the Provenance section of the README
# for exactly what is dropped.
#
# The host is three hops away and each hop authenticates from the one before, so
# this nests ssh rather than using ProxyJump. Commands are base64-encoded on the
# way in to survive three rounds of shell quoting.
#
set -euo pipefail

HOP1="${FACET_HOP1:-s3dflogin}"
HOP2="${FACET_HOP2:-mcclogin}"
HOP3="${FACET_HOP3:-fphysics@facet-srv20}"
REMOTE_ROOT="${FACET_TUNING_ROOT:-/home/fphysics/zhezhang/AgenticOpt/Otter/facet_tuning}"
DEST="data/facet/emittance-scans"

cd "$(dirname "$0")/.."

# Run a command on the control-room host.
remote() {
    local inner outer
    inner=$(printf '%s' "$1" | base64 | tr -d '\n')
    outer=$(printf '%s' "echo $inner | base64 -d | bash" | base64 | tr -d '\n')
    ssh -o BatchMode=yes "$HOP1" \
        "ssh -o BatchMode=yes $HOP2 \"ssh -o BatchMode=yes $HOP3 'echo $outer | base64 -d | bash'\""
}

if [ "${1:-}" = "--list" ]; then
    python3 - <<'PY'
import glob, re
names = set()
for dump in glob.glob("data/facet/campaigns/*/*/automatic_workflow_xopt_*.yaml"):
    for line in open(dump):
        hit = re.search(r"(emittance_scan_\d+\.h5)", line)
        if hit:
            names.add(hit.group(1))
print("\n".join(sorted(names)))
print("(%d files referenced by the optimizer dumps)" % len(names))
PY
    exit 0
fi

echo "Stripping scans on $HOP3 (this reads ~35 GB there and sends back ~1 MB)."

STRIPPER=$(cat <<'PY'
import os, sys, h5py

SKIP = {"raw_images", "processed_images", "background_image"}
PER_POINT_KEEP = {"centroids", "rms_sizes", "rms_sizes_all",
                  "signal_to_noise_ratios", "total_intensities"}
SOURCE_ROOT = os.environ["SOURCE_ROOT"]
OUT_ROOT = "/tmp/emitscans"

def copy_group(src, dst, keep=None):
    for name, obj in src.items():
        if name in SKIP or (keep is not None and name not in keep):
            continue
        if isinstance(obj, h5py.Group):
            below = PER_POINT_KEEP if src.name.endswith("/image_data") else None
            copy_group(obj, dst.create_group(name), keep=below)
        else:
            dst.create_dataset(name, data=obj[()])
        for k, v in obj.attrs.items():
            dst[name].attrs[k] = v

def strip(src_path, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with h5py.File(src_path, "r") as src, h5py.File(out_path, "w") as dst:
        copy_group(src, dst)
        for k, v in src.attrs.items():
            dst.attrs[k] = v
        dst.attrs["stripped_of"] = ", ".join(sorted(SKIP))
        dst.attrs["per_scan_point_kept"] = ", ".join(sorted(PER_POINT_KEEP))
        dst.attrs["original_path"] = src_path

total_in = total_out = count = 0
for campaign in sorted(os.listdir(SOURCE_ROOT)):
    campaign_dir = os.path.join(SOURCE_ROOT, campaign)
    if not os.path.isdir(campaign_dir):
        continue
    for phase in sorted(os.listdir(campaign_dir)):
        phase_dir = os.path.join(campaign_dir, phase)
        if not os.path.isdir(phase_dir):
            continue
        for name in sorted(os.listdir(phase_dir)):
            if not (name.startswith("emittance_scan_") and name.endswith(".h5")):
                continue
            src_path = os.path.join(phase_dir, name)
            out_path = os.path.join(OUT_ROOT, campaign, name)
            try:
                strip(src_path, out_path)
            except Exception as exc:
                print("FAILED %s/%s: %s" % (campaign, name, exc), file=sys.stderr)
                continue
            total_in += os.path.getsize(src_path)
            total_out += os.path.getsize(out_path)
            count += 1
print("%d files, %.1f GB -> %.1f MB" % (count, total_in / 1e9, total_out / 1e6),
      file=sys.stderr)
PY
)

remote "rm -rf /tmp/emitscans
export SOURCE_ROOT='$REMOTE_ROOT'
cat > /tmp/strip_emitscans.py <<'STRIPPER_EOF'
$STRIPPER
STRIPPER_EOF
python3 /tmp/strip_emitscans.py
cd /tmp && tar -czf emitscans.tar.gz emitscans"

echo "Fetching."
mkdir -p "$DEST"
remote 'base64 -w0 /tmp/emitscans.tar.gz' \
  | tr -d '\n' | base64 -d | tar -xzf - -C "$DEST" --strip-components=1

remote 'rm -rf /tmp/emitscans /tmp/emitscans.tar.gz /tmp/strip_emitscans.py'

echo "Collected $(find "$DEST" -name 'emittance_scan_*.h5' | wc -l | tr -d ' ') scans into $DEST/"
echo "Check them with: python scripts/summarize.py"
