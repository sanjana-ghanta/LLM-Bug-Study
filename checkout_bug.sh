#!/bin/bash
# Usage: ./checkout_bug.sh <project> <bug_id>
# Example: ./checkout_bug.sh Lang 1

PROJECT=$1
BUG_ID=$2
OUTDIR=~/llm-bug-study/experiment/bugs/${PROJECT}_${BUG_ID}

mkdir -p $OUTDIR

# Checkout buggy version
defects4j checkout -p $PROJECT -v ${BUG_ID}b -w ${OUTDIR}/buggy

# Checkout patched version
defects4j checkout -p $PROJECT -v ${BUG_ID}f -w ${OUTDIR}/patched

echo "Done! Checked out ${PROJECT} bug ${BUG_ID} to ${OUTDIR}"
