"""

"""
# %%
import os
import sys

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from workflow import control_afni


# %%
# for testing
deriv_dir = "/scratch/madlab/emu_test/derivatives"
subj = "sub-4002"
sess = "ses-S2"
task = "task-test"
num_runs = 3
tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"

afni_data = control_afni.control_preproc(
    deriv_dir, subj, sess, task, num_runs, tplflow_str
)

# %%
decon_json = "sub-4002_decon_plan.json"
afni_data = control_afni.control_deconvolution(
    deriv_dir, subj, sess, afni_data, decon_json
)

# %%
