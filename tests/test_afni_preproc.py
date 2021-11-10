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
import glob
import json
from argparse import ArgumentParser, RawTextHelpFormatter

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.afni import copy, process, masks, motion


# %%
# For testing
deriv_dir = "/scratch/madlab/emu_test/derivatives"
subj = "sub-4002"
sess = "ses-S2"
task = "task-test"
num_runs = 3
tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"


# setup directories
prep_dir = "/home/data/madlab/McMakin_EMUR01/derivatives/fmriprep"
afni_dir = os.path.join(deriv_dir, "afni")
work_dir = os.path.join(afni_dir, subj, sess)
if not os.path.exists(work_dir):
    os.makedirs(work_dir)

# get fMRIprep data
afni_data = copy.copy_data(prep_dir, work_dir, subj, task, tplflow_str)

# blur data
subj_num = subj.split("-")[-1]
afni_data = process.blur_epi(work_dir, subj_num, afni_data)

# make masks
afni_data = masks.make_intersect_mask(work_dir, subj_num, afni_data)
afni_data = masks.make_tissue_masks(work_dir, subj_num, afni_data)

# scale data
afni_data = process.scale_epi(work_dir, subj_num, sess, task, afni_data)

# check for files
with open(os.path.join(work_dir, "afni_data.json"), "w") as jf:
    json.dump(afni_data, jf)
assert "Missing" not in afni_data.values(), "Missing value (file) in afni_data."

# clean
for tmp_file in glob.glob(f"{work_dir}/tmp*"):
    os.remove(tmp_file)
for sbatch_file in glob.glob(f"{work_dir}/sbatch*"):
    os.remove(sbatch_file)

# make mean, deriv, censor motion files
afni_data = motion.mot_files(work_dir, afni_data)
with open(os.path.join(work_dir, "afni_data.json"), "w") as jf:
    json.dump(afni_data, jf)

print(afni_data)
