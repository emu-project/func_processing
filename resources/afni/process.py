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

    Blur pre-processed EPI runs with AFNI's 3dmerge.

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
        epi-blur? = blurred/smoothed EPI data of run-?

    Notes
    -----
    Requires afni_data["epi-preproc*"] keys.
    Determining blur multiplier based off voxel's dimension K.
    """

    # get list of pre-processed EPI files
    num_epi = len([y for x, y in afni_data.items() if "epi-preproc" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-preproc?'] not found. Check resources.afni.copy.copy_data"
    epi_list = [x for k, x in afni_data.items() if "epi-preproc" in k]

    # determine voxel dim i, calc blur size
    h_cmd = f"3dinfo -dk {epi_list[0]}"
    h_out, h_err = submit.submit_hpc_subprocess(h_cmd)
    grid_size = h_out.decode("utf-8").strip()
    blur_size = math.ceil(blur_mult * float(grid_size))

    # blur each
    for epi_file in epi_list:
        epi_blur = epi_file.replace("desc-preproc", "desc-smoothed")
        run_num = epi_file.split("run-")[1].split("_")[0]
        if not os.path.exists(epi_blur):
            print(f"Starting blur for {epi_file} ...")
            h_cmd = f"""
                3dmerge \
                    -1blur_fwhm {blur_size} \
                    -doall \
                    -prefix {epi_blur} \
                    {epi_file}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 1, 1, f"{subj_num}b{run_num}", f"{work_dir}/sbatch_out"
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # update afni_data
        assert os.path.exists(
            epi_blur
        ), f"{epi_blur} failed to write, check resources.afni.process.blur_epi."
        afni_data[f"epi-blur{run_num}"] = epi_blur

    return afni_data


def scale_epi(work_dir, subj_num, afni_data):
    """Scale EPI runs.

    Scale timeseries to center = 100 using AFNI's 3dcalc.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
    afni_data : dict
        afni data dict for passing files

    Returns
    -------
    afni_dict : dict
        epi-scale? = scaled EPI for run-?

    Notes
    -----
    Requires afni_data["epi-blur*"], afni_data["mask-min"].
    """

    # determine relevant files
    num_epi = len([y for x, y in afni_data.items() if "epi-blur" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-blur?'] not found. Check resources.afni.process.blur_epi."

    assert afni_data[
        "mask-min"
    ], "ERROR: afni_data['mask-min'] not found. Check resources.afni.masks.make_minimum_masks."

    epi_blur = [x for k, x in afni_data.items() if "epi-blur" in k]
    mask_min = afni_data["mask-min"]

    # scale each blurred/smoothed file
    for run in epi_blur:
        epi_scale = run.replace("desc-smoothed", "desc-scaled")
        run_num = run.split("run-")[1].split("_")[0]

        # do work if missing
        if not os.path.exists(epi_scale):
            tmp_file = "tmp_tstat.sub".join(run.rsplit("sub", 1))
            print(f"Starting scaling for {run} ...")
            h_cmd = f"""
                3dTstat -prefix {tmp_file} {run}
                3dcalc -a {run} \
                    -b {tmp_file} \
                    -c {mask_min} \
                    -expr 'c * min(200, a/b*100)*step(a)*step(b)' \
                    -prefix {epi_scale}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 1, 1, f"{subj_num}s{run_num}", f"{work_dir}/sbatch_out"
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # update dict
        assert os.path.exists(
            epi_scale
        ), f"{epi_scale} failed to write, check resources.afni.process.scale_epi."
        afni_data[f"epi-scale{run_num}"] = epi_scale

    return afni_data


def reface(subj, sess, t1_file, proj_dir, method):
    """De/Reface T1-weighted files.

    Use AFNI's refacer to deface or reface T1-weighted
    structural files.

    Parameters
    ----------
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-A)
    t1_file : str
        file name of T1-weighted file
        (sub-1234_ses-A_T1w.nii.gz)
    proj_dir : str
        path to BIDS project dir
        (/path/to/BIDS/proj)
    method : str
        "deface", "reface", or "reface_plus" method
    """
    out_dir = os.path.join(proj_dir, f"derivatives/{method}", subj, sess, "anat")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    t1_in = os.path.join(proj_dir, "dset", subj, sess, "anat", t1_file)
    t1_out = os.path.join(
        out_dir,
        t1_file.replace("_T1w", f"_desc-{method}_T1w"),
    )
    h_cmd = f"""
        export TMPDIR={out_dir}

        \\@afni_refacer_run \
            -input {t1_in} \
            -mode_{method} \
            -anonymize_output \
            -prefix {t1_out}

        rm {out_dir}/*.face.nii.gz
        rm -r {out_dir}/*_QC
        rm {out_dir}/*.{{err,out}}
    """
    print(h_cmd)
    subj_num = subj.split("-")[1]
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 1, 1, 1, f"{subj_num}{method}", f"{out_dir}"
    )
    print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")
