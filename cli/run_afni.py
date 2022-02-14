#!/usr/bin/env python

"""Pre-process and deconvolve fMRIprep output.

Incorpoarte fMRIprep output into an AFNI workflow, finish
pre-processing and deconvolve. Will attempt to submit a batch
of participants to a Slurm scheduler every 12 hours over
the course of a week.

By default, all unique behaviors (and non-responses) are modelled
for each subject/session, with user control via --json-dir. Input
directory for --json-dir should contain a json for each subject
in experiment (name format: subj-1234*.json). See
workflow.control_afni.control_deconvolution for guidance
in formatting the dictionary.

Default timing files written specifically for EMU (see
resources.afni.deconvolve.timing_files).

Supports task-based analyses, resting state will come soon.

Examples
--------
sbatch --job-name=runAfni \\
    --output=runAfni_log \\
    --mem-per-cpu=4000 \\
    --partition=IB_44C_512G \\
    --account=iacc_madlab \\
    --qos=pq_madlab \\
    run_afni.py \\
    -s ses-S2 \\
    -t task-test \\
    -c /home/nmuncy/compute/func_processing \\
    -p $TOKEN_GITHUB_EMU
"""


# %%
import os
import sys
import json
import glob
import time
import pandas as pd
from datetime import datetime
import textwrap
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def submit_jobs(
    afni_dir,
    proj_dir,
    subj,
    sess,
    task,
    code_dir,
    slurm_dir,
    tplflow_str,
    dur,
    do_decon,
    decon_plan,
    pat_github_emu,
):
    """Schedule work for single participant.

    Submit workflow.control_afni for a single subject, session,
    and task. Take data from fMRIprep output through deconvolution.
    Finally, clean up, and move relevant files to <afni_final>.

    Parameters
    ----------
    afni_dir : str
        path to /scratch directory, for intermediates
    proj_dir : str
        path to BIDS-formatted project directory
    subj : str
        BIDS subject string
    sess : str
        BIDS session string
    task : str
        BIDS task string
    code_dir : str
        path to clone of github.com/emu-project/func_processing.git
    slurm_dir : str
        path to location for capturing sbatch stdout/err
    tplflow_str : str
        template_flow identifier string
    dur : int/float/str
        duration of event to be modeled
    do_decon : bool
        whether to conduct deconvolution
    decon_plan : dict/None
        planned deconvolution with behavior: timing file mappings
    pat_github_emu : str
        Personal Access Token to https://github.com/emu-project

    Returns
    -------
    h_out, h_err : str
        stdout, stderr of sbatch submission
    """

    subj_num = subj.split("-")[-1]
    prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")
    dset_dir = os.path.join(proj_dir, "dset")
    afni_final = os.path.join(proj_dir, "derivatives/afni")

    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=p{subj_num}
        #SBATCH --output={slurm_dir}/out_{subj_num}.txt
        #SBATCH --time=10:00:00
        #SBATCH --mem=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab

        import os
        import sys
        import shutil
        import glob
        import subprocess
        sys.path.append("{code_dir}")
        from workflow import control_afni
        from resources.reports.check_complete import check_preproc

        afni_data = control_afni.control_preproc(
            "{prep_dir}",
            "{afni_dir}",
            "{subj}",
            "{sess}",
            "{task}",
            "{tplflow_str}",
        )

        if {do_decon}:
            afni_data = control_afni.control_deconvolution(
                afni_data,
                "{afni_dir}",
                "{dset_dir}",
                "{subj}",
                "{sess}",
                "{task}",
                "{dur}",
                {decon_plan},
            )
            print(f"Finished {subj}/{sess}/{task} with: \\n {{afni_data}}")

        # clean up
        shutil.rmtree(os.path.join("{afni_dir}", "{subj}", "{sess}", "sbatch_out"))
        clean_dir = os.path.join("{afni_dir}", "{subj}", "{sess}")
        clean_list = [
            "preproc_bold",
            "smoothed_bold",
            "nuissance_bold",
            "probseg",
            "preproc_T1w",
            "minval_mask",
            "GMe_mask",
        ]
        for c_str in clean_list:
            for h_file in glob.glob(f"{{clean_dir}}/**/*{{c_str}}.nii.gz", recursive=True):
                os.remove(h_file)

        # copy important files to /home/data
        h_cmd = f"cp -r {afni_dir}/{subj} {afni_final}"
        h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
        h_job = h_cp.communicate()

        # turn out the lights
        shutil.rmtree(os.path.join("{afni_dir}", "{subj}"))

        # update logs
        # check_preproc({proj_dir}, {code_dir}, {pat_github_emu}, one_subj="{subj}")
    """

    # write script for review, run it
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"preproc_decon_{subj_num}.py")
    with open(py_script, "w") as ps:
        ps.write(cmd_dedent)
    sbatch_response = subprocess.Popen(
        f"sbatch {py_script}", shell=True, stdout=subprocess.PIPE
    )
    h_out, h_err = sbatch_response.communicate()
    return (h_out, h_err)


# %%
def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)

    parser.add_argument(
        "--proj-dir",
        type=str,
        default="/home/data/madlab/McMakin_EMUR01",
        help=textwrap.dedent(
            """\
            path to BIDS-formatted project directory
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--batch-num",
        type=int,
        default=8,
        help=textwrap.dedent(
            """\
            number of subjects to submit at one time
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--tplflow-str",
        type=str,
        default="space-MNIPediatricAsym_cohort-5_res-2",
        help=textwrap.dedent(
            """\
            template ID string, for finding fMRIprep output in template space,
            (default : %(default)s)
        """
        ),
    )
    parser.add_argument(
        "--dur",
        type=str,
        default="2",
        help=textwrap.dedent(
            """\
            event duration, for deconvolution modulation
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--afni-dir",
        type=str,
        default="/scratch/madlab/McMakin_EMUR01/derivatives/afni",
        help=textwrap.dedent(
            """\
            Path to location for making AFNI intermediates
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--json-dir",
        type=str,
        default=None,
        help=textwrap.dedent(
            """\
            Path to directory containing JSON deconvolution plans for each
            subject. Must be titled <subject>*.json. See notes in
            workflow.control_afni.control_deconvolution for description
            of dictionary format. Default (None) results in all unique
            behaviors modeled (decon_<task>_UniqueBehs*).
            (default : %(default)s)
            """
        ),
    )

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-s", "--session", help="BIDS session str (ses-S2)", type=str, required=True,
    )
    required_args.add_argument(
        "-t", "--task", help="BIDS EPI task str (task-test)", type=str, required=True,
    )
    required_args.add_argument(
        "-p",
        "--pat",
        help="Personal Access Token for github.com/emu-project",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-c",
        "--code-dir",
        required=True,
        help="Path to clone of github.com/emu-project/func_processing.git",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():

    # # For testing
    # pat_github_emu = os.environ["TOKEN_GITHUB_EMU"]
    # proj_dir = "/Volumes/homes/MaDLab/projects/McMakin_EMUR01"
    # batch_num = 3
    # tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"
    # dur = 2
    # afni_dir = "/scratch/madlab/McMakin_EMUR01/derivatives/afni"
    # json_dir = None
    # sess = "ses-S2"
    # task = "task-test"

    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    batch_num = args.batch_num
    tplflow_str = args.tplflow_str
    dur = args.dur
    afni_dir = args.afni_dir
    json_dir = args.json_dir
    sess = args.session
    task = args.task
    pat_github_emu = args.pat
    code_dir = args.code_dir

    # set up
    log_dir = os.path.join(code_dir, "logs")
    prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")
    afni_final = os.path.join(proj_dir, "derivatives/afni")
    if not os.path.exists(afni_final):
        os.makedirs(afni_final)

    # get completed logs
    df_log = pd.read_csv(os.path.join(log_dir, "completed_preprocessing.tsv"), sep="\t")

    # make list of subjects who have fmriprep output and are
    # missing afni deconvolutions
    subj_list_all = df_log["subjID"].tolist()
    subj_dict = {}
    for subj in subj_list_all:

        # check for fmriprep output
        print(f"Checking {subj} for previous work ...")
        fmriprep_check = False
        anat_check = glob.glob(
            f"{prep_dir}/{subj}/**/*_{tplflow_str}_desc-preproc_T1w.nii.gz",
            recursive=True,
        )
        func_check = glob.glob(
            f"{prep_dir}/{subj}/**/*{task}*{tplflow_str}_desc-preproc_bold.nii.gz",
            recursive=True,
        )
        if anat_check and func_check:
            fmriprep_check = True

        # determine decon plans
        if json_dir:
            decon_glob = glob.glob(os.path.join(json_dir, f"{subj}*.json"))
            assert decon_glob, f"No JSON found for {subj} in {json_dir}."
            with open(decon_glob[0]) as jf:
                decon_plan = json.load(jf)
        else:
            decon_plan = None

        # Check logs for missing WM-eroded masks, session intersection mask,
        # deconvolution, or run-1 scaled files.
        ind_subj = df_log.index[df_log["subjID"] == subj]
        wme_missing = pd.isnull(df_log.loc[ind_subj, "wme_mask"]).bool()
        intersect_missing = pd.isnull(df_log.loc[ind_subj, f"intersect_{sess}"]).bool()
        decon_missing = pd.isnull(df_log.loc[ind_subj, f"decon_{sess}_1"]).bool()
        scaled_missing = pd.isnull(df_log.loc[ind_subj, f"scaled_{sess}_1"]).bool()

        # Append subj_list if fmriprep data exists and afni data is missing.
        # Note - only add decon to dict, pre-processing is required to create
        # the afni_data object required by control_afni.control_deconvolution.
        if fmriprep_check:
            if intersect_missing or wme_missing or decon_missing or scaled_missing:
                print(f"\tAdding {subj} to working list (subj_dict).")
                subj_dict[subj] = {
                    "Decon": decon_missing,
                    "Decon_plan": decon_plan,
                }

    # kill for no subjects
    if len(subj_dict.keys()) == 0:
        return

    # submit workflow.control_afni for each subject
    current_time = datetime.now()
    slurm_dir = os.path.join(
        afni_dir, f"""slurm_out/afni_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    for subj, value_dict in list(subj_dict.items())[:batch_num]:
        print(f"Submitting job for {subj} {sess} {task}")
        h_out, h_err = submit_jobs(
            afni_dir,
            proj_dir,
            subj,
            sess,
            task,
            code_dir,
            slurm_dir,
            tplflow_str,
            dur,
            value_dict["Decon"],
            value_dict["Decon_plan"],
            pat_github_emu,
        )
        time.sleep(3)
        print(f"submit_jobs out: {h_out} \nsubmit_jobs err: {h_err}")


if __name__ == "__main__":
    main()
