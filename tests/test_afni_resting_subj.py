#!/usr/bin/env python

"""Test.

Examples
--------
sbatch --job-name=runAfniRest \\
    --output=log_runAfniRest \\
    --mem-per-cpu=4000 \\
    --partition=IB_44C_512G \\
    --account=iacc_madlab \\
    --qos=pq_madlab \\
    test_afni_resting_subj.py \\
        -r
"""


# %%
import os
import sys
import time
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
    do_regress,
    coord_dict,
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
    do_regress : bool
        whether to conduct deconvolution/regression
    coord_dict : dict

    Returns
    -------
    h_out, h_err : str
        stdout, stderr of sbatch submission
    """

    subj_num = subj.split("-")[-1]
    prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")
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

        afni_data = control_afni.control_preproc(
            "{prep_dir}",
            "{afni_dir}",
            "{subj}",
            "{sess}",
            "{task}",
            "{tplflow_str}",
        )
        print(f"afni_data : \\n {{afni_data}}")

        if {do_regress}:
            afni_data = control_afni.control_resting(
                afni_data,
                "{afni_dir}",
                "{subj}",
                "{sess}",
                {coord_dict},
            )
        print(f"Finished {subj}/{sess}/{task} with: \\n {{afni_data}}")

        # # clean up niftis
        # shutil.rmtree(os.path.join("{afni_dir}", "{subj}", "{sess}", "sbatch_out"))
        # clean_dir = os.path.join("{afni_dir}", "{subj}", "{sess}")
        # clean_list = [
        #     "preproc_bold",
        #     "smoothed_bold",
        #     "nuissance_bold",
        #     "probseg",
        #     "preproc_T1w",
        #     "minval_mask",
        #     "GMe_mask",
        #     "meanTS_bold",
        #     "sdTS_bold",
        #     "blurWM_bold",
        #     "combWM_bold",
        #     "masked_bold",
        # ]
        # for c_str in clean_list:
        #     for h_file in glob.glob(f"{{clean_dir}}/**/*{{c_str}}.nii.gz", recursive=True):
        #         os.remove(h_file)

        # # clean up other, based on extension
        # clean_list = [
        #     "unit_tlrc.HEAD",
        #     "unit_tlrc.BRIK",
        #     "1D00.1D",
        #     "1D01.1D",
        #     "1D02.1D",
        #     "1D_eig.1D",
        #     "1D_vec.1D",
        #     "csfPC_timeseries.1D",
        #     "tmp-censor_timeseries.1D",
        # ]
        # for c_str in clean_list:
        #     for h_file in glob.glob(f"{{clean_dir}}/**/*{{c_str}}", recursive=True):
        #         os.remove(h_file)

        # # copy important files to /home/data
        # h_cmd = f"cp -r {afni_dir}/{subj} {afni_final}"
        # h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
        # h_job = h_cp.communicate()

        # # turn out the lights
        # shutil.rmtree(os.path.join("{afni_dir}", "{subj}"))
    """

    # write script for review, run it
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"preproc_regress_{subj_num}.py")
    with open(py_script, "w") as ps:
        ps.write(cmd_dedent)
    sbatch_response = subprocess.Popen(
        f"sbatch {py_script}", shell=True, stdout=subprocess.PIPE
    )
    h_out, h_err = sbatch_response.communicate()
    return (h_out, h_err)


def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-r",
        "--run",
        action="store_true",
        required=True,
        help="Whether to run code or print help",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():

    # For testing
    proj_dir = "/home/data/madlab/McMakin_EMUR01"
    batch_num = 1
    tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"
    afni_dir = "/scratch/madlab/McMakin_EMUR01/derivatives/afni"
    sess = "ses-S2"
    task = "task-rest"
    code_dir = "/home/nmuncy/compute/func_processing"

    # get args
    args = get_args().parse_args()
    if not args.run:
        sys.exit()

    # set up
    coord_dict = {"rPCC": "5 -55 25"}
    afni_final = os.path.join(proj_dir, "derivatives/afni")
    if not os.path.exists(afni_final):
        os.makedirs(afni_final)

    # make list of subjects who have fmriprep output and are
    # missing afni deconvolutions
    subj_dict = {"sub-4146": {"Regress": True}}

    # submit workflow.control_afni for each subject
    current_time = datetime.now()
    slurm_dir = os.path.join(
        afni_dir,
        f"""slurm_out/afni_{current_time.strftime("%y-%m-%d_%H:%M")}""",
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
            value_dict["Regress"],
            coord_dict,
        )
        time.sleep(3)
        print(f"submit_jobs out: {h_out} \nsubmit_jobs err: {h_err}")


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 or emuR01_unc required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
