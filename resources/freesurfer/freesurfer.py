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
def run_freesurfer(subj, subj_t1, freesurfer_dir):
    """Title.

    Desc.
    """
    subj_num = subj.split("-")[1]
    h_cmd = f"""
        module load freesurfer-7.1

        recon-all \
            -all \
            -i {subj_t1} \
            -openmp 4 \
            -subjid {subj} \
            -sd {freesurfer_dir}
    """
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 10, 4, 4, f"fs{subj_num}", deriv_dir
    )
    check_file = os.path.join(freesurfer_dir, subj, "mri/aparc+aseg.mgz")
    assert os.path.exists(
        check_file
    ), f"FreeSurfer failed on {subj}, check resources.freesurfer.freesurfer.run_freesurfer."
    return True
