#!/bin/bash
# Checkout Lang bugs 21-61 and extract bug data

set -e
EXPERIMENT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUGS_DIR="$EXPERIMENT_DIR/data/bugs"

for i in $(seq 21 61); do
    echo "========================================="
    echo "Processing Lang_$i..."
    echo "========================================="
    
    BUG_DIR="$BUGS_DIR/Lang_$i"
    mkdir -p "$BUG_DIR"
    
    # Checkout buggy and patched versions
    defects4j checkout -p Lang -v ${i}b -w "$BUG_DIR/buggy"
    defects4j checkout -p Lang -v ${i}f -w "$BUG_DIR/patched"
    
    # Extract bug data into data.json
    python3 "$EXPERIMENT_DIR/scripts/extract/extract_bug.py" Lang $i
    
    echo "Done: Lang_$i"
    echo ""
done

echo "All Lang bugs 21-61 checked out and extracted!"
