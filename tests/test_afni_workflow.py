# %%
import os
import sys

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from workflow import control_afni


# %%
prep_dir = "/home/data/madlab/McMakin_EMUR01/derivatives/fmriprep"
afni_dir = "/scratch/madlab/emu_test/derivatives/afni"
subj = "sub-4002"
sess = "ses-S2"
task = "task-test"

afni_data = control_afni.control_preproc(prep_dir, afni_dir, subj, sess, task)

# %%
dset_dir = "/home/data/madlab/McMakin_EMUR01/dset"
afni_dir = control_afni.control_deconvolution(
    afni_dir, dset_dir, subj, sess, task, afni_data
)


# %%
