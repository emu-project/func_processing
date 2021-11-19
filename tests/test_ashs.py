# %%
import os
import sys

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.ashs import hipseg

# %%
subj = "sub-4002"
anat_dir = "/home/data/madlab/McMakin_EMUR01/dset/sub-4002/ses-S1/anat"
deriv_dir = "/scratch/madlab/emu_test/derivatives/ashs/sub-4002/ses-S1"
work_dir = "/scratch/madlab/emu_test/derivatives/tmp_ashs/sub-4002/ses-S1"
t1_file = "sub-4002_ses-S1_run-2_T1w.nii.gz"
t2_file = "sub-4002_ses-S1_PD.nii.gz"
atlas_dir = "/home/data/madlab/atlases"
atlas_str = "ashs_atlas_magdeburg"
sing_img = "/home/nmuncy/bin/singularities/ashs_latest.simg"

ashs_out = hipseg.run_ashs(
    anat_dir,
    deriv_dir,
    work_dir,
    atlas_dir,
    sing_img,
    subj,
    t1_file,
    t2_file,
    atlas_str,
)

# %%
