#!/usr/bin/env python3

r"""CLI for running de/refacing of project data.

Submit a batch of subjects for de/refacing.

Examples
--------
code_dir=/home/nmuncy/compute/func_processing/func_processing
sbatch --job-name=runReface \
    --output=${code_dir}/logs/runReface_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${code_dir}/cli/reface.py \
    -c $code_dir
"""


# %%
import os
import sys
import glob
import time
import subprocess
import textwrap
from datetime import datetime
from argparse import ArgumentParser, RawTextHelpFormatter
import pandas as pd


# %%
def submit_jobs(subj, sess, t1_file, proj_dir, method, code_dir, slurm_dir):
    """Submit refacing workflow.

    Also writes a python script to slurm_dir for review.

    Parameters
    ----------
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-A)
    t1_file : str
        file name of T1w file (sub-1234_ses-A_T1w.nii.gz)
    proj_dir : str
        BIDS project directory (/path/to/proj)
    method : str
        refacing method (reface, deface, reface_plus)
    code_dir : str
        path to clone of github.com/emu-project/func_processing.git
    slurm_dir : str
        path to location for capturing sbatch stdout/err

    Returns
    -------
    h_out, h_err : str
        stdout, stderr of sbatch submission
    """
    subj_num = subj.split("-")[-1]

    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=d{subj_num}
        #SBATCH --output={slurm_dir}/out_{subj_num}.txt
        #SBATCH --time=01:00:00
        #SBATCH --mem=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab

        import sys
        sys.path.append("{code_dir}")
        from workflow import control_reface

        msg_out = control_reface.control_reface(
            "{subj}",
            "{sess}",
            "{t1_file}",
            "{proj_dir}",
            "{method}",
        )
        print(msg_out)
    """
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"reface_{subj_num}.py")
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
        "--method",
        type=str,
        default="reface",
        help=textwrap.dedent(
            """\
            method of refacing, accepts "deface",
            "reface", or "reface_plus"
            (default : %(default)s)
        """
        ),
    )

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-c",
        "--code-dir",
        required=True,
        help="Path to func_procesing package of github.com/emu-project/func_processing.git",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Schedule reface workflow."""
    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    batch_num = args.batch_num
    method = args.method
    code_dir = args.code_dir

    # set up
    log_dir = os.path.join(code_dir, "logs")
    scratch_dir = os.path.join(
        proj_dir.replace("/home/data", "/scratch"), "derivatives", "afni"
    )
    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, f"derivatives/{method}")
    if not os.path.exists(deriv_dir):
        os.makedirs(deriv_dir)

    # get completed logs
    df_log = pd.read_csv(os.path.join(log_dir, "completed_preprocessing.tsv"), sep="\t")

    # make subject dict of those who need defaced output
    subj_list_all = df_log["subjID"].tolist()
    subj_dict = {}
    for subj in subj_list_all:

        # check for t1 file
        print(f"Checking {subj} for previous work ...")
        t1_files = sorted(glob.glob(f"{dset_dir}/{subj}/**/*T1w.nii*", recursive=True))
        t1_file = t1_files[-1].split("/")[-1]
        sess = t1_file.split("_")[1]

        # check log for missing re/deface
        ind_subj = df_log.index[df_log["subjID"] == subj]
        reface_missing = pd.isnull(df_log.loc[ind_subj, "reface"]).bool()

        if t1_files and reface_missing:
            print(f"\tAdding {subj} to working list (subj_dict).\n")
            subj_dict[subj] = {}
            subj_dict[subj]["sess"] = sess
            subj_dict[subj]["anat"] = t1_file

    # kill while loop if all subjects have output
    if len(subj_dict.keys()) == 0:
        return

    # submit jobs for N subjects that don't have output in deriv_dir
    current_time = datetime.now()
    slurm_dir = os.path.join(
        scratch_dir,
        f"""slurm_out/reface_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    for subj in list(subj_dict)[:batch_num]:
        job_out, _ = submit_jobs(
            subj,
            subj_dict[subj]["sess"],
            subj_dict[subj]["anat"],
            proj_dir,
            method,
            code_dir,
            slurm_dir,
        )
        print(f"{method} {subj} with job: {job_out}")
        time.sleep(3)


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
