#!/bin/bash
# Checkout Lang bugs 21-61, skipping deprecated ones

DEPRECATED="25 48"
EXPERIMENT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUGS_DIR="$EXPERIMENT_DIR/data/bugs"

for i in $(seq 21 61); do
    if echo "$DEPRECATED" | grep -qw "$i"; then
        echo "Skipping deprecated Lang_$i"
        continue
    fi

    # Skip if already extracted
    if [ -f "$BUGS_DIR/Lang_$i/data.json" ]; then
        echo "Skipping Lang_$i (already done)"
        continue
    fi

    echo "========================================="
    echo "Processing Lang_$i..."
    echo "========================================="

    BUG_DIR="$BUGS_DIR/Lang_$i"
    mkdir -p "$BUG_DIR"

    defects4j checkout -p Lang -v ${i}b -w "$BUG_DIR/buggy"
    defects4j checkout -p Lang -v ${i}f -w "$BUG_DIR/patched"
    python3 "$EXPERIMENT_DIR/scripts/extract/extract_bug.py" Lang $i

    echo "Done: Lang_$i"
done

echo "All done!"
