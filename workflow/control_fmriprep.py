"""Title.

Desc.
"""

# %%
import os
import sys
import glob

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.freesurfer import freesurfer
from resources.fmriprep import fmriprep


# %%
def control_fmriprep(subj, proj_dir, scratch_dir, sing_img, tpflow_dir, fs_license):
    """Title.

    Desc.
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
            os.removedirs(fs_subj)
        print(f"\nStarting FreeSurfer for {subj}")
        fs_status = freesurfer.run_freesurfer(
            subj, subj_t1, freesurfer_dir, scratch_dir
        )

    # clear previous attempts, do fmriprep
    print(f"\nStarting fMRIprep for {subj}")
    fp_subj = os.path.join(fmriprep_dir, subj)
    if os.path.exists(fp_subj):
        os.removedirs(fp_subj)
    fmriprep.run_fmriprep(
        subj, deriv_dir, dset_dir, work_dir, sing_img, tpflow_dir, fs_license
    )
    print(f"\n Finished fMRIprep for {subj}")
