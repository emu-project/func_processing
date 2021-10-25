#!/bin/bash

# Notes:
#
# This script is submitted by crontab every 24 hours.
# It will check whether resources are available, and
# then runs the python wrapper script.

# check that all jobs are done
num_jobs=`squeue -u $(whoami) | wc -l`
if [ $num_jobs -gt 1 ]; then
    echo "Jobs still running, exiting ..."
    exit 0
fi

# run wrapper
~/miniconda3/bin/python func2_submit.py \
    -d /scratch/madlab/emu_UNC/derivatives \
    -t test \
    -s ses-S2 \
    -n 3 \
    -r space-MNIPediatricAsym_cohort-5_res-2