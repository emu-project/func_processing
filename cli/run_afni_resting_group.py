#!/usr/bin/env python

"""Title.

Desc
"""

# %%
import os
import sys
import time
import pandas as pd
import textwrap
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def main():
    """Title.

    Desc
    """

    # For testing
    proj_dir = "/home/data/madlab/McMakin_EMUR01"
    sess = "ses-S2"
    task = "task-rest"
    code_dir = "/home/nmuncy/compute/func_processing"
    atlas_dir = "/home/data/madlab/atlases/templateflow/tpl-MNIPediatricAsym/cohort-5"

    # set up
    log_dir = os.path.join(code_dir, "logs")
    afni_dir = os.path.join(proj_dir, "afni")
    analysis_dir = os.path.join(afni_dir, "analyses")
    for h_dir in [afni_dir, analysis_dir]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # get completed logs
    df_log = pd.read_csv(os.path.join(log_dir, "completed_preprocessing.tsv"), sep="\t")

    # start group_data with template gm mask
    group_data = {}
    tpl_gm = os.path.join(
        atlas_dir, "tpl-MNIPediatricAsym_cohort-5_res-2_label-GM_probseg.nii.gz"
    )
    assert os.path.exists(tpl_gm), f"Template GM not detected: {tpl_gm}"
    group_data["mask-gm"] = tpl_gm

    # make list of subjs with req data
    subj_list_all = df_log["subjID"].tolist()
    subj_list = []
    for subj in subj_list_all:
        print(f"Checking {subj} for required files ...")





if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 or emuR01_unc required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
