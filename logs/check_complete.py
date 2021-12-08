"""Title.

Desc
"""

# %%
import os
import sys
import glob
import json
import textwrap
import platform
import pandas as pd
import numpy as np
import fnmatch
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def main():

    # determine env, path
    proj_dir = (
        "/home/data/madlab/McMakin_EMUR01"
        if platform.system() == "Linux"
        else "/Volumes/homes/MaDLab/projects/McMakin_EMUR01"
    )

    expected_dict = {
        "afni": [
            [
                "ses-S1_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
                "intersect_1",
            ],
            ["decon_task-study_UniqueBehs_stats_REML+tlrc.HEAD", "decon_1"],
            [
                "ses-S2_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
                "intersect_2",
            ],
            ["decon_task-test_UniqueBehs_stats_REML+tlrc.HEAD", "decon_2"],
        ],
        "ashs": [
            ["left_lfseg_corr_usegray", "ashs_L"],
            ["right_lfseg_corr_usegray", "ashs_R"],
        ],
        "reface": [["desc-reface", "reface"]],
    }

    log_dir = os.path.dirname(os.path.abspath(__file__))
    completed_tsv = os.path.join(log_dir, "completed.tsv")
    deriv_dir = os.path.join(proj_dir, "derivatives")
    dset_dir = os.path.join(proj_dir, "dset")

    subj_list = sorted([x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")])

    if not os.path.exists(completed_tsv):
        col_names = [
            "subjID",
            "intersect_1",
            "intersect_2",
            "decon_1",
            "decon_2",
            "ashs_L",
            "ashs_R",
            "reface",
        ]
        df = pd.DataFrame(columns=col_names)
        df["subjID"] = subj_list
        df.to_csv(completed_tsv, index=False, sep="\t")

    df_comp = pd.read_csv(completed_tsv, sep="\t")

    for subj in subj_list:
        print(f"Checking {subj} ...")
        if not df_comp["subjID"].str.contains(subj).any():
            df_comp.loc[len(df_comp.index), "subjID"] = subj
        ind_row = df_comp.index[df_comp["subjID"] == subj].tolist()

        for deriv in expected_dict:
            for h_count, _ in enumerate(expected_dict[deriv]):
                deriv_str = expected_dict[deriv][h_count][0]
                ind_col = df_comp.columns.get_loc(expected_dict[deriv][h_count][1])
                deriv_file = glob.glob(
                    f"{deriv_dir}/{deriv}/{subj}/**/*{deriv_str}*", recursive=True
                )
                h_input = True if deriv_file else False
                df_comp.iloc[ind_row, ind_col] = h_input

    df_comp.sort_values(by=["subjID"])
    df_comp.to_csv(completed_tsv, index=False, sep="\t")


if __name__ == "__main__":
    main()
