# %%
import os
import sys

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from workflow import control_ashs

# %%
subj = "sub-4008"
t1_dir = f"/home/data/madlab/McMakin_EMUR01/dset/{subj}/ses-S1/anat"
t2_dir = f"/home/data/madlab/McMakin_EMUR01/dset/{subj}/ses-S1/anat"
deriv_dir = f"/scratch/madlab/emu_test/derivatives/ashs/{subj}/ses-S1"
work_dir = f"/scratch/madlab/emu_test/derivatives/tmp_ashs/{subj}/ses-S1"
t1_file = f"{subj}_ses-S1_run-2_T1w.nii.gz"
t2_file = f"{subj}_ses-S1_PD.nii.gz"
atlas_dir = "/home/data/madlab/atlases"
atlas_str = "ashs_atlas_magdeburg"
sing_img = "/home/nmuncy/bin/singularities/ashs_test.simg"

ashs_out = control_ashs.control_hipseg(
    t1_dir,
    t2_dir,
    deriv_dir,
    work_dir,
    atlas_dir,
    sing_img,
    subj,
    t1_file,
    t2_file,
    atlas_str,
)
