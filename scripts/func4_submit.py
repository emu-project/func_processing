"""Wrapper script to run deconvolution.

This script checks for subjects that have pre-processed EPI data but
no deconvolved data, and if so, submits the subject for deconvolution.
Also, this will only submit the first ~9 subjects it comes across
missing the decon output, to better share resources.

Notes
-----
Assumes subject timing files exists (that func3 worked).
Sbatch stdout/stderr are captured in derivatives/Slurm_out/afniDcn_<time>.

Examples
--------
func4_submit.py \
    -d /scratch/madlab/emu_UNC/derivatives \
    -t test \
    -s ses-S2 \
    -n 3
"""

import os
import fnmatch
from datetime import datetime
import time
import subprocess
from argparse import ArgumentParser
import sys
import pathlib


def get_args():
    """Get and parse args"""
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

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


def main():
    """Submit jobs for subjects missing decon output"""

    # set necessary paths and variables
    args = get_args().parse_args()
    code_dir = pathlib.Path().resolve()
    deriv_dir = args.deriv_dir
    task = args.task_str
    sess = args.sess_str
    num_runs = args.num_runs
    afni_dir = os.path.join(deriv_dir, "afni")

    # make slurm out dir, afni dir
    current_time = datetime.now()
    out_dir = os.path.join(
        deriv_dir, f"""Slurm_out/afniDcn_{current_time.strftime("%y_%m_%d-%H_%M")}""",
    )
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # list of afni subjs
    subj_afni = [x for x in os.listdir(afni_dir) if fnmatch.fnmatch(x, "sub-*")]
    subj_afni.sort()

    # those who need deconvolution
    subj_list = []
    for subj in subj_afni:
        if not os.path.exists(
            os.path.join(afni_dir, subj, sess, f"{task}_decon_stats_REML+tlrc.HEAD")
        ):
            subj_list.append(subj)

    if len(subj_list) == 0:
        return

    # submit jobs
    for subj in subj_list[:10]:

        h_out = os.path.join(out_dir, f"out_{subj}.txt")
        h_err = os.path.join(out_dir, f"err_{subj}.txt")
        h_job = f"""dcn{subj.split("-")[1]}"""

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
                --wrap="~/miniconda3/bin/python {code_dir}/func4_deconvolve.py \
                    -p {subj} \
                    -s {sess} \
                    -t {task} \
                    -n {num_runs} \
                    -a {afni_dir}"
        """
        sbatch_submit = subprocess.Popen(sbatch_job, shell=True, stdout=subprocess.PIPE)
        job_id = sbatch_submit.communicate()[0]
        print(job_id.decode("utf-8"))
        time.sleep(1)


if __name__ == "__main__":
    main()
