#!/usr/bin/env python

"""Title.

Desc.

Notes
-----
Input directory for -j should contain a json for each subject
in study (name format: subj-1234*.json). See
workflow.control_afni.control_deconvolution for guidance
in formatting json file.

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
    -s ses-S2 \\
    -t task-test \\
    -j /home/data/madlab/McMakin_EMUR01/derivatives/afni/decon_plans \\
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
    subj,
    sess,
    task,
    code_dir,
    slurm_dir,
    tplflow_str=None,
    dur=None,
    decon_plan=None,
):
    """Title.

    Desc.
    """

    # Make arguments, account for optional parameters in workflow.control_afni,
    # use conditionals rather than mess with kwargs since I'd still be writing
    # multiple conditionals.
    preproc_options = [prep_dir, afni_dir, subj, sess, task]
    decon_options = [afni_dir, dset_dir, subj, sess, task]
    if tplflow_str:
        preproc_options.append(tplflow_str)
        decon_options.append(tplflow_str)
    if dur:
        decon_options.append(dur)
    if decon_plan:
        decon_options.append(decon_plan)

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
        sys.path.append("{code_dir}")
        from workflow import control_afni

        afni_data = control_afni.control_preproc(
            {", ".join(preproc_options)}
        )

        afni_data = control_afni.control_deconvolution(
            afni_data, {", ".join(decon_options)}
        )

        print(f"Finished with \\n {{afni_data}}")
    """
    cmd_dedent = textwrap.dedent(h_cmd)
    print(h_cmd)
    return
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
        "-p",
        "--proj-dir",
        help="/path/to/BIDS/project/dir, default=/home/data/madlab/McMakin_EMUR01",
        type=str,
        default="/home/data/madlab/McMakin_EMUR01",
    )
    parser.add_argument(
        "-n",
        "--batch-num",
        help="number of subjects to submit at one time, default=8",
        type=int,
        default=8,
    )
    parser.add_argument(
        "-a",
        "--tplflow-str",
        help="template ID string, for finding fMRIprep output in template space, default=space-MNIPediatricAsym_cohort-5_res-2",
        type=str,
        default="space-MNIPediatricAsym_cohort-5_res-2",
    )
    parser.add_argument(
        "-d",
        "--dur",
        help="event duration, for deconvolution modulation [default=2]",
        type=str,
        default="2",
    )
    parser.add_argument(
        "-d",
        "--dur",
        help="event duration, for deconvolution modulation [default=2]",
        type=str,
        default="2",
    )

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-s",
        "--sess-str",
        help="BIDS session str (ses-S1)",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-t",
        "--task-str",
        help="BIDS EPI task str (task-test)",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-j",
        "--decon-dir",
        help="Path to directory containing json decon plans",
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

    # For testing
    proj_dir = "/home/data/madlab/McMakin_EMUR01"
    tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"
    sess = "ses-S2"
    task = "task-test"
    decon_dir = "/home/nmuncy/compute/func_processing/tests/"
    code_dir = "/home/nmuncy/compute/func_processing"
    batch_num = 3
    afni_dir = "/scratch/madlab/emu_test/derivatives/afni"

    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    tplflow_str = args.tplflow_str
    sess = args.sess_str
    task = args.task_str
    decon_dir = args.decon_dir
    code_dir = args.code_dir
    batch_num = args.batch_num

    # set up
    deriv_dir = os.path.join(proj_dir, "derivatives")
    prep_dir = os.path.join(deriv_dir, "fmriprep")
    # afni_dir = "scratch/madlab/emu_test/derivatives/afni"

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
        # missing afni output
        subj_list = []
        decon_dict = {}
        for subj in subj_list_all[1:2]:

            # check for fmriprep output
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
            decon_glob = glob.glob(os.path.join(decon_dir, f"{subj}*.json"))
            assert decon_glob, f"No decon plan found for {subj} in {decon_dir}"
            with open(decon_glob[0]) as jf:
                decon_plan = json.load(jf)
            for decon_str in decon_plan.keys():
                afni_check.append(
                    os.path.exists(
                        os.path.join(
                            afni_dir,
                            subj,
                            sess,
                            f"decon_{task}_{decon_str}_stats_REML+tlrc.HEAD",
                        )
                    )
                )

            # append subj_list if fmriprep data exists and a planned
            # decon is missing
            if anat_check and func_check and False in afni_check:
                subj_list.append(subj)
                decon_dict[subj] = decon_glob[0]

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
            submit_jobs(
                prep_dir,
                afni_dir,
                subj,
                sess,
                task,
                decon_dict[subj],
                tplflow_str,
                code_dir,
                slurm_dir,
            )

        # pause while loop for 12 hours
        print(f"Waiting for {wait_time} seconds.")
        time.sleep(wait_time)
        while_count += 1


if __name__ == "__main__":
    main()
