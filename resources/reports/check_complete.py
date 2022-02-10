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
def check_preproc(proj_dir, code_dir, pat_github_emu, new_df=False, one_subj=False):
    """Check for files in expected_dict.

    In order to determine which participants need pre-processing,
    and which have files on either the NAS or HPC, make a dataframe
    of which participants have which pre-processed files.

    This will use strings from expected_dict to create a dataframe. In
    order to keep things synchronized, it will git clone/pull the repo
    and add/commit/push the updated logs/completed_preprocessing.tsv.

    Parameters
    ----------
    proj_dir : str
        Path to BIDS-organized project directory, for
        finding dset and derivatives
    code_dir : str
        Path to desired/existing location of https://github.com/emu-project/func_processing.git
    pat_github_emu : str
        Personal Access Token to https://github.com/emu-project
    new_df : bool
        Whether to generate a completely new logs/completed_preprocessing.tsv,
        use "new_df=True" when expected_dict gets updated with new files.
    one_subj : bool/str
        Whether to check for data from single subject. If true, supply
        BIDS-formatted subject string.
        (e.g. one_subj="sub-4001")

    Notes
    -----
    expected_dict should have the following organization:
        - each key corresponds to a derivatives directory
        - the value of each key is a list of tuples
        - one tuple per file to search for
        - tuple[0] is a string that matches a column in col_names
            and a column of logs/completed_preprocessing.tsv
        - tuple[1] is a string used to find the single file via glob
        - multiple decons are supported for each session via
            decon_<sess>_<int>
    """

    # For testing
    proj_dir = (
        "/home/data/madlab/McMakin_EMUR01"
        if platform.system() == "Linux"
        else "/Volumes/homes/MaDLab/projects/McMakin_EMUR01"
    )
    code_dir = "/home/nmuncy/compute/func_processing"
    pat_github_emu = os.environ["TOKEN_GITHUB_EMU"]
    one_subj = "sub-4168"
    new_df = False

    expected_dict = {
        "afni": [
            ("wme_mask", "desc-WMe_mask"),
            (
                "intersect_ses-S1",
                "ses-S1_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            ),
            (
                "intersect_ses-S2",
                "ses-S2_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            ),
            ("scaled_ses-S2_1", "run-1_*_desc-scaled_bold"),
            ("scaled_ses-S2_2", "run-2_*_desc-scaled_bold"),
            ("scaled_ses-S2_3", "run-3_*_desc-scaled_bold"),
            ("decon_ses-S1_1", "decon_task-study_UniqueBehs_stats_REML+tlrc.HEAD"),
            ("decon_ses-S2_1", "decon_task-test_UniqueBehs_stats_REML+tlrc.HEAD"),
        ],
        "ashs": [
            ("ashs_L", "left_lfseg_corr_usegray"),
            ("ashs_R", "right_lfseg_corr_usegray"),
        ],
        "reface": [("reface", "desc-reface")],
    }

    col_names = [
        "subjID",
        "wme_mask",
        "intersect_ses-S1",
        "intersect_ses-S2",
        "scaled_ses-S2_1",
        "scaled_ses-S2_2",
        "scaled_ses-S2_3",
        "decon_ses-S1_1",
        "decon_ses-S2_1",
        "ashs_L",
        "ashs_R",
        "reface",
    ]

    assert len(col_names) == 1 + sum(
        [
            len(expected_dict[x])
            for x in expected_dict
            if isinstance(expected_dict[x], list)
        ]
    ), "Unequal number of expected_dict values and col_names."

    # get, update repo
    repo_origin = f"https://{pat_github_emu}:x-oauth-basic@github.com/emu-project/func_processing.git"
    repo_local = code_dir
    try:
        print(f"Cloning repo to {repo_local}")
        repo = git.Repo.clone_from(repo_origin, repo_local)
    except:
        print(f"Updating repo: {repo_local}")
        repo = git.Repo(repo_local)
        repo.remotes.origin.pull()

    # set up
    log_dir = os.path.join(code_dir, "logs")
    completed_tsv = os.path.join(log_dir, "completed_preprocessing.tsv")
    deriv_dir = os.path.join(proj_dir, "derivatives")
    dset_dir = os.path.join(proj_dir, "dset")

    # determine subjects from dset
    if one_subj:
        subj_list = [one_subj]
    else:
        subj_list = sorted(
            [x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")]
        )

    # make new completed_tsv
    if new_df:
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

                # determine column index, only continue if empty
                ind_col = df_comp.columns.get_loc(expected_dict[deriv][h_count][0])
                if pd.isna(df_comp.iloc[ind_row, ind_col]).bool() is False:
                    continue

                # determine file str, find file in derivatives, update df cell with creation time
                deriv_str = expected_dict[deriv][h_count][1]
                deriv_file = glob.glob(
                    f"{deriv_dir}/{deriv}/{subj}/**/*{deriv_str}*", recursive=True
                )
                if deriv_file:
                    df_comp.iloc[ind_row, ind_col] = time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.strptime(time.ctime(os.path.getmtime(deriv_file[0]))),
                    )

    # keep dataframe sorted, write
    df_comp.sort_values(by=["subjID"])
    df_comp.to_csv(completed_tsv, index=False, sep="\t")

    # update repo origin
    now = datetime.datetime.now()
    repo.git.add(completed_tsv)
    repo.index.commit(
        f"""Updated completed_preprocess.tsv at {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )
    origin = repo.remote(name="origin")
    origin.push()
