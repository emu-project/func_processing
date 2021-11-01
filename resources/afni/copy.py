"""Copy data from fMRIprep to AFNI.

Copy certain derivative output from fMRIprep to AFNI for use in
finishing pre-processing, deconvolution, and group-level analyses.
"""

import os
import shutil


def copy_data(prep_dir, work_dir, subj, sess, task, num_runs, tplflow_str):
    """Get relevant fMRIprep files, rename.

    Copies select fMRIprep files into AFNI format.

    Parameters
    ----------
    prep_dir : str
        /path/to/derivatives/fmriprep
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-A)
    task : str
        BIDS task string (task-test)
    num_runs : int
        number of EPI runs
    tplflow_str : str
        template ID string, for finding fMRIprep output in
        template space (space-MNIPediatricAsym_cohort-5_res-2)

    Returns
    -------
    file_dict : dict
        files copied from derivatives/fMRIprep to derivatives/afni
        e.g. {
            "mask-brain": "<BIDS-str>_desc-brain_mask.nii.gz",
            "struct-t1": "<BIDS-str>_desc-preproc_T1w.nii.gz",
            }

    Notes
    -----
    file_dict keys:
        struct-t1 = T1w structural
        mask-brain = brain mask
        mask-probGM = probability gray matter mask
        mask-probWM = probability white matter mask
        epi-preproc? = fMRIprep preprocessed EPI for run-?
        mot-confound? = confounds (motion) file for EPI data for run-?
    """

    # set vars, dict
    anat_str = f"{subj}_{sess}_{tplflow_str}"
    func_str = f"{subj}_{sess}_{task}"

    # switch for assigning file_dict keys
    file_name_switch = {
        f"{anat_str}_desc-preproc_T1w.nii.gz": "struct-t1",
        f"{anat_str}_desc-brain_mask.nii.gz": "mask-brain",
        f"{anat_str}_label-GM_probseg.nii.gz": "mask-probGM",
        f"{anat_str}_label-WM_probseg.nii.gz": "mask-probWM",
    }

    # organize copy_dict by BIDS scan type
    copy_dict = {
        "anat": [
            f"{anat_str}_desc-preproc_T1w.nii.gz",
            f"{anat_str}_desc-brain_mask.nii.gz",
            f"{anat_str}_label-GM_probseg.nii.gz",
            f"{anat_str}_label-WM_probseg.nii.gz",
        ],
        "func": [],
    }

    # add preproc bold, confound TS to copy_dict and file_name_switch
    for run in range(0, num_runs):
        run_num = run + 1
        run_str = f"{func_str}_run-{run_num}_{tplflow_str}"
        copy_dict["func"].append(f"{run_str}_desc-preproc_bold.nii.gz")
        copy_dict["func"].append(
            f"{subj}_{sess}_{task}_run-{run_num}_desc-confounds_timeseries.tsv"
        )

        file_name_switch[
            f"{run_str}_desc-preproc_bold.nii.gz"
        ] = f"epi-preproc{run_num}"
        file_name_switch[
            f"{subj}_{sess}_{task}_run-{run_num}_desc-confounds_timeseries.tsv"
        ] = f"mot-confound{run_num}"

    # copy data
    file_dict = {}
    for scan_type in copy_dict:
        source_dir = os.path.join(prep_dir, subj, sess, scan_type)
        for h_file in copy_dict[scan_type]:
            in_file = os.path.join(source_dir, h_file)
            out_file = os.path.join(work_dir, h_file)
            if not os.path.exists(out_file):
                print(f"Copying {h_file} ...")
                shutil.copyfile(in_file, out_file)

            # write return dict
            h_key = file_name_switch[h_file]
            if os.path.exists(out_file):
                file_dict[h_key] = h_file
            else:
                file_dict[h_key] = "Missing"

    return file_dict
