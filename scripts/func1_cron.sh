#!/bin/bash

# Notes:
#
# This script is submitted by crontab every 12 hours.
# It will check whether resources are available, and
# then sources the wrapper script.

# check that all jobs are done
num_jobs=`squeue -u $(whoami) | wc -l`
if [ $num_jobs -gt 1 ]; then
    echo "Jobs still running, exiting ..."
    exit 0
fi

# run wrapper
./func1_submit.sh \
    -f ~/bin/licenses/fs_license.txt \
    -i /home/nmuncy/bin/singularities/nipreps_fmriprep_20.2.3.simg \
    -p /scratch/madlab/emu_UNC \
    -m 8 \
    -s ses-S2 \
    -t task-test \
    -r space-MNIPediatricAsym_cohort-5_res-2
    -x /home/data/madlab/singularity-images/templateflow
