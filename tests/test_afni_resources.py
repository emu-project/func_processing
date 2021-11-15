"""Finish pre-processing on EPI data.

Copy relevant files from derivatives/fmriprep to derivatives/afni,
then blur and scale EPI data. Also creates EPI-T1 intersection
and tissue class masks. Finally, generate motion mean, derivative,
and censor files.

Notes
-----
Requires AFNI and c3d.
"""
# %%
import os
import sys
import json

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.afni import copy, process, masks, motion, deconvolve


# %%
# For testing
deriv_dir = "/scratch/madlab/emu_test/derivatives"
subj = "sub-4002"
sess = "ses-S2"
task = "task-test"
tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"


# setup directories
prep_dir = "/home/data/madlab/McMakin_EMUR01/derivatives/fmriprep"
afni_dir = os.path.join(deriv_dir, "afni")
work_dir = os.path.join(afni_dir, subj, sess)
anat_dir = os.path.join(work_dir, "anat")
func_dir = os.path.join(work_dir, "func")
sbatch_dir = os.path.join(work_dir, "sbatch_out")
for h_dir in [anat_dir, func_dir, sbatch_dir]:
    if not os.path.exists(h_dir):
        os.makedirs(h_dir)

# %%
# get fMRIprep data
afni_data = copy.copy_data(prep_dir, work_dir, subj, task, tplflow_str)

# %%
# blur data
subj_num = subj.split("-")[-1]
afni_data = process.blur_epi(work_dir, subj_num, afni_data)

# %%
# make masks
afni_data = masks.make_intersect_mask(work_dir, subj_num, afni_data)

# %%
afni_data = masks.make_tissue_masks(work_dir, subj_num, afni_data)

# %%
afni_data = masks.make_minimum_masks(work_dir, subj_num, sess, task, afni_data)

# %%
afni_data = process.scale_epi(work_dir, subj_num, afni_data)

# make mean, deriv, censor motion files
afni_data = motion.mot_files(work_dir, afni_data)

# %%
dset_dir = "/home/data/madlab/McMakin_EMUR01/dset"
deriv_dir = "/scratch/madlab/emu_test/derivatives/afni"
decon_plan = deconvolve.timing_files(dset_dir, deriv_dir, subj, sess, task)

# %%
for decon_name, tf_dict in decon_plan.items():
    afni_data = deconvolve.write_decon(decon_name, tf_dict, afni_data, work_dir)

# %%
afni_data = deconvolve.run_reml(work_dir, afni_data)
# %%
