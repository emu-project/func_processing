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

    # orient to data
    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, "derivatives")
    scratch_subj = os.path.join(scratch_dir, subj)

    dset_subj = os.path.join(dset_dir, subj)
    t1_list = sorted(glob.glob(f"{dset_subj}/**/*T1w.nii.gz", recursive=True))
    assert t1_list, f"No T1w files found for {subj}"
    subj_t1 = t1_list[-1]

    # setup directories - many paths set for freesurfer/fmriprep needs
    freesurfer_dir = os.path.join(deriv_dir, "freesurfer")
    # freesurfer_subj = os.path.join(freesurfer_dir, subj)
    fmriprep_dir = os.path.join(deriv_dir, "fmriprep")
    fmriprep_subj = os.path.join(fmriprep_dir, subj)

    for h_dir in [freesurfer_dir, fmriprep_subj, scratch_subj]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # do freesurfer
    fs_status = freesurfer.run_freesurfer(subj, subj_t1, freesurfer_dir, scratch_dir)
    if not fs_status:
        print("ERROR: FreeSurfer failed, check workflow.control_fmriprep.")

    # do fmriprep
    fmriprep.run_fmriprep(
        subj, deriv_dir, dset_dir, work_dir, sing_img, tpflow_dir, fs_license
    )
