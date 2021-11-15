"""Copy data from fMRIprep to AFNI.

Copy certain derivative output from fMRIprep to AFNI for use in
finishing pre-processing, deconvolution, and group-level analyses.
"""

import os
import glob
import shutil


def copy_data(prep_dir, work_dir, subj, task, tplflow_str):
    """Get relevant fMRIprep files, rename.

    Copies select fMRIprep files into AFNI derivatives, prepares
    for AFNI pre-processing steps.

    Parameters
    ----------
    prep_dir : str
        /path/to/derivatives/fmriprep
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj : str
        BIDS subject string (sub-1234)
    task : str
        BIDS task string (task-test)
    tplflow_str : str
        template ID string, for finding fMRIprep output in
        template space (space-MNIPediatricAsym_cohort-5_res-2)

    Returns
    -------
    file_dict : dict
        files copied from derivatives/fMRIprep to derivatives/afni
        e.g. {
            "mask-brain": "anat/<BIDS-str>_desc-brain_mask.nii.gz",
            "struct-t1": "anat/<BIDS-str>_desc-preproc_T1w.nii.gz",
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

    # determine anat string
    h_anat = glob.glob(
        f"{prep_dir}/{subj}/**/*{tplflow_str}_desc-preproc_T1w.nii.gz", recursive=True
    )
    anat_str = h_anat[0].split("/")[-1].split("_desc")[0]

    # make a list of anat files to copy
    desired_anat = (
        f"{anat_str}_desc-preproc_T1w.nii.gz",
        f"{anat_str}_desc-brain_mask.nii.gz",
        f"{anat_str}_label-GM_probseg.nii.gz",
        f"{anat_str}_label-WM_probseg.nii.gz",
    )
    anat_files = []
    for anat in desired_anat:
        anat_files.extend(glob.glob(f"{prep_dir}/{subj}/**/{anat}", recursive=True))
    assert len(desired_anat) == len(
        anat_files
    ), "Missing desired_anat files, check resources.afni.copy."

    # switch for assigning anat file_dict keys
    file_name_switch = {
        f"{anat_str}_desc-preproc_T1w.nii.gz": "struct-t1",
        f"{anat_str}_desc-brain_mask.nii.gz": "mask-brain",
        f"{anat_str}_label-GM_probseg.nii.gz": "mask-probGM",
        f"{anat_str}_label-WM_probseg.nii.gz": "mask-probWM",
    }

    # copy anat files, update file_dict
    file_dict = {}
    anat_dir = os.path.join(work_dir, "anat")
    for anat in anat_files:
        anat_name = anat.split("/")[-1]
        file_dict[file_name_switch[anat_name]] = f"anat/{anat_name}"
        out_file = os.path.join(anat_dir, anat_name)
        if not os.path.exists(out_file):
            print(f"Copying {anat_name} ...")
            shutil.copyfile(anat, out_file)
        assert os.path.exists(
            out_file
        ), f"{out_file} failed to copy, check resources.afni.copy."

    # find EPI, motion files
    epi_files = glob.glob(
        f"{prep_dir}/{subj}/**/*{task}*{tplflow_str}_desc-preproc_bold.nii.gz",
        recursive=True,
    )
    epi_files.sort()

    mot_files = glob.glob(
        f"{prep_dir}/{subj}/**/*{task}*desc-confounds_timeseries.tsv",
        recursive=True,
    )
    mot_files.sort()

    assert len(epi_files) == len(
        mot_files
    ), "Number of task EPI files != condound files, check resources.afni.copy."

    # copy EPI files, update dict (key = epi-preproc?)
    func_dir = os.path.join(work_dir, "func")

    for count, epi in enumerate(epi_files):
        epi_name = epi.split("/")[-1]
        file_dict[f"epi-preproc{count + 1}"] = f"func/{epi_name}"
        out_file = os.path.join(func_dir, epi_name)
        if not os.path.exists(out_file):
            print(f"Copying {out_file}")
            shutil.copyfile(epi, out_file)
        assert os.path.exists(
            out_file
        ), f"{out_file} failed to copy, check resources.afni.copy."

    # copy mot files, update dict (key = mot-confound?)
    for count, mot in enumerate(mot_files):
        mot_name = mot.split("/")[-1]
        file_dict[f"mot-confound{count + 1}"] = f"func/{mot_name}"
        out_file = os.path.join(func_dir, mot_name)
        if not os.path.exists(out_file):
            print(f"Copying {out_file}")
            shutil.copyfile(mot, out_file)
        assert os.path.exists(
            out_file
        ), f"{out_file} failed to copy, check resources.afni.copy."

    return file_dict
