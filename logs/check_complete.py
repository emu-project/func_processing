"""Title.

Desc
"""

# %%
import os
import sys
import glob
import json
import textwrap
import fnmatch
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def check_afni():
    pass


# %%
def main():

    # For testing
    proj_dir = "/Volumes/homes/MaDLab/projects/McMakin_EMUR01"

    task_dict = {
        "ses-S1": {"num_runs": 2, "task_name": "task-study"},
        "ses-S2": {"num_runs": 3, "task_name": "task-test"},
    }
    expected_dict = {
        "afni": [
            "space-MNIPediatricAsym_cohort-5_res-2_desc-WMe_mask.nii.gz",
            "ses-S1_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            "task-study_run-1_space-MNIPediatricAsym_cohort-5_res-2_desc-scaled_bold.nii.gz",
            "task-study_run-2_space-MNIPediatricAsym_cohort-5_res-2_desc-scaled_bold.nii.gz",
            "decon_task-study_UniqueBehs_stats_REML+tlrc.HEAD",
            "ses-S2_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            "task-test_run-1_space-MNIPediatricAsym_cohort-5_res-2_desc-scaled_bold.nii.gz",
            "task-test_run-2_space-MNIPediatricAsym_cohort-5_res-2_desc-scaled_bold.nii.gz",
            "task-test_run-3_space-MNIPediatricAsym_cohort-5_res-2_desc-scaled_bold.nii.gz",
            "decon_task-test_UniqueBehs_stats_REML+tlrc.HEAD",
        ],
        "ashs": ["left_lfseg_corr_usegray", "right_lfseg_corr_usegray"],
        "reface": ["desc-reface"],
    }

    log_dir = os.path.dirname(os.path.abspath(__file__))
    deriv_dir = os.path.join(proj_dir, "derivatives")
    dset_dir = os.path.join(proj_dir, "dset")

    subj_list = sorted([x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")])

    with open(os.path.join(log_dir, "completed.json")) as jf:
        json_dict = json.load(jf)

    # for subj in subj_list:
    json_dict["subjID"].append(subj)
    for exp in expected_dict:
        pass


if __name__ == "__main__":
    main()
