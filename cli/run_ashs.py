"""Title.

Desc.
"""
# %%
import os
import sys
import fnmatch
import glob
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from workflow import control_ashs
from resources.afni import submit


# %%
def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    required_args = parser.add_argument_group("required named arguments")
    required_args.add_argument(
        "-p",
        "--proj-dir",
        help="/path/to/BIDS/project/dir",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-s",
        "--share-dir",
        help="/path/to/SharePoint/Florida International University",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-t",
        "--token-github",
        help="PAT for github.com/emu-project",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Title."""

    # For testing
    proj_dir = "/home/data/madlab/McMakin_EMUR01"
    scratch_dir = "/scratch/madlab/emu_ashs"
    sess = "ses-S1"
    batch_num = 3

    # # receive passed args
    # args = get_args().parse_args()
    # proj_dir = args.proj_dir
    # share_dir = args.share_dir
    # pat_github_emu = args.token_github

    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, "derivatives/ashs")

    # submit all subjects to ASHS
    while_count = 0
    work_status = True
    while work_status:

        # make dict of dset subjects which have T1- and T2-weighted data
        # and do not have ASHS output
        subj_list_all = [x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")]
        subj_list_all.sort()
        subj_dict = {}
        for subj in subj_list_all:
            ashs_exists = os.path.exists(
                os.path.join(
                    deriv_dir, subj, sess, f"{subj}_left_lfseg_corr_usegray.nii.gz"
                )
            )
            t1_files = glob.glob(f"{dset_dir}/{subj}/**/*T1w.nii.gz", recursive=True)
            t2_files = glob.glob(f"{dset_dir}/{subj}/**/*PD.nii.gz", recursive=True)
            if t1_files and t2_files and not ashs_exists:

                # give list item in list for field map correction, multiple acquisitions
                subj_dict[subj] = {}
                subj_dict[subj]["t1-file"] = t1_files[-1].split("/")[-1]
                subj_dict[subj]["t2-file"] = t2_files[-1].split("/")[-1]

        # kill while loop if all subjects have output, also don't
        # let job run longer than a few days
        if len(subj_dict.keys()) == 0 or while_count > 72:
            work_status = False

        # check to make sure no pending jobs exist
        sq_check = subprocess.Popen(
            "squeue -u $(whoami)", shell=True, stdout=subprocess.PIPE
        )
        out_lines = sq_check.communicate()[0].decode("utf-8")
        if not out_lines.count("\n") < 2:
            continue

        # submit jobs for N subjects that don't have output in deriv_dir
        for subj in list(subj_dict)[:batch_num]:
            # anat_dir = os.path.join(dset_dir, subj)
            control_ashs.control_hipseg(
                anat_dir,
                deriv_dir,
                work_dir,
                atlas_dir,
                sing_img,
                subj,
                t1_file,
                t2_file,
                atlas_str,
            )


if __name__ == "__main__":
    main()
