#!/bin/bash

# Receives 5 arguments from func1_submit.sh, runs
# singularity version of fMRIprep.
#
# Notes:
#   --skull-strip-template, --output-spaces are hardcoded
#
# Required Input:
#   1: subject id (int)
#   2: singularity image
#   3: BIDs-structured project directory
#   4: FreeSurfer license
#   5: location of templatflow directory


#SBATCH --qos pq_madlab
#SBATCH --account iacc_madlab
#SBATCH -p IB_44C_512G
#SBATCH --nodes 1
#SBATCH --ntasks 1
#SBATCH --cpus-per-task 10
#SBATCH --mem 16000
#SBATCH --job-name nm_fmriprep


# set up
module load singularity-3.8.2

label=$1
sing_img=$2
proj_dir=$3
fs_license=$4
tpflow_dir=$5

# set paths
dset_dir=${proj_dir}/dset
deriv_dir=${proj_dir}/derivatives
work_dir=${deriv_dir}/tmp_work/sub-${label}
mkdir -p $work_dir

# reference template fow, fs, avoid root issues
export SINGULARITYENV_TEMPLATEFLOW_HOME=$tpflow_dir
export FS_LICENSE=$fs_license
cd /

# do job
singularity run --cleanenv $sing_img \
  $dset_dir \
  $deriv_dir \
  participant \
  --participant-label $label \
  --work-dir $work_dir \
  --skull-strip-template MNIPediatricAsym:cohort-5 \
  --output-spaces emur MNIPediatricAsym:cohort-5:res-2 \
  --nthreads 10 \
  --omp-nthreads 10 \
  --fs-license-file $FS_LICENSE \
  --stop-on-first-crash
