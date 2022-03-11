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
def run_freesurfer(subj, subj_t1, freesurfer_dir, scratch_dir):
    """Title.

    Desc.
    """
    subj_num = subj.split("-")[1]
    h_cmd = f"""
        module load freesurfer-7.1

        # I find generating the 001.mgz to be a bit more stable
        # than the "recon-all -i" option
        mkdir -p {freesurfer_dir}/{subj}/mri/orig
        mri_convert {subj_t1} {freesurfer_dir}/{subj}/mri/orig/001.mgz

        recon-all \
            -subjid {subj} \
            -all \
            -sd {freesurfer_dir} \
            -parallel \
            -openmp 4
    """
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 10, 4, 4, f"fs{subj_num}", scratch_dir
    )
    check_file = os.path.join(freesurfer_dir, subj, "mri/aparc+aseg.mgz")
    assert os.path.exists(
        check_file
    ), f"FreeSurfer failed on {subj}, check resources.freesurfer.freesurfer.run_freesurfer."
