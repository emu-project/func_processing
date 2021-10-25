"""Wrapper script to finish pre-processing.

This script checks for subjects that have fMRIprep output but
lack scaled and blurred (smoothed) EPI data. If any are detected,
then they are passed to func2_finish_preproc.py

Notes
-----
Sbatch stdout/stderr are captured in derivatives/Slurm_out/afniPP_<time>.

Examples
--------
func2_submit.py \
    -d /scratch/madlab/emu_UNC/derivatives \
    -t test \
    -s ses-S2 \
    -n 3 \
    -r space-MNIPediatricAsym_cohort-5_res-2
"""

import os
import fnmatch
from datetime import datetime
import time
import subprocess
import pathlib
from argparse import ArgumentParser
import sys


def get_args():
    parser = ArgumentParser("Receive bash CLI args")
    requiredNamed = parser.add_argument_group("required named arguments")
    requiredNamed.add_argument(
        "-d",
        "--deriv-dir",
        help="/path/to/bids/project_directory/derivatives",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-t",
        "--task-str",
        help="BIDS task-string (test, for task-test)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-s", "--sess-str", help="BIDS ses-string (ses-S2)", type=str, required=True,
    )
    requiredNamed.add_argument(
        "-n", "--num-runs", help="Number of EPI runs (int)", type=int, required=True,
    )
    requiredNamed.add_argument(
        "-r",
        "--refspace-str",
        help="fMRIprep reference space string (space-MNIPediatricAsym_cohort-5_res-2)",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


def main():
    """Check for data that completed fMRIprep but not afni pre-processing."""
    # set necessary paths and variables
    args = get_args().parse_args()
    deriv_dir = args.deriv_dir
    task = args.task_str
    sess = args.sess_str
    num_runs = args.num_runs
    space = args.refspace_str
    code_dir = pathlib.Path().resolve()

    prep_dir = os.path.join(deriv_dir, "fmriprep")
    afni_dir = os.path.join(deriv_dir, "afni")

    # make slurm_out dir, afni dir
    current_time = datetime.now()
    out_dir = os.path.join(
        deriv_dir, f"""Slurm_out/afniPP_{current_time.strftime("%y_%m_%d-%H_%M")}""",
    )
    for h_dir in [out_dir, afni_dir]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # list of fmriprep subjs
    subj_fmriprep = [
        x.split(".")[0] for x in os.listdir(prep_dir) if fnmatch.fnmatch(x, "*.html")
    ]
    subj_fmriprep.sort()

    # those who have fmriprep and need to finish pre-processing
    subj_list = []
    for subj in subj_fmriprep:
        prep_bool = os.path.exists(
            os.path.join(
                prep_dir,
                subj,
                sess,
                "func",
                f"{subj}_{sess}_task-{task}_run-1_{space}_desc-preproc_bold.nii.gz",
            )
        )
        afni_bool = os.path.exists(
            os.path.join(afni_dir, subj, sess, f"run-1_{task}_scale+tlrc.HEAD")
        )
        if prep_bool and not afni_bool:
            subj_list.append(subj)

    # account for no missing data
    if len(subj_list) == 0:
        return

    # submit jobs
    for subj in subj_list:

        h_out = os.path.join(out_dir, f"out_{subj}.txt")
        h_err = os.path.join(out_dir, f"err_{subj}.txt")
        h_job = f"""afni{subj.split("-")[1]}"""

        sbatch_job = f"""
            sbatch \
                -J "{h_job}" \
                -t 00:30:00 \
                --mem=4000 \
                --ntasks-per-node=1 \
                -p IB_44C_512G  \
                -o {h_out} -e {h_err} \
                --account iacc_madlab \
                --qos pq_madlab \
                --wrap="~/miniconda3/bin/python {code_dir}/func2_finish_preproc.py \
                    -p {subj} \
                    -s {sess} \
                    -t {task} \
                    -n {num_runs} \
                    -d {deriv_dir}"
        """
        sbatch_submit = subprocess.Popen(sbatch_job, shell=True, stdout=subprocess.PIPE)
        job_id = sbatch_submit.communicate()[0]
        print(job_id.decode("utf-8"))
        time.sleep(1)


if __name__ == "__main__":
    main()
