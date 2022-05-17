"""Functions for checking pre-processing status.

Pull and update logs of completed_preprocessing.tsv.
"""

# %%
import os
import time
import datetime
import glob
import fnmatch
import io
import git
import requests
import pandas as pd


# %%
def clone_guid(pat_github_emu):
    """Clone pseudo_guid_list.csv.

    Parameters
    ----------
    pat_github_emu: str
        personal access token for github.com/emu-project

    Returns
    -------
    df_guid : pandas.DataFrame
        dataframe of subject ID, GUIDs, comments
    """
    req = requests.get(
        "https://raw.githubusercontent.com/emu-project/guid_list/master/guid_list.csv",
        headers={
            "accept": "application/vnd.github.v3.raw",
            "authorization": "token {}".format(pat_github_emu),
        },
    )
    df_guid = pd.read_csv(io.StringIO(req.text), index_col=False)
    return df_guid


# %%
def check_preproc(proj_dir, code_dir, pat_github_emu, new_df, one_subj=False):
    """Check for files in expected_dict.

    In order to determine which participants need pre-processing,
    and which have files on either the NAS or HPC, make a dataframe
    of which participants have which pre-processed files.

    This will use strings from expected_dict to create a dataframe. In
    order to keep things synchronized, it will git clone/pull the repo
    and add/commit/push the updated logs/completed_preprocessing.tsv.

    Subject list is made from pseudo_guid_list, so only consented data
    is reflected in log.

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
        "True" when expected_dict gets updated with new files.

    one_subj : bool/str
        Whether to check for data from single subject. If true, supply
        BIDS-formatted subject string.

        (e.g. one_subj="sub-4001")

    Notes
    -----
    Internet connection is required!

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
    # # For testing
    # proj_dir = "/home/data/madlab/McMakin_EMUR01"
    # code_dir = "/home/nmuncy/compute/func_processing"
    # pat_github_emu = os.environ["TOKEN_GITHUB_EMU"]
    # one_subj = "sub-4168"
    # new_df = False

    expected_dict = {
        "afni": [
            ("wme_mask", "desc-WMe_mask"),
            (
                "intersect_ses-S1_task-study",
                "ses-S1_task-study_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            ),
            (
                "intersect_ses-S2_task-test",
                "ses-S2_task-test_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            ),
            (
                "intersect_ses-S2_task-rest",
                "ses-S2_task-rest_space-MNIPediatricAsym_cohort-5_res-2_desc-intersect_mask.nii.gz",
            ),
            ("scaled_ses-S1_1", "ses-S1_*_run-1_*_desc-scaled_bold"),
            ("scaled_ses-S1_2", "ses-S1_*_run-2_*_desc-scaled_bold"),
            ("scaled_ses-S2_1", "ses-S2_*_run-1_*_desc-scaled_bold"),
            ("scaled_ses-S2_2", "ses-S2_*_run-2_*_desc-scaled_bold"),
            ("scaled_ses-S2_3", "ses-S2_*_run-3_*_desc-scaled_bold"),
            ("scaled_resting", "task-rest_*_desc-scaled_bold"),
            ("decon_ses-S1_1", "decon_task-study_UniqueBehs_stats_REML+tlrc.HEAD"),
            ("decon_ses-S2_1", "decon_task-test_UniqueBehs_stats_REML+tlrc.HEAD"),
            ("decon_resting", "X.decon_task-rest.xmat.1D"),
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
        "intersect_ses-S1_task-study",
        "intersect_ses-S2_task-test",
        "intersect_ses-S2_task-rest",
        "scaled_ses-S1_1",
        "scaled_ses-S1_2",
        "scaled_ses-S2_1",
        "scaled_ses-S2_2",
        "scaled_ses-S2_3",
        "scaled_resting",
        "decon_ses-S1_1",
        "decon_ses-S2_1",
        "decon_resting",
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
    try:
        print(f"\nCloning repo to {code_dir}")
        repo = git.Repo.clone_from(repo_origin, code_dir)
    except Exception:
        print(f"\nUpdating repo: {code_dir}")
        repo = git.Repo(code_dir)
        repo.remotes.origin.pull()

    # set up
    log_dir = os.path.join(code_dir, "func_processing", "logs")
    completed_tsv = os.path.join(log_dir, "completed_preprocessing.tsv")
    deriv_dir = os.path.join(proj_dir, "derivatives")
    dset_dir = os.path.join(proj_dir, "dset")

    # get updated pseudo_guid_list
    df_guid = clone_guid(pat_github_emu)

    # determine subjects from dset*pseudo_guid_list
    if one_subj:
        subj_list = [one_subj]
    else:
        subj_list_all = sorted(
            [x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")]
        )
        df_guid["comments"] = df_guid["comments"].fillna("nan")
        exclude_list = [
            f"sub-{x}" for x in df_guid[df_guid["exclude"].notnull()]["redcap_id"]
        ]
        subj_guid = [f"sub-{x}" for x in df_guid["redcap_id"]]
        subj_list = [
            x for x in subj_list_all if x not in exclude_list and x in subj_guid
        ]

    # make new completed_tsv
    if new_df:
        h_df = pd.DataFrame(columns=col_names)
        h_df["subjID"] = subj_list
        h_df.to_csv(completed_tsv, index=False, sep="\t")

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
    df_comp.sort_values(by=["subjID"], inplace=True)
    df_comp.to_csv(completed_tsv, index=False, sep="\t")

    # update repo origin
    print("\nCommiting, pushing updates ...")
    now = datetime.datetime.now()
    repo.git.add(completed_tsv)
    repo.index.commit(
        f"""Updated completed_preprocess.tsv at {now.strftime("%Y-%m-%d %H:%M:%S")}"""
    )
    origin = repo.remote(name="origin")
    origin.push()
