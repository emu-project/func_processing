"""Write and run deconvolution commands.

Use AFNI's 3dDeconvolve and 3dREMLfit to deconvolve
pre-processed EPI data.
"""

import os
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
    task : str
        test for task-test
    dur : int/float
        duration of event to model
    decon_str: str
        name of deconvolution, useful when conducting multiple
        deconvolutions on same session. Will be appended to
        BIDS task name (decon_<task-name>_<decon_str>).
    tf_dict : dict
        timing files dictionary, behavior string is key
        e.g. {"lureFA": "/path/to/tf_task-test_lureFA.txt"}
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
    h_cmd = f"""
        cd {work_dir}
        {cmd_decon}
    """
    h_out, h_err = submit.submit_hpc_subprocess(h_cmd)

    # update afni_data
    if os.path.exists(os.path.join(work_dir, f"{out_str}_stats.REML_cmd")):
        afni_data[f"dcn-{decon_str}"] = f"{out_str}_stats.REML_cmd"
    else:
        afni_data[f"dcn-{decon_str}"] = "Missing"

    return afni_data
