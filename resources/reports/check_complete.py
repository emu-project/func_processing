"""Title.

Desc
"""

# %%
import os
import time
import datetime
import glob
import git
import platform
import pandas as pd
import fnmatch


# %%
def check_preproc(proj_dir, code_dir):
    """Desc.

    Test.
    """

    # # For testing
    # # determine env, path
    # proj_dir = (
    #     "/home/data/madlab/McMakin_EMUR01"
    #     if platform.system() == "Linux"
    #     else "/Volumes/homes/MaDLab/projects/McMakin_EMUR01"
    # )
    code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    # For each derivative directory in proj_dir, a key
    # with associated tuples exist for file to be checked.
    # One tuple should exist per file to check, and tuple[0]
    # should contain the completed_tsv column name while tuple[1]
    # contains the file string to search for
    # Tuple[0] = column name of completed_tsv, tuple[1] = file name
    #   e.g. "afni": [["intersect_1", "ses-S1_foo_desc-intersect_mask.nii.gz"]]
    expected_dict = {
        "afni": [
            [
                "intersect_1",
                "ses-S1_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            ],
            ["decon_1", "decon_task-study_UniqueBehs_stats_REML+tlrc.HEAD"],
            [
                "intersect_2",
                "ses-S2_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            ],
            ["decon_2", "decon_task-test_UniqueBehs_stats_REML+tlrc.HEAD"],
        ],
        "ashs": [
            ["ashs_L", "left_lfseg_corr_usegray"],
            ["ashs_R", "right_lfseg_corr_usegray"],
        ],
        "reface": [["reface", "desc-reface"]],
    }

    # update repo
    repo = git.Repo(code_dir)
    repo.remotes.origin.pull()

    # set up
    log_dir = os.path.join(code_dir, "logs")
    completed_tsv = os.path.join(log_dir, "completed_preprocessing.tsv")
    deriv_dir = os.path.join(proj_dir, "derivatives")
    dset_dir = os.path.join(proj_dir, "dset")

    # determine subjects from dset
    subj_list = sorted([x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")])

    # make new completed_tsv if one does not exist
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

    # read in completed_tsv
    df_comp = pd.read_csv(completed_tsv, sep="\t")

    # check each subject for data in expected_dict
    for subj in subj_list:
        print(f"Checking {subj} ...")

        # add subject to df if they are new, determine subj df row index
        if not df_comp["subjID"].str.contains(subj).any():
            df_comp.loc[len(df_comp.index), "subjID"] = subj
        ind_row = df_comp.index[df_comp["subjID"] == subj].tolist()

        # look for each file in each key of expected_dict, by tuple index
        for deriv in expected_dict:
            for h_count, _ in enumerate(expected_dict[deriv]):

                # determine column index, file str, find file in derivatives
                ind_col = df_comp.columns.get_loc(expected_dict[deriv][h_count][0])
                deriv_str = expected_dict[deriv][h_count][1]
                deriv_file = glob.glob(
                    f"{deriv_dir}/{deriv}/{subj}/**/*{deriv_str}*", recursive=True
                )

                # update df cell with creation time
                if deriv_file:
                    df_comp.iloc[ind_row, ind_col] = time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.strptime(time.ctime(os.path.getmtime(deriv_file[0]))),
                    )

    # keep dataframe sorted, write
    df_comp.sort_values(by=["subjID"])
    df_comp.to_csv(completed_tsv, index=False, sep="\t")

    # update repo
    now = datetime.datetime.now()
    repo.git.add(completed_tsv)
    repo.index.commit(
        f"""Updated completed_preprocess.tsv at {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )
    origin = repo.remote(name="origin")
    origin.push()
