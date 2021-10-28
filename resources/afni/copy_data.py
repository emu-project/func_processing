import os
import shutil


def _copyfile_patched(fsrc, fdst, length=16 * 1024 * 1024):
    """Patches shutil method to hugely improve copy speed"""
    while 1:
        buf = fsrc.read(length)
        if not buf:
            break
        fdst.write(buf)


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
        task for BIDS task string ("test" for task-test)
    num_runs : int
        number of EPI runs
    tplflow_str = str
        template ID string, for finding fMRIprep output in
        template space (space-MNIPediatricAsym_cohort-5_res-2)

    Returns
    -------
    file_dict : dict
        files copied from derivatives/fMRIprep to derivatives/afni
        e.g. {"brain-mask": "mask_brain.nii.gz"}


    Notes
    -----
    MRI output : structural
        struct_head.nii.gz
        mask_brain.nii.gz
        mask_WM_prob.nii.gz
        mask_GM_prob.nii.gz

    MRI output : functional
        run-?_<task>_preproc.nii.gz

    file output : tsv
        run-?_motion_all.tsv
    """

    # switch for assigning file_dict keys
    file_name_switch = {
        "mask_brain.nii.gz": "brain-mask",
        "mask_GM_prob.nii.gz": "gm-mask",
        "mask_WM_prob.nii.gz": "wm-mask",
        "struct_head.nii.gz": "t1-struct",
    }

    # set vars, dict
    anat_str = f"{subj}_{sess}_{tplflow_str}"
    func_str = f"{subj}_{sess}_task-{task}"

    # organize copy_dict by BIDS scan type
    copy_dict = {
        "anat": {
            "struct_head.nii.gz": f"{anat_str}_desc-preproc_T1w.nii.gz",
            "mask_brain.nii.gz": f"{anat_str}_desc-brain_mask.nii.gz",
            "mask_GM_prob.nii.gz": f"{anat_str}_label-GM_probseg.nii.gz",
            "mask_WM_prob.nii.gz": f"{anat_str}_label-WM_probseg.nii.gz",
        },
        "func": {},
    }

    # add preproc bold, confound TS to copy_dicts and file_name_switch
    for run in range(0, num_runs):
        h_run = f"run-{run+1}"

        copy_dict["func"][
            f"{h_run}_{task}_preproc.nii.gz"
        ] = f"{func_str}_{h_run}_{tplflow_str}_desc-preproc_bold.nii.gz"

        copy_dict["func"][
            f"{h_run}_motion_all.tsv"
        ] = f"{func_str}_{h_run}_desc-confounds_timeseries.tsv"

        file_name_switch[f"{h_run}_{task}_preproc.nii.gz"] = f"epi-{h_run}"
        file_name_switch[f"{h_run}_motion_all.tsv"] = f"mot-{h_run}"

    # copy data
    file_dict = {}
    for scan_type in copy_dict:
        source_dir = os.path.join(prep_dir, subj, sess, scan_type)
        for h_file in copy_dict[scan_type]:
            in_file = os.path.join(source_dir, copy_dict[scan_type][h_file])
            out_file = os.path.join(work_dir, h_file)
            if not os.path.exists(os.path.join(work_dir, h_file)):
                print(f"{subj}: Copying {copy_dict[scan_type][h_file]} to {h_file}")
                shutil.copyfile(in_file, out_file)

            # write return dict
            h_key = file_name_switch[h_file]
            if os.path.exists(os.path.join(work_dir, h_file)):
                file_dict[h_key] = h_file
            else:
                file_dict[h_key] = "Missing"

    return file_dict
