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
    --time=00:10:00 \\
    --mem-per-cpu=4000 \\
    --partition=IB_44C_512G \\
    --account=iacc_madlab \\
    --qos=pq_madlab \\
    run_afni.py \\
    -s ses-S1 \\
    -t task-study \\
    -c /home/nmuncy/compute/func_processing
"""
# %%
import os
import sys
import json
import fnmatch
import time
import glob
from datetime import datetime
import textwrap
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def submit_jobs(
    prep_dir,
    dset_dir,
    afni_dir,
    afni_final,
    subj,
    sess,
    task,
    code_dir,
    slurm_dir,
    tplflow_str,
    dur,
    decon_plan,
):
    """Schedule work for single participant.

    Submit workflow.control_afni for a single subject, session,
    and task. Take data from fMRIprep output through deconvolution.
    Finally, clean up, and move relevant files to <afni_final>.

    Parameters
    ----------
    prep_dir : str
        path to project derivatives/fmriprep
    dset_dir : str
        path to project dset
    afni_dir : str
        path to /scratch directory, for intermediates
    afni_final : str
        path to project derivatives/afni
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
    decon_plan : dict/None
        planned deconvolution with behavior: timing file mappings

    Returns
    -------
    h_out, h_err : str
        stdout, stderr of sbatch submission
    """

    subj_num = subj.split("-")[-1]

    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=p{subj_num}
        #SBATCH --output={slurm_dir}/out_{subj_num}.txt
        #SBATCH --time=10:00:00
        #SBATCH --mem=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab

        import sys
        import shutil
        import glob
        sys.path.append("{code_dir}")
        from workflow import control_afni

        afni_data = control_afni.control_preproc(
            "{prep_dir}",
            "{afni_dir}",
            "{subj}",
            "{sess}",
            "{task}",
            "{tplflow_str}",
        )

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
        print(f"Finished {{subj}} {{sess}} {{task}} with: \\n {{afni_data}}")

        # clean up
        shutil.rmtree(os.path.join("{afni_dir}", "sbatch_out"))
        clean_dir = os.path.join("{afni_dir}", "{subj}", "{sess}", "func")
        clean_list = ["preproc", "smoothed"]
        for c_str in clean_list:
            for h_file in glob.glob(f"{{clean_dir}}/*{{c_str}}_bold.nii.gz"):
                os.remove(h_file)

        # copy important files to /home/data
        src = os.path.join("{afni_dir}", "{subj}")
        dst = os.path.join("{afni_final}", "{subj}")
        shutil.copytree(src, dst)

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
        "-s",
        "--session",
        help="BIDS session str (ses-S2)",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-t",
        "--task",
        help="BIDS EPI task str (task-test)",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-c",
        "--code-dir",
        help="Path to clone of github.com/emu-project/func_processing.git",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():

    # # For testing
    # proj_dir = "/home/data/madlab/McMakin_EMUR01"
    # batch_num = 1
    # tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"
    # dur = 2
    # afni_dir = "/scratch/madlab/McMain_EMUR01/derivatives/afni"
    # json_dir = None
    # sess = "ses-S1"
    # task = "task-study"
    # code_dir = "/home/nmuncy/compute/func_processing"

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
    code_dir = args.code_dir

    # set up
    dset_dir = os.path.join(proj_dir, "dset")
    prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")
    afni_final = os.path.join(proj_dir, "derivatives/afni")
    if not os.path.exists(afni_final):
        os.makedirs(afni_final)

    # wait 12H between submission attempts
    wait_time = 43200

    # submit all subjects to AFNI
    while_count = 0
    work_status = True
    while work_status:

        # see if jobs are still running, wait another 12 hours if so
        sq_check = subprocess.Popen(
            "squeue -u $(whoami)", shell=True, stdout=subprocess.PIPE
        )
        out_lines = sq_check.communicate()[0].decode("utf-8")
        if not out_lines.count("\n") < 3:
            print("Waiting for jobs to finish.")
            time.sleep(wait_time)
            while_count += 1
            continue

        # list subjects in fmriprep dir
        subj_list_all = [
            x
            for x in os.listdir(prep_dir)
            if fnmatch.fnmatch(x, "sub-*") and not fnmatch.fnmatch(x, "*html")
        ]
        subj_list_all.sort()

        # make list of subjects who have fmriprep output and are
        # missing afni deconvolutions
        subj_list = []
        for subj in subj_list_all:

            # check for fmriprep output
            print(f"Checking {subj} for previous work ...")
            anat_check = glob.glob(
                f"{prep_dir}/{subj}/**/*_{tplflow_str}_desc-preproc_T1w.nii.gz",
                recursive=True,
            )
            func_check = glob.glob(
                f"{prep_dir}/{subj}/**/*{task}*{tplflow_str}_desc-preproc_bold.nii.gz",
                recursive=True,
            )

            # check whether each planned decon exists
            afni_check = []
            if json_dir:
                decon_glob = glob.glob(os.path.join(json_dir, f"{subj}*.json"))
                assert decon_glob, f"No JSON found for {subj} in {json_dir}."
                with open(decon_glob[0]) as jf:
                    decon_plan = json.load(jf)
                for decon_str in decon_plan.keys():
                    afni_check.append(
                        os.path.exists(
                            os.path.join(
                                afni_final,
                                subj,
                                sess,
                                "func",
                                f"decon_{task}_{decon_str}_stats_REML+tlrc.HEAD",
                            )
                        )
                    )
            else:
                decon_plan = None
                afni_check.append(
                    os.path.exists(
                        os.path.join(
                            afni_final,
                            subj,
                            sess,
                            "func",
                            f"decon_{task}_UniqueBehs_stats_REML+tlrc.HEAD",
                        )
                    )
                )

            # append subj_list if fmriprep data exists and a planned
            # decon is missing
            if anat_check and func_check and False in afni_check:
                print(f"Adding {subj} to working list (subj_list).")
                subj_list.append(subj)

        # kill while loop if all subjects have output, also don't
        # let job run longer than a week
        if len(subj_list) == 0 or while_count > 14:
            work_status = False

        # do preproc/decon for each subject
        current_time = datetime.now()
        slurm_dir = os.path.join(
            afni_dir,
            f"""slurm_out/afni_{current_time.strftime("%y-%m-%d_%H:%M")}""",
        )
        if not os.path.exists(slurm_dir):
            os.makedirs(slurm_dir)

        for subj in subj_list[:batch_num]:
            print(f"Submitting job for {subj} {sess} {task}")
            h_out, h_err = submit_jobs(
                prep_dir,
                dset_dir,
                afni_dir,
                afni_final,
                subj,
                sess,
                task,
                code_dir,
                slurm_dir,
                tplflow_str,
                dur,
                decon_plan,
            )
            print(f"out: {h_out}, err: {h_err}")

        # pause while loop for 12 hours
        print(f"Waiting for {wait_time} seconds.")
        time.sleep(wait_time)
        while_count += 1


if __name__ == "__main__":
    main()
