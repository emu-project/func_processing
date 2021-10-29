# %%
"""Finish pre-processing on EPI data.

Copy relevant files from derivatives/fmriprep to derivatives/afni,
then blur and scale EPI data. Also creates EPI-T1 intersection
and tissue class masks.

Notes
-----
Requires AFNI and c3d.

Examples
--------
func2_finish_preproc.py \\
    -p sub-4020 \\
    -t task-test \\
    -s sess-S2 \\
    -n 3 \\
    -d /scratch/madlab/emu_UNC/derivatives \\
    -r space-MNIPediatricAsym_cohort-5_res-2
"""
# %%
import os
import sys
import glob
from argparse import ArgumentParser, RawTextHelpFormatter
from resources.afni import copy, process, masks


# %%
def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    requiredNamed = parser.add_argument_group("required named arguments")
    requiredNamed.add_argument(
        "-p",
        "--part-id",
        help="Participant ID (sub-1234)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-t",
        "--task-str",
        help="BIDS task-string (task-test)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-s",
        "--sess-str",
        help="BIDS ses-string (ses-S2)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-n",
        "--num-runs",
        help="Number of EPI runs (int)",
        type=int,
        required=True,
    )
    requiredNamed.add_argument(
        "-d",
        "--deriv-dir",
        help="/path/to/project/derivatives",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-r",
        "--ref-tpl",
        help="tplflow ID string",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Move data through AFNI pre-processing."""

    # # For testing
    # deriv_dir = "/scratch/madlab/emu_test/derivatives"
    # subj = "sub-4002"
    # sess = "ses-S2"
    # task = "task-test"
    # num_runs = 3
    # tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"

    # get passed arguments
    args = get_args().parse_args()
    subj = args.part_id
    sess = args.sess_str
    task = args.task_str
    num_runs = args.num_runs
    deriv_dir = args.deriv_dir
    tplflow_str = args.ref_tpl

    # setup directories
    prep_dir = os.path.join(deriv_dir, "fmriprep")
    afni_dir = os.path.join(deriv_dir, "afni")
    work_dir = os.path.join(afni_dir, subj, sess)
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    # get fMRIprep data
    afni_data = copy.copy_data(
        prep_dir, work_dir, subj, sess, task, num_runs, tplflow_str
    )

    # blur data
    subj_num = subj.split("-")[-1]
    afni_data = process.blur_epi(work_dir, subj_num, afni_data)

    # make masks
    afni_data = masks.make_intersect_mask(work_dir, subj_num, afni_data)
    afni_data = masks.make_tissue_masks(work_dir, subj_num, afni_data)

    # scale data
    afni_data = process.scale_epi(work_dir, subj_num, sess, task, afni_data)

    # check for files
    assert "Missing" not in afni_data.values(), "Missing value (file) in afni_data."

    # clean
    for tmp_file in glob.glob(f"{work_dir}/tmp*"):
        os.remove(tmp_file)
    for sbatch_file in glob.glob(f"{work_dir}/sbatch*"):
        os.remove(sbatch_file)


if __name__ == "__main__":
    main()
