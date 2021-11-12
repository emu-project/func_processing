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


def write_decon(dur, decon_str, tf_dict, afni_data, work_dir):
    """Generate deconvolution script.

    Write a deconvolution script using the pre-processed data, motion, and
    censored files passed by afni_data. Uses a 2GAM basis function
    (AFNI's TWOGAMpw). This script is used to generate X.files and the
    foo_stats.REML_cmd.

    Timing files should contain AFNI-formatted onset times (duration is hardcoded),
    using the asterisk for runs in which a certain behavior does not occur.

    Parameters
    ----------
    dur : int/float
        duration of event to model
    decon_str: str
        name of deconvolution, useful when conducting multiple
        deconvolutions on same session. Will be appended to
        BIDS task name (decon_<task-name>_<decon_str>).
    tf_dict : dict
        timing files dictionary, behavior string is key
        e.g. {"lureFA": "/path/to/tf_task-test_lureFA.txt"}
    afni_data : dict
        contains names for various files
    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    Returns
    -------
    afni_data : dict
        updated with REML commands
        {"dcn-<decon_str>": foo_stats.REML_cmd}

    Notes
    -----
    Deconvolution files will be written in AFNI format, rather
    than BIDS. This includes the X.files (cue spooky theme), script,
    and deconvolved output. Files names will have the format:
        decon_<bids-task>_<decon_str>
    """

    # get pre-processed runs
    epi_list = [x for k, x in afni_data.items() if "epi-scale" in k]

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
    task_str = epi_list[0].split("_")[2]
    out_str = f"decon_{task_str}_{decon_str}"

    # build full decon command
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
            -x1D X.{out_str}.xmat.1D \\
            -xjpeg X.{out_str}.jpg \\
            -x1D_uncensored X.{out_str}.nocensor.xmat.1D \\
            -bucket {out_str}_stats \\
            -cbucket {out_str}_cbucket \\
            -errts {out_str}_errts
    """

    # write for review
    decon_script = os.path.join(work_dir, f"{out_str}.sh")
    with open(decon_script, "w") as script:
        script.write(cmd_decon)

    # run
    print(f"Running 3dDeconvolve for {decon_str}")
    h_cmd = f"""
        cd {work_dir}
        {cmd_decon}
    """
    h_out, h_err = submit.submit_hpc_subprocess(h_cmd)

    # update afni_data
    assert os.path.exists(
        os.path.join(work_dir, f"{out_str}_stats.REML_cmd")
    ), f"{out_str}_stats.REML_cmd failed to write, check resources.afni.deconvolve.write_decon."
    afni_data[f"dcn-{decon_str}"] = f"{out_str}_stats.REML_cmd"

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
        rml-<decon_str> = deconvolved file (<decon_str>_stats_REML+tlrc)
    """
    # generate WM timeseries (nuissance file) for task
    epi_list = [x for k, x in afni_data.items() if "epi-scale" in k]
    eroded_mask = afni_data["mask-erodedWM"]
    nuiss_file = (
        epi_list[0].replace("_run-1", "").replace("desc-scaled", "desc-nuissance")
    )
    subj_num = epi_list[0].split("_")[0].split("-")[-1]

    if not os.path.exists(os.path.join(work_dir, nuiss_file)):
        print(f"Making nuissance file {nuiss_file} ...")
        tcat_file = nuiss_file.replace("nuissance", "tcat")
        h_cmd = f"""
            cd {work_dir}

            3dTcat -prefix tmp_{tcat_file} {" ".join(epi_list)}

            3dcalc \
                -a tmp_{tcat_file} \
                -b {eroded_mask} \
                -expr 'a*bool(b)' \
                -datum float \
                -prefix tmp_epi_{eroded_mask}

            3dmerge \
                -1blur_fwhm 20 \
                -doall \
                -prefix {nuiss_file} \
                tmp_epi_{eroded_mask}

            if [ -f {nuiss_file} ]; then
                rm tmp*
            fi
        """
        job_name, job_id = submit.submit_hpc_sbatch(
            h_cmd, 1, 4, 1, f"{subj_num}wts", work_dir
        )
        assert os.path.exists(
            os.path.join(work_dir, nuiss_file)
        ), f"{nuiss_file} failed to write, check resources.afni.deconvolve.run_reml."
        afni_data["epi-nuiss"] = nuiss_file

    # run each planned deconvolution
    reml_list = [x for k, x in afni_data.items() if "dcn-" in k]
    for reml_script in reml_list:
        decon_str = reml_script.split("_")[2]
        reml_out = reml_script.replace(".REML_cmd", "_REML+tlrc.HEAD")
        if not os.path.exists(os.path.join(work_dir, reml_out)):
            print(f"Starting 3dREMLfit for {decon_str} ...")
            h_cmd = f"""
                cd {work_dir}
                tcsh \
                    -x {reml_script} \
                    -dsort {afni_data["epi-nuiss"]} \
                    -GOFORIT
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 25, 4, 6, f"{subj_num}rml", work_dir
            )
        assert os.path.exists(
            os.path.join(work_dir, reml_out)
        ), f"{reml_out} failed to write, check resources.afni.deconvolve.run_reml."
        afni_data[f"rml-{decon_str}"] = reml_out.split(".")[0]

    return afni_data


def timing_files(subj, sess, task, decon_name, timing_dir, dset_dir):

    # For testing
    subj = "sub-4002"
    sess = "ses-S2"
    task = "task-test"
    decon_name = "UniqueBehs"
    timing_dir = "/home/data/madlab/McMakin_EMUR01/derivatives/afni/timing_files"
    dset_dir = "/home/data/madlab/McMakin_EMUR01/dset"

    # Structure subject output and input Paths based on subject and session (if specified)
    afni_output = os.path.join(timing_dir, subj, sess)
    source_dir = os.path.join(dset_dir, subj, sess, "func")
    if not os.path.exists(afni_output):
        os.makedirs(afni_output)

    # If events files are present in source_dir, produce combined events file from all runs
    events_files = sorted(glob.glob(f"{source_dir}/*{task}*_events.tsv"))
    if not events_files:
        raise ValueError(f"""Task name: "{task}" returned no files""")
    events_data = [pd.read_table(x) for x in events_files]
    for idx, _ in enumerate(events_data):
        events_data[idx]["run"] = idx + 1
    events_data = pd.concat(events_data)

    # Once events file is complete, iterate across trial_types to produce AFNI style events file
    for trial_type, type_frame in events_data.groupby("trial_type"):
        valence, ttype, outcome = trial_type.split("_")
        trunc_name = valence + ttype[0].upper() + outcome[0].upper()
        if trial_type == "non_resp_tr":
            trunc_name = "NR"
        wf = open(afni_output / f"tf_{task}_{decon_name}_{trunc_name}.txt")
        for _, run_frame in type_frame.groupby("run"):
            if run_frame.empty():
                wf.writelines("*")
            else:
                wf.writelines(" ".join(run_frame["onset"].round().tolist()))
        wf.close()

    print(events_data)
