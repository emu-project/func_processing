"""Functions for processing EPI data.

Finish pre-processing on fMRIprep output
using an AFNI workflow.

Notes
-----
Requires "submit" module at same level.
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
        afni struct, mask, epi, and tsv files, returned
        by copy.copy_data
    blur-mult : int
        blur kernel multiplier (default = 1.5)
        e.g. vox=2, blur_mult=1.5, blur size is 3 (will round float up to nearest int)

    Returns
    -------
    afni_data : dict
        updated with names of blurred data,
        epi-s? = smoothed EPI data of run-?
    """

    # get list of pre-processed EPI files
    epi_list = [x for k, x in afni_data.items() if "epi-p" in k]

    # determine voxel dim i, calc blur size
    h_cmd = f"3dinfo -dk {work_dir}/{epi_list[0]}"
    h_out, h_err = submit.submit_hpc_subprocess(h_cmd)
    grid_size = h_out.decode("utf-8").strip()
    blur_size = math.ceil(blur_mult * float(grid_size))

    # blur each
    for epi_file in epi_list:
        epi_blur = epi_file.replace("desc-preproc", "desc-smoothed")
        run_num = epi_file.split("run-")[1].split("_")[0]
        if not os.path.exists(os.path.join(work_dir, epi_blur)):
            h_cmd = f"""
                cd {work_dir}
                3dmerge \
                    -1blur_fwhm {blur_size} \
                    -doall \
                    -prefix {epi_blur} \
                    {epi_file}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 1, 1, f"{subj_num}b{run_num}", work_dir
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # update afni_data
        if os.path.exists(os.path.join(work_dir, epi_blur)):
            afni_data[f"epi-s{run_num}"] = epi_blur
        else:
            afni_data[f"epi-s{run_num}"] = "Missing"

    return afni_data
