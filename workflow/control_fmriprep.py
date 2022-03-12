"""Control module for running fMRIprep."""

# %%
import os
import sys
import glob
import shutil

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.fmriprep import preprocess


# %%
def control_fmriprep(subj, proj_dir, scratch_dir, sing_img, tplflow_dir, fs_license):
    """Control fMRIprep resources

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
    str
        message
    """

    # set paths
    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, "derivatives")
    work_dir = os.path.join(scratch_dir, subj)

    # orient to data
    dset_subj = os.path.join(dset_dir, subj)
    t1_list = sorted(glob.glob(f"{dset_subj}/**/*T1w.nii.gz", recursive=True))
    assert t1_list, f"No T1w files found for {subj}"
    subj_t1 = t1_list[-1]

    # setup directories
    freesurfer_dir = os.path.join(deriv_dir, "freesurfer")
    fmriprep_dir = os.path.join(deriv_dir, "fmriprep")
    for h_dir in [freesurfer_dir, fmriprep_dir, work_dir]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # do freesurfer if necessary
    check_freesurfer = os.path.join(freesurfer_dir, subj, "mri/aparc+aseg.mgz")
    if not os.path.exists(check_freesurfer):

        # clear previour attempts, execute
        fs_subj = os.path.join(freesurfer_dir, subj)
        if os.path.exists(fs_subj):
            shutil.rmtree(fs_subj)
        print(f"\nStarting FreeSurfer for {subj}")
        fs_orig = os.path.join(fs_subj, "mri/orig")
        os.makedirs(fs_orig)
        fs_status = preprocess.run_freesurfer(
            subj, subj_t1, freesurfer_dir, fs_orig, work_dir
        )

    # clear previous attempts, do fmriprep
    print(f"\nStarting fMRIprep for {subj}")
    fp_subj = os.path.join(fmriprep_dir, subj)
    if os.path.exists(fp_subj):
        shutil.rmtree(fp_subj)
        try:
            os.remove(f"{fp_subj}.html")
        except:
            print(f"No {fp_subj}.html detected")
    preprocess.run_fmriprep(
        subj, deriv_dir, dset_dir, work_dir, sing_img, tplflow_dir, fs_license
    )
    print(f"\n Finished fMRIprep for {subj}")
