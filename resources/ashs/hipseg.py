"""Title.

Desc.
"""
# %%
import os
import sys

resource_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(resource_dir)

from afni import submit


# %%
# def run_ashs(
#     anat_dir, deriv_dir, atlas_dir, sing_img, subj, t1_file, t2_file, atlas_str
# ):
#     """Run automatic hippocampal subfield segmentation.

#     Use ASHS singularity to generate HC subfield labels.

#     Parameters
#     ----------

#     Returns
#     -------

#     """

subj = "sub-4002"
anat_dir = "/home/data/madlab/McMakin_EMUR01/dset/sub-4002/ses-S1/anat"
deriv_dir = "/scratch/madlab/emu_test/derivatives/ashs/sub-4002/ses-S1"
t1_file = "sub-4002_ses-S1_run-2_T1w.nii.gz"
t2_file = "sub-4002_ses-S1_PD.nii.gz"
atlas_dir = "/home/data/madlab/atlases"
atlas_str = "ashs_atlas_magdeburg"
sing_img = "/home/nmuncy/bin/singularities/ashs_latest.sif"

# %%
subj_num = subj.split("-")[1]
h_cmd = f"""
    module load singularity-3.8.2
    cd /
    singularity run \
        --bind {anat_dir}:/data_dir \
        --bind {deriv_dir}:/work_dir \
        --bind {atlas_dir}:/atlas_dir \
        {sing_img} \
        -i {subj} \
        -g {t1_file} \
        -f {t2_file} \
        -a {atlas_str}
"""
job_name, job_id = submit.submit_hpc_sbatch(
    h_cmd, 2, 4, 6, f"ashs{subj_num}", deriv_dir
)
print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

# %%
