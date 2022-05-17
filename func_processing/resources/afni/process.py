"""Functions for processing EPI data.

Finish pre-processing on fMRIprep output
using an AFNI workflow.
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
        contains keys pointing to required files

        required keys:

        - [epi-preproc<1..N>] = fmriprep pre-processed files

    blur-mult : int
        blur kernel multiplier (default = 1.5)

        e.g. vox=2, blur_mult=1.5, blur size is 3 (will round float up to nearest int)

    Returns
    -------
    afni_data : dict
        updated with names of blurred data

        added afni_data keys:

        - [epi-blur?] = blurred/smoothed EPI data of run-?

    Notes
    -----
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
    h_out, _ = submit.submit_hpc_subprocess(h_cmd)
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


def scale_epi(work_dir, subj_num, afni_data, do_blur):
    """Scale EPI runs.

    Scale timeseries to center = 100 using AFNI's 3dcalc.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A

    subj_num : int/str
        subject identifier, for sbatch job name

    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [mask-min] = mask of voxels with >minimum signal conditionally required keys

        - [do_blur] = T when [epi-blur<1..N>] = list of blurred EPI files

        - [do_blur] = F when [epi-preproc<1..N>] = list of fmriprep preprocessed files

    do_blur : bool
        [T/F] whether to blur as part of pre-processing

    Returns
    -------
    afni_dict : dict
        updated with scaled files

        added afni_data keys:

        - [epi-scale?] = scaled EPI for run-?
    """
    # determine required files
    if do_blur:
        num_epi = len([y for x, y in afni_data.items() if "epi-blur" in x])
        assert (
            num_epi > 0
        ), "ERROR: afni_data['epi-blur?'] not found. Check resources.afni.process.blur_epi"
        epi_files = [x for k, x in afni_data.items() if "epi-blur" in k]
    else:
        num_epi = len([y for x, y in afni_data.items() if "epi-preproc" in x])
        assert (
            num_epi > 0
        ), "ERROR: afni_data['epi-preproc?'] not found. Check resources.afni.copy.copy_data."
        epi_files = [x for k, x in afni_data.items() if "epi-preproc" in k]

    assert afni_data[
        "mask-min"
    ], "ERROR: afni_data['mask-min'] not found. Check resources.afni.masks.make_minimum_masks."
    mask_min = afni_data["mask-min"]

    # scale each blurred/smoothed file
    for run in epi_files:
        h_str = "desc-smoothed" if do_blur else "desc-preproc"
        epi_scale = run.replace(h_str, "desc-scaled")
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

    Returns
    -------
    return_str : str
        Success message
    """
    out_dir = os.path.join(proj_dir, f"derivatives/{method}", subj, sess, "anat")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    t1_in = os.path.join(proj_dir, "dset", subj, sess, "anat", t1_file)
    t1_out = os.path.join(out_dir, t1_file.replace("_T1w", f"_desc-{method}_T1w"),)
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
    assert os.path.exists(
        t1_out
    ), f"ERROR: failed to write {t1_out}, check resources.afni.process.reface."
    return_str = f"Wrote {t1_out}"
    return return_str


def resting_metrics(afni_data, work_dir):
    """Generate info about resting data.

    Produce TSNR, GCOR, and noise estimations.

    Parameters
    ----------
    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [epi-scale1] = first/only scaled RS epi file

        - [reg-matrix] = project regression matrix

        - [mot-censor] = binary censor vector

        - [mask-int] = epi-anat intersection mask

    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    Returns
    -------
    afni_data : dict
        not currently adding any keys/values
    """
    # check for req files
    num_epi = len([y for x, y in afni_data.items() if "epi-scale" in x])
    assert num_epi == 1, (
        "ERROR: afni_data['epi-scale1'] not found, or too many RS files."
        "Check resources.afni.process.scale_epi."
    )

    assert afni_data[
        "reg-matrix"
    ], "ERROR: no regression matrix, check resources.afni.deconvolve.regress_resting."

    assert afni_data[
        "mot-censor"
    ], "ERROR: missing afni_data[mot-censor] file, check resources.afni.motion.mot_files."

    assert afni_data[
        "mask-int"
    ], "ERROR: missing afni_data[mask-int] file, check resources.afni.masks.make_intersect_mask."

    # set up
    epi_file = afni_data["epi-scale1"]
    reg_file = afni_data["reg-matrix"]
    file_censor = afni_data["mot-censor"]
    int_mask = afni_data["mask-int"]
    out_str = "decon_task-rest"
    func_dir = os.path.join(work_dir, "func")
    subj_num = epi_file.split("sub-")[-1].split("_")[0]

    # calc SNR
    snr_file = epi_file.replace("scaled", "tsnr")
    if not os.path.exists(snr_file):
        print(f"\nMaking SNR file {snr_file}")
        mean_file = epi_file.replace("scaled", "meanTS")
        sd_file = epi_file.replace("scaled", "sdTS")

        # determine non-censored volumes
        h_out, _ = submit.submit_hpc_subprocess(
            f"1d_tool.py -infile {file_censor} -show_trs_uncensored encoded"
        )
        used_vols = h_out.decode("utf-8").strip()

        # make mean, sd of used volumes, then
        # produce snr calc. Mask snr.
        h_cmd = f"""
            3dTstat \
                -mean \
                -prefix {mean_file} \
                {epi_file}'[{used_vols}]'

            3dTstat \
                -stdev \
                -prefix {sd_file} \
                {reg_file}'[{used_vols}]'

            3dcalc \
                -a {mean_file} \
                -b {sd_file} \
                -c {int_mask} \
                -expr 'c*a/b' \
                -prefix {snr_file}
        """
        _, _ = submit.submit_hpc_sbatch(
            h_cmd, 1, 8, 1, f"{subj_num}SNR", f"{work_dir}/sbatch_out"
        )

    # calc global corr
    unit_file = reg_file.replace("+tlrc", "_unit+tlrc")
    gmean_file = reg_file.replace("+tlrc", "_gmean.1D")
    gcor_file = reg_file.replace("+tlrc", "_gcor.1D")
    if not os.path.exists(gcor_file):
        print(f"\nCalculating global correlation {gcor_file}")
        h_cmd = f"""
            3dTnorm \
                -norm2 \
                -prefix {unit_file} \
                {reg_file}

            3dmaskave \
                -quiet \
                -mask {int_mask} \
                {unit_file} >{gmean_file}

            3dTstat \
                -sos \
                -prefix - \
                {gmean_file}\\' >{gcor_file}
        """
        _, _ = submit.submit_hpc_sbatch(
            h_cmd, 1, 8, 1, f"{subj_num}GCOR", f"{work_dir}/sbatch_out"
        )

    # noise estimations - afni style
    acf_reg = reg_file.replace("+tlrc", "_ACF-estimates.1D")
    avg_reg = reg_file.replace("+tlrc", "_ACF-average.1D")
    acf_epi = epi_file.replace("_bold.nii.gz", "_ACF-estimates.1D")
    avg_epi = epi_file.replace("_bold.nii.gz", "_ACF-average.1D")

    if not os.path.isfile(avg_reg):
        print("\nRunning noise simulations ...")

        # determine used volumes in decon
        h_out, _ = submit.submit_hpc_subprocess(
            f"""1d_tool.py \
                -infile {func_dir}/X.{out_str}.xmat.1D \
                -show_trs_uncensored encoded \
                -show_trs_run 1 \
            """
        )
        used_trs = h_out.decode("utf-8").strip()

        # simulate noise, ACF method
        h_cmd = f"""
            if [ ! -s {avg_reg} ]; then
                3dFWHMx \
                    -mask {int_mask} \
                    -ACF {acf_epi} \
                    {epi_file}'[{used_trs}]' >{avg_epi}

                3dFWHMx \
                    -mask {int_mask} \
                    -ACF {acf_reg} \
                    {reg_file}'[{used_trs}]' >{avg_reg}
            fi
        """
        _, _ = submit.submit_hpc_sbatch(
            h_cmd, 2, 8, 4, f"{subj_num}FWHMx", f"{work_dir}/sbatch_out"
        )

    return afni_data


def resting_seed(coord_dict, afni_data, work_dir):
    """Produce correlation matrices for seeds.

    For each seed in coord_dict, produce a projected
    correlation matrix.

    Parameters
    ----------
    coord_dict : dict
        seed name, coordinates

        {"rPCC": "5 -55 25"}

    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [reg-matrix] = project regression matrix

        - [mask-int] = epi-anat intersection mask

        - [mot-censor] = binary censory vector

    work_dir : str
        location of subject's scratch directory

    Returns
    -------
    afni_data : dict
        updated with z-transformed data

        added afni_data keys:

        - [S<seed>-ztrans] = Z-transformed correlation matrix of seed
    """
    # check for req files
    assert afni_data[
        "reg-matrix"
    ], "ERROR: missing afni_data['reg-matrix'], check resources.afni.deconvolve.regress_resting."
    assert afni_data[
        "mask-int"
    ], "ERROR: missing afni_data['mask-int'], check resources.afni.masks.make_intersection_mask."
    assert afni_data[
        "mot-censor"
    ], "ERROR: missing afni_data['mot-censor'], check resources.afni.motion.mot_files."

    # unpack afni_data to get file, reference strings
    reg_file = afni_data["reg-matrix"]
    int_mask = afni_data["mask-int"]
    file_censor = afni_data["mot-censor"]
    subj_num = reg_file.split("sub-")[-1].split("/")[0]

    # make seed for coordinates, get timeseries
    for seed, coord in coord_dict.items():
        seed_file = int_mask.replace("desc-intersect", f"desc-RS{seed}")
        seed_ts = file_censor.replace("desc-censor", f"desc-RS{seed}")
        if not os.path.exists(seed_file):
            print(f"Making Seed {seed}\n")
            h_cmd = f"""
                echo {coord} > {work_dir}/anat/tmp.txt
                3dUndump \
                    -prefix {seed_file} \
                    -master {reg_file} \
                    -srad 2 \
                    -xyz {work_dir}/anat/tmp.txt

                3dROIstats \
                    -quiet \
                    -mask {seed_file} \
                    {reg_file} > {seed_ts}
            """
            _, _ = submit.submit_hpc_subprocess(h_cmd)
        assert os.path.exists(
            seed_file
        ), f"Failed to write {seed_file}, check resources.afni.group.resting_seed."

    # project correlation matrix, z-transform
    for seed in coord_dict:
        corr_file = reg_file.replace("+tlrc", f"_{seed}_corr")
        ztrans_file = reg_file.replace("+tlrc", f"_{seed}_ztrans")
        seed_ts = file_censor.replace("desc-censor", f"desc-RS{seed}")
        if not os.path.exists(f"{ztrans_file}+tlrc.HEAD"):
            print(f"Making Ztrans  {ztrans_file}\n")
            h_cmd = f"""
                3dTcorr1D \
                    -mask {int_mask} \
                    -prefix {corr_file} \
                    {reg_file} \
                    {seed_ts}

                3dcalc \
                    -a {corr_file}+tlrc \
                    -expr 'log((1+a)/(1-a))/2' \
                    -prefix {ztrans_file}
            """
            _, _ = submit.submit_hpc_sbatch(
                h_cmd, 1, 4, 1, f"{subj_num}Ztran", f"{work_dir}/sbatch_out"
            )
        assert os.path.exists(
            f"{ztrans_file}+tlrc.HEAD"
        ), f"Failed to write {ztrans_file}+tlrc.HEAD, check resources.afni.group.resting_seed."
        afni_data[f"S{seed}-ztrans"] = f"{ztrans_file}+tlrc"
    return afni_data
