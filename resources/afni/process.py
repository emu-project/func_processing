"""

"""

import os
import math
from . import submit


def blur_epi(work_dir, subj_num, afni_data, blur_mult=1.5):
    """Blur EPI data

    Blur pre-processed EPI runs.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
    afni_data : dict
        afni struct, mask, epi, and tsv files
        e.g. {"brain-mask": "mask_brain.nii.gz"}
    blur-mult : int
        blur kernel multiplier (default = 1.5)
        e.g. vox=2, blur_mult=1.5, blur size is 3 (will round float up to nearest int)

    Returns
    -------

    Notes
    -----
    MRI output : functional
        run-1_<task>_blur+tlrc
    """

    # get list of epi files
    epi_list = [x for k, x in afni_data.items() if "epi" in k]

    # determine voxel dim i, calc blur size
    h_cmd = f"3dinfo -dk {work_dir}/{epi_list[0]}"
    h_out, h_err = submit.submit_hpc_subprocess(h_cmd)
    grid_size = h_out.decode("utf-8").strip()
    blur_size = math.ceil(blur_mult * float(grid_size))

    # blur each
    for epi_file in epi_list:
        run_task = "_".join(epi_file.split("_", 2)[:2])
        run_num = epi_file.split("-")[1].split("_")[0]
        if not os.path.exists(os.path.join(work_dir, f"{run_task}_blur.nii.gz")):
            h_cmd = f"""
                cd {work_dir}
                3dmerge \
                    -1blur_fwhm {blur_size} \
                    -doall \
                    -prefix {run_task}_blur.nii.gz \
                    {epi_file}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 1, 1, f"{subj_num}blur{run_num}", work_dir
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # update afni_data
        if os.path.exists(os.path.join(work_dir, f"{run_task}_blur.nii.gz")):
            afni_data[f"blur-{run_num}"] = f"{run_task}_blur.nii.gz"
        else:
            afni_data[f"blur-{run_num}"] = "Missing"

    return afni_data
