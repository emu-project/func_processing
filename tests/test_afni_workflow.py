# %%
import os
import sys

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from workflow import control_afni


# %%
prep_dir = "/home/data/madlab/McMakin_EMUR01/derivatives/fmriprep"
afni_dir = "/scratch/madlab/McMakin_EMUR01/derivatives/afni"
subj = "sub-4146"
sess = "ses-S2"
task = "task-rest"

afni_data = control_afni.control_preproc(prep_dir, afni_dir, subj, sess, task)
afni_dir = control_afni.control_resting(afni_data, afni_dir, subj, sess)
