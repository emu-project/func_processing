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
    """Blur EPI data.

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
        epi-b? = blurred/smoothed EPI data of run-?
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
            afni_data[f"epi-b{run_num}"] = epi_blur
        else:
            afni_data[f"epi-b{run_num}"] = "Missing"

    return afni_data


def scale_epi(work_dir, subj_num, sess, task, afni_data):
    """Scale EPI runs.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
    sess : str
        BIDS session string (ses-S1)
    task : str
        BIDS task string (task-test)

    Returns
    -------
    afni_dict : dict
        updated with mask, epi keys
        mask-min = mask of minimum value for task
        epi-s? = scaled EPI for run-?
    """

    # make masks of voxels where some data exists
    epi_pre = [x for k, x in afni_data.items() if "epi-p" in k]

    mask_str = afni_data["mask-brain"]
    mask_min = mask_str.replace("desc-brain", "desc-minval")
    mask_min = mask_min.replace(sess, f"{sess}_{task}")

    if not os.path.exists(os.path.join(work_dir, mask_min)):
        min_list = []
        for run in epi_pre:
            min_list.append(f"tmp_mask_min.{run}")
            if not os.path.exists(os.path.join(work_dir, f"tmp_mask_min.{run}")):
                h_cmd = f"""
                    cd {work_dir}

                    3dcalc \
                        -overwrite \
                        -a {run} \
                        -expr 1 \
                        -prefix tmp_mask_bin.{run}

                    3dTstat \
                        -min \
                        -prefix tmp_mask_min.{run} \
                        tmp_mask_bin.{run}
                """
                h_out, h_err = submit.submit_hpc_subprocess(h_cmd)

        h_cmd = f"""
            cd {work_dir}

            3dMean \
                -datum short \
                -prefix tmp_mask_mean_{task}.nii.gz \
                {" ".join(min_list)}

            3dcalc \
                -a tmp_mask_mean_{task}.nii.gz \
                -expr 'step(a-0.999)' \
                -prefix {mask_min}
        """
        job_name, job_id = submit.submit_hpc_sbatch(
            h_cmd, 1, 1, 1, f"{subj_num}min", work_dir
        )
        print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

    if os.path.exists(os.path.join(work_dir, mask_min)):
        afni_data["mask-min"] = mask_min
    else:
        afni_data["mask-min"] = "Missing"

    # scale data timeseries
    epi_blur = [x for k, x in afni_data.items() if "epi-b" in k]

    for run in epi_blur:
        epi_scale = run.replace("desc-smoothed", "desc-scaled")
        run_num = run.split("run-")[1].split("_")[0]
        if not os.path.exists(os.path.join(work_dir, epi_scale)):
            h_cmd = f"""
                cd {work_dir}

                3dTstat -prefix tmp_tstat.{run} {run}

                3dcalc -a {run} \
                    -b tmp_tstat.{run} \
                    -c {mask_min} \
                    -expr 'c * min(200, a/b*100)*step(a)*step(b)' \
                    -prefix {epi_scale}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 1, 1, f"{subj_num}s{run_num}", work_dir
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        if os.path.exists(os.path.join(work_dir, epi_scale)):
            afni_data[f"epi-s{run_num}"] = epi_scale
        else:
            afni_data[f"epi-s{run_num}"] = "Missing"

    return afni_data
