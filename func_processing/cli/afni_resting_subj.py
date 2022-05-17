#!/usr/bin/env python3

r"""Pre-process and regress resting fMRIprep output.

Incorpoarte fMRIprep output into an AFNI workflow, finish
pre-processing and project regression matrix. Default uses
anaticor method for projection, but "original" method is
supported (see resources.afni.deconvolve.regress_resting).

Based on example 11 of afni_proc.py and s17.proc.FT.rest.11
of afni_data6. Submits batches of size N for processing, according to
user input and based on which subejcts do not have output in
logs/completed_preprocessing.tsv (see cli/run_checks.py).

Final regression matrix is:
    <proj_dir>/derivatives/afni/<subj>/ses-S2/func/decon_task-rest_<anaticor>+tlrc.
SNR, GCor, noise estimations (3dFWHMx) and other metrics also generated.

Seed-based regression matrix is:
    decon_task-rest_<anaticor>_<seed>_ztrans+tlrc.

Example
--------
code_dir=/home/nmuncy/compute/func_processing/func_processing
sbatch --job-name=runAfniRest \
    --output=${code_dir}/logs/runAfniRest_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${code_dir}/cli/afni_resting_subj.py \
    -c $code_dir \
    -j ${code_dir}/examples/rs_seed.json
"""


# %%
import os
import sys
import glob
import time
import json
from datetime import datetime
import textwrap
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter
import pandas as pd


# %%
def submit_jobs(
    afni_dir,
    afni_final,
    code_dir,
    coord_dict,
    do_blur,
    do_regress,
    kp_interm,
    proj_dir,
    sess,
    slurm_dir,
    subj,
    task,
    tplflow_str,
):
    """Schedule work for single participant.

    Submit workflow.control_afni for a single subject, session,
    and task. Take data from fMRIprep output through deconvolution.
    Finally, clean up, and move relevant files to <afni_final>.

    Parameters
    ----------
    afni_dir : str
        path to /scratch directory, for intermediates
    afni_final : str
        path to desired output location of final files
    code_dir : str
        path to clone of github.com/emu-project/func_processing.git
    coord_dict : dict
        seed name and coordinates
    do_blur : bool
        [T/F] whether to blur as part of pre-processing
    do_regress : bool
        whether to conduct deconvolution/regression
    kp_interm : bool
        [T/F] whether to keep (T) or remove (F) intemediates
    proj_dir : str
        path to BIDS-formatted project directory
    sess : str
        BIDS session string
    slurm_dir : str
        path to location for capturing sbatch stdout/err
    subj : str
        BIDS subject string
    task : str
        BIDS task string
    tplflow_str : str
        template_flow identifier string

    Returns
    -------
    h_out, h_err : str
        stdout, stderr of sbatch submission
    """
    subj_num = subj.split("-")[-1]
    prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")

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
            {do_blur},
        )
        print(f"afni_data : \\n {{afni_data}}")

        if {do_regress}:
            afni_data = control_afni.control_resting(
                afni_data,
                "{afni_dir}",
                "{subj}",
                "{sess}",
                {coord_dict},
                {kp_interm},
            )
        print(f"Finished {subj}/{sess}/{task} with: \\n {{afni_data}}")

        # clean up
        if not {kp_interm}:
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
                "meanTS_bold",
                "sdTS_bold",
                "blurWM_bold",
                "combWM_bold",
                "masked_bold",
            ]
            for c_str in clean_list:
                for h_file in glob.glob(f"{{clean_dir}}/**/*{{c_str}}.nii.gz", recursive=True):
                    os.remove(h_file)

            # clean up other, based on extension
            clean_list = [
                "unit+tlrc.HEAD",
                "unit+tlrc.BRIK",
                "corr+tlrc.HEAD",
                "corr+tlrc.BRIK",
                "1D00.1D",
                "1D01.1D",
                "1D02.1D",
                "1D_eig.1D",
                "1D_vec.1D",
                "csfPC_timeseries.1D",
                "tmp-censor_timeseries.1D",
            ]
            for c_str in clean_list:
                for h_file in glob.glob(f"{{clean_dir}}/**/*{{c_str}}", recursive=True):
                    os.remove(h_file)

        # copy important files to /home/data
        h_cmd = f"cp -r {afni_dir}/{subj} {afni_final}"
        h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
        h_job = h_cp.communicate()

        # turn out the lights
        shutil.rmtree(os.path.join("{afni_dir}", "{subj}"))
    """

    # write script for review, run it
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"preproc_regress_{subj_num}.py")
    with open(py_script, "w") as h_script:
        h_script.write(cmd_dedent)
    sbatch_response = subprocess.Popen(
        f"sbatch {py_script}", shell=True, stdout=subprocess.PIPE
    )
    h_out, h_err = sbatch_response.communicate()
    return (h_out, h_err)


# %%
def get_args():
    """Get and parse arguments."""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)

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
        "--blur",
        action="store_true",
        help=textwrap.dedent(
            """\
            Toggle of whether to use blurring option in pre-processing.
            Boolean (True if "--blur", else False).
            """
        ),
    )
    parser.add_argument(
        "--keep-interm",
        action="store_true",
        help=textwrap.dedent(
            """\
            Toggle of whether to remove intermediates.
            Boolean (True if "--keep-interm", else False).
            """
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help=textwrap.dedent(
            """\
            Path to desired output directory for final AFNI files. If
            [None], output location will be <proj_dir>/derivatives/afni.
            (default : %(default)s)
            """
        ),
    )
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
        "--session",
        type=str,
        default="ses-S2",
        help=textwrap.dedent(
            """\
            BIDS session str
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--task",
        type=str,
        default="task-rest",
        help=textwrap.dedent(
            """\
            BIDS EPI task str
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

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-c",
        "--code-dir",
        required=True,
        type=str,
        help="Path to func_procesing package of github.com/emu-project/func_processing.git",
    )
    required_args.add_argument(
        "-j",
        "--coord-json",
        required=True,
        type=str,
        help=textwrap.dedent(
            """\
            Path to json file containing name, MNI coordinates of desired seeds.
            JSON format example: {"rPCC": "5 -55 25"}
        """
        ),
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Set up for workflow.

    Find subjects without resting state output, schedule
    job for them.
    """
    # receive passed args
    args = get_args().parse_args()
    afni_dir = args.afni_dir
    batch_num = args.batch_num
    do_blur = args.blur
    code_dir = args.code_dir
    coord_json = args.coord_json
    kp_interm = args.keep_interm
    out_dir = args.out_dir
    proj_dir = args.proj_dir
    sess = args.session
    task = args.task
    tplflow_str = args.tplflow_str

    # set up
    log_dir = os.path.join(code_dir, "logs")
    prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")
    afni_final = out_dir if out_dir else os.path.join(proj_dir, "derivatives/afni")
    if not os.path.exists(afni_final):
        os.makedirs(afni_final)
    with open(coord_json) as json_file:
        coord_dict = json.load(json_file)

    # get completed logs
    df_log = pd.read_csv(os.path.join(log_dir, "completed_preprocessing.tsv"), sep="\t")

    # make list of subjects who have fmriprep output and are
    # missing afni deconvolutions
    subj_list_all = df_log["subjID"].tolist()
    subj_dict = {}
    for subj in subj_list_all:

        # check for required fmriprep output
        print(f"Checking {subj} for previous work ...")
        anat_check = glob.glob(
            f"{prep_dir}/{subj}/**/*_{tplflow_str}_desc-preproc_T1w.nii.gz",
            recursive=True,
        )
        func_check = glob.glob(
            f"{prep_dir}/{subj}/**/*{task}*{tplflow_str}_desc-preproc_bold.nii.gz",
            recursive=True,
        )
        if not anat_check or not func_check:
            continue

        # Check for missing certain pre-processing files, account for
        # user specified output location
        if out_dir:
            subj_dir = os.path.join(afni_final, subj, sess)
            wme_found = glob.glob(f"{subj_dir}/anat/*desc-WMe_mask.nii.gz")
            intx_found = glob.glob(
                f"{subj_dir}/anat/*{sess}_{task}*desc-intersect_mask.nii.gz"
            )
            scaled_found = glob.glob(
                f"{subj_dir}/func/*{sess}_{task}_run-1*desc-scaled_bold.nii.gz"
            )
            regress_found = glob.glob(f"{subj_dir}/func/X.decon_{task}.xmat.1D")

            # invert bool to match with existing structure
            wme_missing = False if wme_found else True
            intersect_missing = False if intx_found else True
            scaled_missing = False if scaled_found else True
            regress_missing = False if regress_found else True
        else:
            ind_subj = df_log.index[df_log["subjID"] == subj]
            wme_missing = pd.isnull(df_log.loc[ind_subj, "wme_mask"]).bool()
            intersect_missing = pd.isnull(
                df_log.loc[ind_subj, f"intersect_{sess}_{task}"]
            ).bool()
            regress_missing = pd.isnull(df_log.loc[ind_subj, "decon_resting"]).bool()
            scaled_missing = pd.isnull(df_log.loc[ind_subj, "scaled_resting"]).bool()

        # Append subj_list if fmriprep data exists and afni data is missing.
        if intersect_missing or wme_missing or regress_missing or scaled_missing:
            print(f"\tAdding {subj} to working list (subj_dict).\n")
            subj_dict[subj] = {"Regress": regress_missing}

    # kill for no subjects
    if len(subj_dict.keys()) == 0:
        return

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
        do_regress = value_dict["Regress"]
        h_out, h_err = submit_jobs(
            afni_dir,
            afni_final,
            code_dir,
            coord_dict,
            do_blur,
            do_regress,
            kp_interm,
            proj_dir,
            sess,
            slurm_dir,
            subj,
            task,
            tplflow_str,
        )
        time.sleep(3)
        print(f"submit_jobs out: {h_out} \nsubmit_jobs err: {h_err}")


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
