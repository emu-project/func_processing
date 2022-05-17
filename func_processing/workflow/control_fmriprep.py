"""Control module for running fMRIprep.

Orients to the data, runs FreeSurfer if needed,
and then runs fMRIprep.
"""

# %%
import os
import sys
import glob
import shutil
import subprocess
from func_processing.resources.fmriprep import preprocess


# %%
def control_fmriprep(subj, proj_dir, scratch_dir, sing_img, tplflow_dir, fs_license):
    """Control fMRIprep resources.

    First, run subject data through FreeSurfer. Then, run fMRIprep.

    Parameters
    ----------
    subj : str
        BIDS subject string
    proj_dir : str
        Path to BIDS project directory
    scratch_dir : str
        Path to working/scratch directory
    sing_img : str
        Path to fmriprep singularity iamge
    tplflow_dir : str
        Path to templateflow directory
    fs_license : str
        Path to FreeSurfer license

    Returns
    -------
    path_dict : dict
        paths for ease of copying, cleaning
    """
    # set paths
    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, "derivatives")
    scratch_dset = os.path.join(scratch_dir, "dset")
    scratch_deriv = os.path.join(scratch_dir, "derivatives")

    # setup scratch deriv directories
    freesurfer_dir = os.path.join(scratch_deriv, "freesurfer")
    fmriprep_dir = os.path.join(scratch_deriv, "fmriprep")
    work_dir = os.path.join(scratch_deriv, "work", subj)
    for h_dir in [freesurfer_dir, fmriprep_dir, work_dir]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # copy data to scratch for write issue in home/data/madlab, identify t1w
    subj_scratch_dset = os.path.join(scratch_dset, subj)
    t1_list = sorted(glob.glob(f"{subj_scratch_dset}/**/*T1w.nii.gz", recursive=True))
    if not t1_list:
        print(f"\nCopying {subj} dset to {scratch_dset} ...\n")
        h_cmd = f"cp -r {dset_dir}/{subj} {scratch_dset}/"
        h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
        h_cp.communicate()
        t1_list = sorted(
            glob.glob(f"{subj_scratch_dset}/**/*T1w.nii.gz", recursive=True)
        )
    assert t1_list, "Copying data to scratch failed, check workflow.control_fmriprep."
    subj_t1 = t1_list[-1]

    # do freesurfer if necessary, clear previous attempts
    check_freesurfer = os.path.join(freesurfer_dir, subj, "mri/aparc+aseg.mgz")
    if not os.path.exists(check_freesurfer):
        try:
            shutil.rmtree(os.path.join(freesurfer_dir, subj))
        except FileNotFoundError:
            print("No previous FreeSurfer attempt found, continuing ...")

        # set up freesurfer dir, execute
        print(f"\nStarting FreeSurfer for {subj}")
        os.makedirs(os.path.join(freesurfer_dir, subj, "mri/orig"))
        preprocess.run_freesurfer(subj, subj_t1, freesurfer_dir, work_dir)

    # check the freesurfer ran
    assert os.path.exists(
        check_freesurfer
    ), f"FreeSurfer failed on {subj}, check resources.fmriprep.preprocess.run_freesurfer."
    print(f"\nFinished FreeSurfer for {subj}")

    # clear previous attempts, do fmriprep
    print(f"\nStarting fMRIprep for {subj}")
    fp_subj = os.path.join(fmriprep_dir, subj)
    if os.path.exists(fp_subj):
        shutil.rmtree(fp_subj)
        try:
            os.remove(f"{fp_subj}.html")
        except FileNotFoundError:
            print(f"No {fp_subj}.html detected, continuing ...")
    preprocess.run_fmriprep(
        subj, scratch_deriv, scratch_dset, sing_img, tplflow_dir, fs_license
    )

    # check the fmriprep ran
    check_fmriprep = glob.glob(
        f"{fmriprep_dir}/{subj}/**/*desc-preproc_T1w.nii.gz", recursive=True
    )
    assert (
        check_fmriprep
    ), f"fMRIprep failed on {subj}, check resources.fmriprep.preprocess_run_fmriprep."
    print(f"\n Finished fMRIprep for {subj}")
    path_dict = {
        "proj-deriv": deriv_dir,
        "scratch-fprep": fmriprep_dir,
        "scratch-fsurf": freesurfer_dir,
        "scratch-work": work_dir,
    }
    return path_dict
