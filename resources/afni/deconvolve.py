"""Write and run deconvolution commands.

Use AFNI's 3dDeconvolve and 3dREMLfit to deconvolve
pre-processed EPI data.
"""

import os
import glob
import math
import json
import pandas as pd
from . import submit


def write_decon(decon_name, tf_dict, afni_data, work_dir, dur):
    """Generate deconvolution script.

    Write a deconvolution script using the pre-processed data, motion, and
    censored files passed by afni_data. Uses a 2GAM basis function
    (AFNI's TWOGAMpw). This script is used to generate X.files and the
    foo_stats.REML_cmd.

    Timing files should contain AFNI-formatted onset times (duration is hardcoded),
    using the asterisk for runs in which a certain behavior does not occur.

    Parameters
    ----------
    decon_name: str
        name of deconvolution, useful when conducting multiple
        deconvolutions on same session. Will be appended to
        BIDS task name (decon_<task-name>_<decon_name>).

    tf_dict : dict
        timing files dictionary, behavior string is key

        e.g. {"lureFA": "/path/to/tf_task-test_lureFA.txt"}

    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [epi-scale<1..N>] = list of scaled files

        - [mot-mean] = mean motion timeseries

        - [mot-deriv] = derivative motion timeseries

        - [mot-censor] = binary censory vector

    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    dur : int/float/str
        duration of event to model

    Returns
    -------
    afni_data : dict
        updated with REML commands

        added afni_data keys:

        - [dcn-<decon_name>] = name of decon reml command

    Notes
    -----
    Deconvolution files will be written in AFNI format, rather
    than BIDS. This includes the X.files (cue spooky theme), script,
    and deconvolved output.

    Files names will have the format:

    - decon_<bids-task>_<decon_name>
    """
    # check for req files
    num_epi = len([y for x, y in afni_data.items() if "epi-scale" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-scale?'] not found. Check resources.afni.process.scale_epi."
    assert (
        afni_data["mot-mean"] and afni_data["mot-deriv"] and afni_data["mot-censor"]
    ), "ERROR: missing afni_data[mot-*] files, check resources.afni.motion.mot_files."

    # set regressors - baseline
    reg_base = [
        f"""-ortvec {afni_data["mot-mean"]} mot_mean""",
        f"""-ortvec {afni_data["mot-deriv"]} mot_deriv""",
    ]

    # set regressors - behavior
    reg_beh = []
    for c_beh, beh in enumerate(tf_dict):

        # add stim_time info, order is
        #   -stim_times 1 tf_beh.txt basisFunction
        reg_beh.append("-stim_times")
        reg_beh.append(f"{c_beh + 1}")
        reg_beh.append(f"{tf_dict[beh]}")
        reg_beh.append(f"'TWOGAMpw(4,5,0.2,12,7,{dur})'")

        # add stim_label info, order is
        #   -stim_label 1 beh
        reg_beh.append("-stim_label")
        reg_beh.append(f"{c_beh + 1}")
        reg_beh.append(beh)

    # set output str
    epi_list = [x for k, x in afni_data.items() if "epi-scale" in k]
    task_str = "task-" + epi_list[0].split("task-")[1].split("_")[0]
    out_str = f"decon_{task_str}_{decon_name}"

    # build full decon command
    func_dir = os.path.join(work_dir, "func")
    cmd_decon = f"""
        3dDeconvolve \\
            -x1D_stop \\
            -GOFORIT \\
            -input {" ".join(epi_list)} \\
            -censor {afni_data["mot-censor"]} \\
            {" ".join(reg_base)} \\
            -polort A \\
            -float \\
            -local_times \\
            -num_stimts {len(tf_dict.keys())} \\
            {" ".join(reg_beh)} \\
            -jobs 1 \\
            -x1D {func_dir}/X.{out_str}.xmat.1D \\
            -xjpeg {func_dir}/X.{out_str}.jpg \\
            -x1D_uncensored {func_dir}/X.{out_str}.nocensor.xmat.1D \\
            -bucket {func_dir}/{out_str}_stats \\
            -cbucket {func_dir}/{out_str}_cbucket \\
            -errts {func_dir}/{out_str}_errts
    """

    # write for review
    decon_script = os.path.join(func_dir, f"{out_str}.sh")
    with open(decon_script, "w") as script:
        script.write(cmd_decon)

    # generate x-matrices, reml command
    out_file = os.path.join(func_dir, f"{out_str}_stats.REML_cmd")
    if not os.path.exists(out_file):
        print(f"Running 3dDeconvolve for {decon_name}")
        _, _ = submit.submit_hpc_subprocess(cmd_decon)

    # update afni_data
    assert os.path.exists(
        out_file
    ), f"{out_file} failed to write, check resources.afni.deconvolve.write_decon."
    afni_data[f"dcn-{decon_name}"] = out_file

    return afni_data


def write_new_decon(decon_name, tf_dict, afni_data, work_dir, dur):
    """Write a deconvolution script using new censor approach.

    Rather than using desc-censor_events.tsv to remove volumes at the
    deconvolution, as is the default in AFNI\'s workflow, instead use
    the censor file to remove behaviors that co-occur during the
    same volume. Then, add a baseline censor regressor after polynomials
    but before the behavior regressors.

    Additionally, convolution of the timing file with the HRF basis
    function is supplied as the regressor via "-stim_file" rather
    using the "-stim_times" option. This is because I don't remember
    how to go from a binary vector in volume time to AFNI-styled
    timing files =).

    Parameters
    ----------
    decon_name: str
        name of deconvolution, useful when conducting multiple
        deconvolutions on same session. Will be appended to
        BIDS task name (decon_<task-name>_<decon_name>).

    tf_dict : dict
        timing files dictionary, behavior string is key

        e.g. {"lureFA": "/path/to/tf_task-test_lureFA.txt"}

    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [epi-scale<1..N>] = list of scaled files

        - [mot-mean] = mean motion timeseries

        - [mot-deriv] = derivative motion timeseries

        - [mot-censor] = binary censory vector (0 = censor)

        - [mot-censorInv] = inverted binary censory vector (1 = censor)

    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    dur : int/float/str
        duration of event to model

    Returns
    -------
    afni_data : dict
        updated with REML commands

        added afni_data keys:

        - [dcn-<decon_name>] = name of decon reml command

    Notes
    -----
    Deconvolution files will be written in AFNI format, rather
    than BIDS. This includes the X.files (cue spooky theme), script,
    and deconvolved output.

    Files names will have the format:

    - decon_<bids-task>_<decon_name>

    Also, writes info_behavior_censored.json to subject directory.
    """
    # check for req files
    num_epi = len([y for x, y in afni_data.items() if "epi-scale" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-scale?'] not found. Check resources.afni.process.scale_epi."
    assert (
        afni_data["mot-mean"]
        and afni_data["mot-deriv"]
        and afni_data["mot-censor"]
        and afni_data["mot-censorInv"]
    ), "ERROR: missing afni_data[mot-*] files, check resources.afni.motion.mot_files."

    # make list
    epi_list = [x for k, x in afni_data.items() if "epi-scale" in k]

    # get TR
    h_out, _ = submit.submit_hpc_subprocess(f"3dinfo -tr {epi_list[0]}")
    len_tr = float(h_out.decode("utf-8").strip())

    # list of run lengths in seconds, and total run length
    run_len = []
    num_vol = []
    for epi_file in epi_list:
        h_out, _ = submit.submit_hpc_subprocess(f"3dinfo -ntimes {epi_file}")
        h_vol = int(h_out.decode("utf-8").strip())
        run_len.append(str(h_vol * len_tr))
        num_vol.append(h_vol)
    sum_vol = sum(num_vol)

    # make ideal HRF with two gamma function
    hrf_file = os.path.join(os.path.dirname(epi_list[0]), "HRF_model.1D")
    if not os.path.exists(hrf_file):
        print("\nMaking ideal HRF")
        h_cmd = f"""
            3dDeconvolve\
                -polort -1 \
                -nodata {round((1 / len_tr) * 19)} {len_tr} \
                -num_stimts 1 \
                -stim_times 1 1D:0 'TWOGAMpw(4,5,0.2,12,7,{dur})' \
                -x1D {hrf_file} \
                -x1D_stop
        """
        _, _ = submit.submit_hpc_subprocess(h_cmd)
    assert os.path.exists(
        hrf_file
    ), "HRF model failed, check resources.afni.deconvolve.write_new_decon."

    # create adjusted behavior waveform
    tf_adjust = {}
    mot_report = {}
    for h_beh, h_tf in tf_dict.items():

        # make binary vector for behavior
        print(f"\nMaking behavior vectors for {h_beh}")
        beh_vec = h_tf.replace("_events.", "_events_vec.")
        h_cmd = f"""
            timing_tool.py \
                -timing {h_tf} \
                -tr {len_tr} \
                -stim_dur {dur} \
                -run_len {" ".join(run_len)} \
                -min_frac 0.3 \
                -timing_to_1D {beh_vec}
        """
        print(f"\n Bin vect cmd:\n\t {h_cmd}")
        _, _ = submit.submit_hpc_subprocess(h_cmd)
        assert os.path.exists(beh_vec), (
            f"Failed to write binary behavior vector for {h_beh}, "
            "check resources.afni.deconvolve.write_new_decon."
        )

        # remove behavior volumes when they co-occur with motion
        beh_cens = h_tf.replace("_events.", "_events_cens.")
        h_cmd = f"""
            1deval \
                -a {beh_vec} \
                -b {afni_data["mot-censor"]} \
                -expr 'a*b' \
                > {beh_cens}
        """
        _, _ = submit.submit_hpc_subprocess(h_cmd)

        # determine number of behaviors excluded
        df_orig = pd.read_csv(beh_vec)
        df_adj = pd.read_csv(beh_cens)
        num_orig = df_orig.sum().tolist()[0]
        num_adj = df_adj.sum().tolist()[0]
        num_diff = num_orig - num_adj
        mot_report[h_beh] = {"Orig": num_orig, "Adj": num_adj, "Diff": num_diff}

        # convolve adjusted behavior vector with HRF
        beh_adj = h_tf.replace(f"desc-{h_beh}", f"desc-{h_beh}Cens")
        h_cmd = f"""
            waver \
                -FILE {len_tr} {hrf_file} \
                -peak 1 \
                -TR {len_tr} \
                -input {beh_cens} \
                -numout {sum_vol} \
                > {beh_adj}
        """
        _, _ = submit.submit_hpc_subprocess(h_cmd)

        # check output, update dict with adjusted file
        assert os.stat(beh_adj).st_size > 0, (
            f"Adjusting timing file failed for {h_beh}, "
            "check resources.afni.deconvolve.write_new_decon."
        )
        tf_adjust[h_beh] = beh_adj

    # write motion adjust report
    mot_json = os.path.join(os.path.dirname(epi_list[0]), "info_behavior_censored.json")
    with open(mot_json, "w") as j_file:
        json.dump(mot_report, j_file)

    # set baseline regressors
    reg_base = [
        f"""-ortvec {afni_data["mot-mean"]} mot_mean""",
        f"""-ortvec {afni_data["mot-deriv"]} mot_deriv""",
    ]

    # set inverted censor as baseline regressor, start regressor count
    c_beh = 1
    reg_cens = [f"-stim_file {c_beh} {afni_data['mot-censorInv']}"]
    reg_cens.append(f"-stim_base {c_beh}")
    reg_cens.append(f"-stim_label {c_beh} mot_cens")

    # set behavior regressors
    reg_beh = []
    for h_beh, h_tf in tf_adjust.items():
        c_beh += 1
        reg_beh.append(f"-stim_file {c_beh} {h_tf}")
        reg_beh.append(f"-stim_label {c_beh} {h_beh}")

    # set output str
    task_str = "task-" + epi_list[0].split("task-")[1].split("_")[0]
    out_str = f"decon_{task_str}_{decon_name}"

    # build full decon command, put censor as baseline regressor
    func_dir = os.path.join(work_dir, "func")
    cmd_decon = f"""
        3dDeconvolve \\
            -x1D_stop \\
            -GOFORIT \\
            -input {" ".join(epi_list)} \\
            {" ".join(reg_base)} \\
            -polort A \\
            -float \\
            -local_times \\
            -num_stimts {c_beh} \\
            {" ".join(reg_cens)} \\
            {" ".join(reg_beh)} \\
            -jobs 1 \\
            -x1D {func_dir}/X.{out_str}.xmat.1D \\
            -xjpeg {func_dir}/X.{out_str}.jpg \\
            -x1D_uncensored {func_dir}/X.{out_str}.nocensor.xmat.1D \\
            -bucket {func_dir}/{out_str}_stats \\
            -cbucket {func_dir}/{out_str}_cbucket \\
            -errts {func_dir}/{out_str}_errts
    """

    # write for review
    decon_script = os.path.join(func_dir, f"{out_str}.sh")
    with open(decon_script, "w") as script:
        script.write(cmd_decon)

    # generate x-matrices, reml command
    out_file = os.path.join(func_dir, f"{out_str}_stats.REML_cmd")
    if not os.path.exists(out_file):
        print(f"Running 3dDeconvolve for {decon_name}")
        _, _ = submit.submit_hpc_subprocess(cmd_decon)

    # update afni_data
    assert os.path.exists(
        out_file
    ), f"{out_file} failed to write, check resources.afni.deconvolve.write_decon."
    afni_data[f"dcn-{decon_name}"] = out_file

    return afni_data


def run_reml(work_dir, afni_data):
    """Deconvolve EPI timeseries.

    Generate an idea of nuissance signal from the white matter and
    include this in the generated 3dREMLfit command.

    Parameters
    ----------
    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [epi-scale<1..N>] = list of scaled files

        - [mask-erodedWM] = eroded WM mask

    Returns
    -------
    afni_data : dict
        updated for nuissance, deconvolved files

        added afni_data keys:

        - [epi-nuiss] = nuissance signal file

        - [rml-<decon_name>] = deconvolved file (<decon_name>_stats_REML+tlrc)
    """
    # check for files
    num_epi = len([y for x, y in afni_data.items() if "epi-scale" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-scale?'] not found. Check resources.afni.process.scale_epi."

    assert afni_data[
        "mask-erodedWM"
    ], "ERROR: afni_data['mask-erodedWM'] not found. Check resources.afni.masks.make_tissue_masks."

    # generate WM timeseries (nuissance file) for task
    epi_list = [x for k, x in afni_data.items() if "epi-scale" in k]
    eroded_mask = afni_data["mask-erodedWM"]
    nuiss_file = (
        epi_list[0].replace("_run-1", "").replace("desc-scaled", "desc-nuissance")
    )
    subj_num = epi_list[0].split("sub-")[-1].split("_")[0]

    if not os.path.exists(nuiss_file):
        print(f"Making nuissance file {nuiss_file} ...")
        tcat_file = "tmp_tcat.sub".join(nuiss_file.rsplit("sub", 1))
        epi_eroded = "tmp_epi.sub".join(eroded_mask.rsplit("sub", 1))
        h_cmd = f"""
            3dTcat -prefix {tcat_file} {" ".join(epi_list)}

            3dcalc \
                -a {tcat_file} \
                -b {eroded_mask} \
                -expr 'a*bool(b)' \
                -datum float \
                -prefix {epi_eroded}

            3dmerge \
                -1blur_fwhm 20 \
                -doall \
                -prefix {nuiss_file} \
                {epi_eroded}
        """
        _, _ = submit.submit_hpc_sbatch(
            h_cmd, 1, 4, 1, f"{subj_num}wts", f"{work_dir}/sbatch_out"
        )
    assert os.path.exists(
        nuiss_file
    ), f"{nuiss_file} failed to write, check resources.afni.deconvolve.run_reml."
    afni_data["epi-nuiss"] = nuiss_file

    # run each planned deconvolution
    num_dcn = len([y for x, y in afni_data.items() if "dcn-" in x])
    assert (
        num_dcn > 0
    ), "ERROR: afni_data['dcn-*'] not found. Check resources.afni.deconvolve.write_decon."

    reml_list = [x for k, x in afni_data.items() if "dcn-" in k]
    for reml_script in reml_list:
        decon_name = reml_script.split("decon_")[1].split("_")[1]
        reml_out = reml_script.replace(".REML_cmd", "_REML+tlrc.HEAD")
        if not os.path.exists(reml_out):
            print(f"Starting 3dREMLfit for {decon_name} ...")
            h_cmd = f"""
                tcsh \
                    -x {reml_script} \
                    -dsort {afni_data["epi-nuiss"]} \
                    -GOFORIT
            """
            _, _ = submit.submit_hpc_sbatch(
                h_cmd, 25, 4, 6, f"{subj_num}rml", f"{work_dir}/sbatch_out"
            )
        assert os.path.exists(
            reml_out
        ), f"{reml_out} failed to write, check resources.afni.deconvolve.run_reml."
        afni_data[f"rml-{decon_name}"] = reml_out.split(".")[0]

    return afni_data


def timing_files(dset_dir, deriv_dir, subj, sess, task, decon_name="UniqueBehs"):
    """Generate AFNI timing files.

    Written specifically for the EMU study. Use dset/func/events.tsv
    files to generate AFNI-style timing files for each unique
    behavior (trial_type).

    Parameters
    ----------
    dset_dir : str
        /path/to/BIDS/dset

    deriv_dir : str
        /path/to/BIDS/derivatives/afni

    subj : str
        BIDS subject string (sub-1234)

    sess : str
        BIDS session string (ses-A)

    task : str
        BIDS task string (task-test)

    decon_name : str
        name of deconvolution given all unique behaviors [default=UniqueBehs]

    Returns
    -------
    decon_plan : dict
        Matches behaviors to timing file

        keys description:

        - [beh-A] = /path/to/foo_desc-behA_events.1D

        - [beh-B] = /path/to/foo_desc-behB_events.1D

    Notes
    -----
    Currently only writes onset time, not married duration.

    Behavior key (beh-A, beh-B above) become label of deconvolved sub-brick.
    """
    # make switch for AFNI-length names of ses-S2 behaviors, awkward
    # NR switch is for consistency with ses-S1.
    switch_names = {
        "neg_targ_ht": "negTH",
        "neg_targ_ms": "negTM",
        "neg_lure_cr": "negLC",
        "neg_lure_fa": "negLF",
        "neg_foil_cr": "negFC",
        "neg_foil_fa": "negFF",
        "neu_targ_ht": "neuTH",
        "neu_targ_ms": "neuTM",
        "neu_lure_cr": "neuLC",
        "neu_lure_fa": "neuLF",
        "neu_foil_cr": "neuFC",
        "neu_foil_fa": "neuFF",
        "pos_targ_ht": "posTH",
        "pos_targ_ms": "posTM",
        "pos_lure_cr": "posLC",
        "pos_lure_fa": "posLF",
        "pos_foil_cr": "posFC",
        "pos_foil_fa": "posFF",
        "NR": "NR",
    }

    # Structure subject output and input Paths based on subject and session (if specified)
    work_dir = os.path.join(deriv_dir, subj, sess, "func")
    source_dir = os.path.join(dset_dir, subj, sess, "func")

    # If events files are present in source_dir, produce combined events file from all runs
    events_files = sorted(glob.glob(f"{source_dir}/*{task}*_events.tsv"))
    if not events_files:
        raise ValueError(
            f"""Task name: "{task}" returned no events.tsv files in {source_dir}"""
        )
    events_data = [pd.read_table(x) for x in events_files]
    for idx, _ in enumerate(events_data):
        events_data[idx]["run"] = idx + 1
    events_data = pd.concat(events_data)
    events_data.fillna("NR", inplace=True)

    # determine behaviors, runs
    beh_list = events_data.trial_type.unique()
    run_list = sorted(events_data.run.unique())

    # start with empty timing files, fill decon_plan
    decon_plan = {decon_name: {}}
    for beh in beh_list:
        beh_name = beh if sess == "ses-S1" else switch_names[beh]
        h_tf = f"{work_dir}/{subj}_{sess}_{task}_desc-{beh_name}_events.1D"
        open(h_tf, "w").close()
        decon_plan[decon_name][beh_name] = h_tf

    # append timing files by row for e/run * behavior
    for run in run_list:
        df_run = events_data[events_data["run"] == run]
        for beh in beh_list:
            beh_name = beh if sess == "ses-S1" else switch_names[beh]
            timing_file = f"{work_dir}/{subj}_{sess}_{task}_desc-{beh_name}_events.1D"
            idx_beh = df_run.index[df_run["trial_type"] == beh].tolist()
            if not idx_beh:
                with open(timing_file, "a") as h_tf:
                    h_tf.writelines("*\n")
            else:
                onsets = df_run.iloc[idx_beh]["onset"].round().tolist()
                with open(timing_file, "a") as h_tf:
                    h_tf.writelines(f"""{" ".join(map(str, onsets))}\n""")

    return decon_plan


def regress_resting(afni_data, work_dir, proj_meth="anaticor"):
    """Construct regression matrix for resting state data.

    Conduct a principal components analysis to identify
    CSF timeseries. Use CSF timeseries as nuissance regressor,
    along with motion etc to clean signal via deconvolution.
    Residuals (cleaned signal) are then used to project regression
    matrices. Anaticor uses WM as a nuissance regressor.

    Parameters
    ----------
    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [epi-scale1] = single/first scaled file

        - [mask-min] = mask of voxels with >min signal

        - [mask-erodedCSF] = eroded CSF mask

        - [mot-mean] = mean motion timeseries

        - [mot-deriv] = derivative motion timeseries

        - [mot-censor] = binary censor vector

    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    proj_meth : str
        [anaticor | original] method of matrix progression.

    Returns
    -------
      decon_plan : dict
        Matches behaviors to timing file

        new key:

        - [reg-matrix] = regression matrix

    Notes
    -----
    Only supports RS conducted in single run
    """
    # check for req files
    num_epi = len([y for x, y in afni_data.items() if "epi-scale" in x])
    assert num_epi == 1, (
        "ERROR: afni_data['epi-scale1'] not found, or too many RS files."
        "Check resources.afni.process.scale_epi."
    )

    assert (
        afni_data["mask-min"] and afni_data["mask-erodedCSF"]
    ), "ERROR: required masks (min, erodedCSF) not found. Check resources.afni.masks."

    assert (
        afni_data["mot-mean"] and afni_data["mot-deriv"] and afni_data["mot-censor"]
    ), "ERROR: missing afni_data[mot-*] files, check resources.afni.motion.mot_files."

    # set up strings
    epi_file = afni_data["epi-scale1"]
    file_censor = afni_data["mot-censor"]
    subj_num = epi_file.split("sub-")[-1].split("_")[0]

    # Conduct PCA to identify CSF signal - mask EPI data
    # by minimum mask to avoid projecting into non-brain spaces. Then
    # conduct PC analysis to derive timeseries of CSF.
    file_pcomp = file_censor.replace("censor", "csfPC")
    masked_epi = epi_file.replace("scaled", "masked")
    if not os.path.exists(file_pcomp):
        print(f"\nStarting PCA for {epi_file} ...")

        # set file strings
        tmp_censor = file_censor.replace("censor", "tmp-censor")
        project_epi = epi_file.replace("scaled", "project")
        roi_pcomp = file_censor.replace("censor", "roiPC")

        # determine polynomial order
        h_out, _ = submit.submit_hpc_subprocess(f"3dinfo -ntimes {epi_file}")
        tr_count = int(h_out.decode("utf-8").strip())
        h_out, _ = submit.submit_hpc_subprocess(f"3dinfo -tr {epi_file}")
        tr_len = float(h_out.decode("utf-8").strip())
        num_pol = 1 + math.ceil((tr_count * tr_len) / 150)

        # do PCA - account for censored vols so they do not
        # influence detrending.
        h_cmd = f"""
            3dcalc \
                -a {epi_file} \
                -b {afni_data["mask-min"]} \
                -expr 'a*b' \
                -prefix {masked_epi}

            1d_tool.py \
                -set_run_lengths {tr_count} \
                -select_runs 1 \
                -infile {file_censor} \
                -write {tmp_censor}

            3dTproject \
                -polort {num_pol} \
                -prefix {project_epi} \
                -censor {tmp_censor} \
                -cenmode KILL \
                -input {masked_epi}

            3dpc \
                -mask {afni_data["mask-erodedCSF"]} \
                -pcsave 3 \
                -prefix {roi_pcomp} \
                {project_epi}

            1d_tool.py \
                -censor_fill_parent {tmp_censor} \
                -infile {roi_pcomp}_vec.1D \
                -write - | 1d_tool.py \
                -set_run_lengths {tr_count} \
                -pad_into_many_runs 1 1 \
                -infile - -write {file_pcomp}
        """
        _, _ = submit.submit_hpc_sbatch(
            h_cmd, 1, 8, 1, f"{subj_num}PC", f"{work_dir}/sbatch_out"
        )
    assert os.path.exists(
        file_pcomp
    ), f"{file_pcomp} failed to write, check resources.afni.deconvolve.regress_resting."

    # Build deconvolve command, write script for review.
    # This will load effects of no interest on fitts sub-brick, and
    # errts will contain cleaned time series. CSF time series is
    # used as a nuissance regressor.
    print("\nWriting 3dDeconvolve for Resting data ...")
    func_dir = os.path.join(work_dir, "func")
    out_str = "decon_task-rest"
    cmd_decon = f"""
        3dDeconvolve \
            -x1D_stop \
            -input {epi_file} \
            -censor {file_censor} \
            -ortvec {file_pcomp} csf_ts \
            -ortvec {afni_data["mot-mean"]} mot_mean \
            -ortvec {afni_data["mot-deriv"]} mot_deriv \
            -polort A \
            -fout -tout \
            -x1D {func_dir}/X.{out_str}.xmat.1D \
            -xjpeg {func_dir}/X.{out_str}.jpg \
            -x1D_uncensored {func_dir}/X.{out_str}.nocensor.xmat.1D \
            -fitts {func_dir}/{out_str}_fitts \
            -errts {func_dir}/{out_str}_errts \
            -bucket {func_dir}/{out_str}_stats
    """
    decon_script = os.path.join(func_dir, f"{out_str}.sh")
    with open(decon_script, "w") as script:
        script.write(cmd_decon)

    # generate x-matrices
    xmat_file = os.path.join(func_dir, f"X.{out_str}.xmat.1D")
    if not os.path.exists(xmat_file):
        print("\nRunning 3dDeconvolve for Resting data")
        h_out, _ = submit.submit_hpc_subprocess(cmd_decon)
    assert os.path.exists(
        xmat_file
    ), f"{xmat_file} failed to write, check resources.afni.deconvolve.regress_resting."

    # project regression matrix
    if proj_meth == "original":
        epi_tproject = os.path.join(func_dir, f"{out_str}_tproject+tlrc")
        if not os.path.exists(f"{epi_tproject}.HEAD"):
            print(f"\nProject regression matrix as {epi_tproject}")
            h_cmd = f"""
                3dTproject \
                    -polort 0 \
                    -input {epi_file} \
                    -censor {file_censor} \
                    -cenmode ZERO \
                    -ort {func_dir}/X.{out_str}.nocensor.xmat.1D \
                    -prefix {epi_tproject}
            """
            _, _ = submit.submit_hpc_sbatch(
                h_cmd, 1, 8, 1, f"{subj_num}Proj", f"{work_dir}/sbatch_out"
            )
        assert os.path.exists(
            f"{epi_tproject}.HEAD"
        ), f"{epi_tproject}.HEAD failed to write, check resources.afni.deconvolve.regress_resting."
        afni_data["reg-matrix"] = epi_tproject

    # project via anaticor method
    if proj_meth == "anaticor":
        epi_anaticor = os.path.join(func_dir, f"{out_str}_anaticor+tlrc")
        if not os.path.exists(f"{epi_anaticor}.HEAD"):
            print(f"\nProject regression matrix as {epi_anaticor}")
            comb_mask = epi_file.replace("scaled", "combWM")
            blur_mask = epi_file.replace("scaled", "blurWM")

            # get WM timeseries, generate blurred anaticor (WM)
            # regressors, project regression
            h_cmd = f"""
                3dcalc \
                    -a {masked_epi} \
                    -b {afni_data["mask-erodedWM"]} \
                    -expr 'a*bool(b)' \
                    -datum float \
                    -prefix {comb_mask}

                3dmerge \
                    -1blur_fwhm 60 \
                    -doall \
                    -prefix {blur_mask} \
                    {comb_mask}

                3dTproject \
                    -polort 0 \
                    -input {epi_file} \
                    -censor {file_censor} \
                    -cenmode ZERO \
                    -dsort {blur_mask} \
                    -ort {func_dir}/X.{out_str}.nocensor.xmat.1D \
                    -prefix {epi_anaticor}
            """
            _, _ = submit.submit_hpc_sbatch(
                h_cmd, 1, 8, 1, f"{subj_num}Proj", f"{work_dir}/sbatch_out"
            )
        assert os.path.exists(
            f"{epi_anaticor}.HEAD"
        ), f"{epi_anaticor}.HEAD failed to write, check resources.afni.deconvolve.regress_resting."
        afni_data["reg-matrix"] = epi_anaticor

    return afni_data
