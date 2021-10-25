# %%
"""Generate and execute a deconvolution script.

This script will construct a deconvlution script for a
participant, and then execute the script. Uses AFNI's
3dDeconvolve to generate the needed X.matrix and
foobar_stats.REML_cmd, which runs 3dREMLfit.

Notes
-----
Currently only supports single decon per phase. Orients in
behaviors due to timing file naming convention.

Also, write_decon is a stripped-down version, supporting only
the TWOGAMpw basis function.

Behavior duration is hardcoded to 2s.

Examples
--------
func4_deconvolve.py \
    -p sub-4020 \
    -t test \
    -s ses-S2 \
    -n 3 \
    -a /scratch/madlab/emu_UNC/derivatives/afni
"""

import os
import subprocess
import pandas as pd
import fnmatch
import json
from func2_finish_preproc import func_sbatch
from argparse import ArgumentParser
import sys


# %%
def mot_files(work_dir, num_runs, task):
    """Constuct motion and censor files

    Mine <run>_motion_all.tsv for motion events, make
    motion files for mean (6df) and derivative (6df)
    motion events. Also, create motion censor file.
    Finally, report the number of censored volumes.

    I'm not sure if motion is demeaned or not, given that
    it is output by fMRIprep (mined from confounds.tsv file).

    Parameters
    ----------
    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A
    num_runs : int
        number of EPI runs
    task : str
        task identifier - test for task-test

    Notes
    -----
    Concats mot_*<run>.1D files given that not all my runs
    have the same number of volumes, and I don't feel like
    padding.

    MRI output : 1D files
        mot_demean_<task>_concat.1D
        mot_deriv_<task>_concat.1D
        mot_censor_<task>_concat.1D
    MRI output : json files
        info_volumes.json
    """

    # determine relevant col labels
    mean_labels = [
        "trans_x",
        "trans_y",
        "trans_z",
        "rot_x",
        "rot_y",
        "rot_z",
    ]

    drv_labels = [
        "trans_x_derivative1",
        "trans_y_derivative1",
        "trans_z_derivative1",
        "rot_x_derivative1",
        "rot_y_derivative1",
        "rot_z_derivative1",
    ]

    mean_cat = []
    deriv_cat = []
    censor_cat = []

    for run in range(0, num_runs):

        # read in data
        h_run = f"run-{run + 1}"
        df_all = pd.read_csv(
            os.path.join(work_dir, f"{h_run}_motion_all.tsv"), sep="\t"
        )

        # make motion demean file
        df_mean = df_all[mean_labels].copy()
        df_mean = df_mean.round(6)
        df_mean.to_csv(
            os.path.join(work_dir, f"mot_demean_{task}_{h_run}.1D"),
            sep=" ",
            index=False,
            header=False,
        )
        mean_cat.append(df_mean)

        # make motion deriv file
        df_drv = df_all[drv_labels].copy()
        df_drv = df_drv.fillna(0)
        df_drv = df_drv.round(6)
        df_drv.to_csv(
            os.path.join(work_dir, f"mot_deriv_{task}_{h_run}.1D"),
            sep=" ",
            index=False,
            header=False,
        )
        deriv_cat.append(df_drv)

        # make motion censor file
        #   invert binary, exclude preceding volume
        df_cen = df_all.filter(regex="motion_outlier")
        df_cen["sum"] = df_cen.sum(axis=1)
        df_cen = df_cen.astype(int)
        df_cen = df_cen.replace({0: 1, 1: 0})
        zero_pos = df_cen.index[df_cen["sum"] == 0].tolist()
        zero_fill = [x - 1 for x in zero_pos]
        if -1 in zero_fill:
            zero_fill.remove(-1)
        df_cen.loc[zero_fill, "sum"] = 0

        df_cen.to_csv(
            os.path.join(work_dir, f"mot_censor_{task}_{h_run}.1D"),
            sep=" ",
            index=False,
            header=False,
            columns=["sum"],
        )
        censor_cat.append(df_cen)

    # cat files into singular rather than pad zeros
    df_mean_cat = pd.concat(mean_cat, ignore_index=True)
    df_deriv_cat = pd.concat(deriv_cat, ignore_index=True)
    df_censor_cat = pd.concat(censor_cat, ignore_index=True)

    df_mean_cat.to_csv(
        os.path.join(work_dir, f"mot_demean_{task}_concat.1D"),
        sep=" ",
        index=False,
        header=False,
    )
    df_deriv_cat.to_csv(
        os.path.join(work_dir, f"mot_deriv_{task}_concat.1D"),
        sep=" ",
        index=False,
        header=False,
    )
    df_censor_cat.to_csv(
        os.path.join(work_dir, f"mot_censor_{task}_concat.1D"),
        sep=" ",
        index=False,
        header=False,
        columns=["sum"],
    )

    # determine number censored volumes
    num_vol = df_censor_cat["sum"].sum()
    num_tot = len(df_censor_cat)
    cen_dict = {
        "total_volumes": int(num_tot),
        "included_volumes": int(num_vol),
        "proportion_excluded": round(1 - (num_vol / num_tot), 3),
    }
    with open(os.path.join(work_dir, "info_volumes.json"), "w") as jfile:
        json.dump(cen_dict, jfile)


# %%
def write_decon(task, dur, work_dir):
    """Generate deconvolution script

    Create 3dDeconvolve command from available mot_*_concat.1D,
    run-?_<task>_scale+tlrc, and timing_files/tf_<task>_*.txt files.
    Uses the TWOGAMpw basis function, with a duration modulator.

    This is a simplified version, supporting only one basis function
    and taking advantage of ALL timing files in work_dir/timing_files.

    Parameters
    ----------
    task : str
        test for task-test
    dur : int
        duration of event to model
    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    Notes
    -----
    MRI output : decon files
        X.<task>_decon.jpg
        X.<task>_decon.nocensor.xmat.1D
        X.<task>_decon.xmat.1D
    MRI output : scripts
        decon_<task>.sh
        <task>_decon_stats.REML_cmd
    """

    # make timing file dict
    tf_list = os.listdir(os.path.join(work_dir, "timing_files"))
    tf_list.sort()
    tf_dict = {}
    for h_tf in tf_list:
        beh = h_tf.split("_")[-1].split(".")[0]
        tf_dict[beh] = h_tf

    # get pre-processed runs
    epi_list = [
        x.split(".")[0]
        for x in os.listdir(work_dir)
        if fnmatch.fnmatch(x, "*scale+tlrc.HEAD")
    ]
    epi_list.sort()

    # set regressors - baseline
    reg_base = [
        f"-ortvec mot_demean_{task}_concat.1D mot_dmn_1",
        f"-ortvec mot_deriv_{task}_concat.1D mot_drv_1",
    ]

    # set regressors - behavior
    reg_beh = []
    for c_beh, beh in enumerate(tf_dict):

        # add stim_time info, order is
        #   -stim_times 1 tf_beh.txt basisFunction
        reg_beh.append("-stim_times")
        reg_beh.append(f"{c_beh + 1}")
        reg_beh.append(f"timing_files/{tf_dict[beh]}")
        reg_beh.append(f"'TWOGAMpw(4,5,0.2,12,7,{dur})'")

        # add stim_label info, order is
        #   -stim_label 1 beh
        reg_beh.append("-stim_label")
        reg_beh.append(f"{c_beh + 1}")
        reg_beh.append(beh)

    # set output str
    h_out = f"{task}_decon"

    # build full decon command
    cmd_decon = f"""
        3dDeconvolve \\
            -x1D_stop \\
            -GOFORIT \\
            -input {" ".join(epi_list)} \\
            -censor mot_censor_{task}_concat.1D \\
            {" ".join(reg_base)} \\
            -polort A \\
            -float \\
            -local_times \\
            -num_stimts {len(tf_dict.keys())} \\
            {" ".join(reg_beh)} \\
            -jobs 1 \\
            -x1D X.{h_out}.xmat.1D \\
            -xjpeg X.{h_out}.jpg \\
            -x1D_uncensored X.{h_out}.nocensor.xmat.1D \\
            -bucket {h_out}_stats \\
            -cbucket {h_out}_cbucket \\
            -errts {h_out}_errts
    """

    # write for review
    decon_script = os.path.join(work_dir, f"decon_{task}.sh")
    with open(decon_script, "w") as script:
        script.write(cmd_decon)

    # run
    h_cmd = f"""
        module load afni-20.2.06
        cd {work_dir}
        source {decon_script}
    """
    h_dcn = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
    h_dcn.wait()


# %%
def run_reml(work_dir, task, sub_num):
    """Deconvolve EPI timeseries

    Generate an idea of nuissance signal from the white matter and
    include this in the generated 3dREMLfit command.

    Parameters
    ----------
    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A
    task : str
        test for task-test
    sub_num : int/str
        subject identifier for sbatch job

    Notes
    -----
    MRI output : functional
        <task>_WMe_rall+tlrc
        <task>_decon_cbucket_REML+tlrc
        <task>_decon_errts_REML+tlrc
        <task>_decon_stats_REML+tlrc
        <task>_decon_stats_REMLvar+tlrc
    """
    # generate WM timeseries
    if not os.path.exists(os.path.join(work_dir, f"{task}_WMe_rall+tlrc.HEAD")):
        h_cmd = f"""
            cd {work_dir}

            3dTcat -prefix tmp_allRuns_{task} run-*{task}_scale+tlrc.HEAD

            3dcalc \
                -a tmp_allRuns_{task}+tlrc \
                -b final_mask_WM_eroded+tlrc \
                -expr 'a*bool(b)' \
                -datum float \
                -prefix tmp_allRuns_{task}_WMe

            3dmerge \
                -1blur_fwhm 20 \
                -doall \
                -prefix {task}_WMe_rall \
                tmp_allRuns_{task}_WMe+tlrc
        """
        func_sbatch(h_cmd, 1, 4, 1, f"{sub_num}wts", work_dir)

    # run REML for each task of session
    h_cmd = f"""
        cd {work_dir}
        tcsh \
            -x {task}_decon_stats.REML_cmd \
            -dsort {task}_WMe_rall+tlrc \
            -GOFORIT
    """
    func_sbatch(h_cmd, 25, 4, 6, f"{sub_num}rml", work_dir)


def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser("Receive bash CLI args")
    requiredNamed = parser.add_argument_group("required named arguments")
    requiredNamed.add_argument(
        "-p", "--part-id", help="Participant ID (sub-1234)", type=str, required=True,
    )
    requiredNamed.add_argument(
        "-t",
        "--task-str",
        help="BIDS task-string (test, for task-test)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-s", "--sess-str", help="BIDS ses-string (ses-S2)", type=str, required=True,
    )
    requiredNamed.add_argument(
        "-n", "--num-runs", help="Number of EPI runs (int)", type=int, required=True,
    )
    requiredNamed.add_argument(
        "-a",
        "--afni-dir",
        help="/path/to/project/derivatives/afni",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Make motion files and deconvolve data."""

    # # For testing
    # afni_dir = "/scratch/madlab/emu_UNC/derivatives/afni"
    # subj = "sub-4002"
    # sess = "ses-S2"
    # task = "test"
    # num_runs = 3

    # set up
    args = get_args().parse_args()
    subj = args.part_id
    sess = args.sess_str
    task = args.task_str
    num_runs = args.num_runs
    afni_dir = args.afni_dir
    work_dir = os.path.join(afni_dir, subj, sess)

    # motion and censor
    if not os.path.exists(os.path.join(work_dir, f"mot_censor_{task}_concat.1D")):
        mot_files(work_dir, num_runs, task)

    # write decon script
    dur = 2
    write_decon(task, dur, work_dir)

    # run decon script
    if not os.path.exists(os.path.join(work_dir, f"{task}_decon_stats_REML+tlrc.HEAD")):
        run_reml(work_dir, task, subj.split("-")[-1])


if __name__ == "__main__":
    main()

# %%
