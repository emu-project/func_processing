"""Write and run deconvolution commands.

Use AFNI's 3dDeconvolve and 3dREMLfit to deconvolve
pre-processed EPI data.

Notes
-----
Requires "submit" module at same level.
"""

import os
import pandas as pd
import glob
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
        contains names for various files
    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A
    dur : int/float/str
        duration of event to model

    Returns
    -------
    afni_data : dict
        updated with REML commands
        {"dcn-<decon_name>": foo_stats.REML_cmd}

    Notes
    -----
    Requires afni_data["epi-scale*"], afni_data["mot-mean"],
        afni_data["mot-deriv"], and afni_data["mot-censor"].
    Deconvolution files will be written in AFNI format, rather
        than BIDS. This includes the X.files (cue spooky theme), script,
        and deconvolved output. Files names will have the format:
            decon_<bids-task>_<decon_name>
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
        h_out, h_err = submit.submit_hpc_subprocess(cmd_decon)

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
        contains names for various files

    Returns
    -------
    afni_data : dict
        updated for nuissance, deconvolved files
        epi-nuiss = nuissance signal file
        rml-<decon_name> = deconvolved file (<decon_name>_stats_REML+tlrc)
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
        job_name, job_id = submit.submit_hpc_sbatch(
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
            job_name, job_id = submit.submit_hpc_sbatch(
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
        {<decon_name>: {
            beh-A: /path/to/*_desc-behA_events.1D,
            beh-B: /path/to/*_desc-behB_events.1D,
            }
        }

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

    # Once events file is complete, iterate across trial_types to produce AFNI style events file
    decon_plan = {decon_name: {}}
    for trial_type, type_frame in events_data.groupby("trial_type"):

        # determine description/behavior name per session
        beh_name = trial_type if sess == "ses-S1" else switch_names[trial_type]

        # Write timing file, make sure to start with empty file
        # since runs will be appended as new lines.
        timing_file = f"{work_dir}/{subj}_{sess}_{task}_desc-{beh_name}_events.1D"
        open(timing_file, "w").close()

        wf = open(timing_file, "a")
        for _, run_frame in type_frame.groupby("run"):
            if run_frame.empty:
                wf.writelines("*")
            else:
                h_line = run_frame["onset"].round().tolist()
                wf.writelines(" ".join(map(str, h_line)))
            wf.write("\n")
        wf.close()

        # build decon_plan
        decon_plan[decon_name][beh_name] = timing_file

    return decon_plan
