#!/bin/bash

# Notes:
#
# This script is submitted by crontab every 2 days.
# It will check whether resources are available, runs
# the func3 wrapper (to make timing files), and then
# runs the wrapper for func4.

# check that all jobs are done
num_jobs=`squeue -u $(whoami) | wc -l`
if [ $num_jobs -gt 1 ]; then
    echo "Jobs still running, exiting ..."
    exit 0
fi

# update timing files - for everyone. Could be more efficient.
./func3_submit.sh \\
    -p /scratch/madlab/emu_UNC \\
    -s ses-S2 \\
    -t test

# start decon script
~/miniconda3/bin/python func4_submit.py \
    -d /scratch/madlab/emu_UNC/derivatives \
    -t test \
    -s ses-S2 \
    -n 3
