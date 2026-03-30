#!/bin/bash
BUGS_DIR="/Users/sunny/llm-bug-study/experiment/bugs"

checkout_bug() {
    PROJECT=$1
    BUG_ID=$2
    OUTDIR="$BUGS_DIR/${PROJECT}_${BUG_ID}"

    if [ -f "$OUTDIR/data.json" ]; then
        echo "Skipping ${PROJECT}-${BUG_ID}, already done"
        return
    fi

    echo "Checking out ${PROJECT}-${BUG_ID}..."
    mkdir -p "$OUTDIR"
    defects4j checkout -p $PROJECT -v ${BUG_ID}b -w "$OUTDIR/buggy" -q
    defects4j checkout -p $PROJECT -v ${BUG_ID}f -w "$OUTDIR/patched" -q
    python3 /Users/sunny/llm-bug-study/experiment/extract_bug.py $PROJECT $BUG_ID
    echo "Done: ${PROJECT}-${BUG_ID}"
}

for i in $(seq 1 20); do checkout_bug Lang $i; done
for i in $(seq 2 20); do checkout_bug Math $i; done
for i in $(seq 1 10); do checkout_bug Chart $i; done

echo "All done!"
