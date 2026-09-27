#!/bin/bash

EXPERIMENT_DIR=~/llm-bug-study/experiment
BUGS_DIR=$EXPERIMENT_DIR/bugs

mkdir -p $BUGS_DIR

# 20 Lang bugs
LANG_BUGS=(1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20)

# 20 Math bugs
MATH_BUGS=(1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20)

# 10 Chart bugs
CHART_BUGS=(1 2 3 4 5 6 7 8 9 10)

checkout_and_extract() {
    PROJECT=$1
    BUG_ID=$2
    OUTDIR=$BUGS_DIR/${PROJECT}_${BUG_ID}

    if [ -f "$OUTDIR/data.json" ]; then
        echo "Skipping ${PROJECT}-${BUG_ID}, already done"
        return
    fi

    echo "Processing ${PROJECT}-${BUG_ID}..."
    mkdir -p $OUTDIR

    defects4j checkout -p $PROJECT -v ${BUG_ID}b -w ${OUTDIR}/buggy -q
    defects4j checkout -p $PROJECT -v ${BUG_ID}f -w ${OUTDIR}/patched -q

    python3 $EXPERIMENT_DIR/extract_bug.py $PROJECT $BUG_ID
    echo "Done: ${PROJECT}-${BUG_ID}"
}

for id in "${LANG_BUGS[@]}"; do
    checkout_and_extract Lang $id
done

for id in "${MATH_BUGS[@]}"; do
    checkout_and_extract Math $id
done

for id in "${CHART_BUGS[@]}"; do
    checkout_and_extract Chart $id
done

echo ""
echo "All done! Bugs saved to $BUGS_DIR"
