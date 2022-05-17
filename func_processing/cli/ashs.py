#!/usr/bin/env python3

r"""CLI for runnings project data through ASHS.

References a singularity image of docker://nmuncy/ashs,
this is a required argument.

This will determine which participants do not have
ASHS output in proj_dir/derivatives/ashs/sub..., and
then submit batchs of subjects. Data files are located in
dset, /scratch is used as a working space, and output are
written to derivatives.

Example
--------
code_dir=/home/nmuncy/compute/func_processing/func_processing
sbatch --job-name=runAshs \
    --output=${code_dir}/logs/runAshs_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${code_dir}/cli/ashs.py \
    -c $code_dir \
    -s /home/nmuncy/bin/singularities/ashs_latest.simg
"""
# %%
import os
import sys
import glob
import time
import textwrap
from datetime import datetime
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter
import pandas as pd


# %%
def submit_jobs(
    subj,
    subj_dict,
    subj_deriv,
    subj_work,
    atlas_str,
    atlas_dir,
    sing_img,
    slurm_dir,
    code_dir,
):
    """Run workflow.control_ashs for each subject.

    Generate a parent job for each subject (p1234) to
    govern child ashs jobs (ashs1234).

    Parameters
    ----------
    subj : str
        BIDs subject string (sub-1234)
    subj_dict : dict
        {sub-1234:
            {
                t1-file: t1.nii.gz,
                t1-dir: /path/to/anat,
                t2-file: t2.nii.gz,
                t2-dir: /path/to/anat,
            }
        }
    subj_deriv : str
        path to desired output dir
    subj_work : str
        path to ashs working dir
    atlas_str : str
        ASHS atlas dir
    atlas_dir : str
        location of ASHS atlas dir
    sing_img : str
        singularity image of docker://nmuncy/ashs
    slurm_dir : str
        output location for stdout/err
    code_dir : str
        location of this project

    Returns
    -------
    (h_out, h_err) : duple
        stdout, stderr from sbatch subprocess submission of
        subject control script
    """
    subj_num = subj.split("-")[-1]

    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=p{subj_num}
        #SBATCH --output={slurm_dir}/out_{subj_num}.txt
        #SBATCH --time=01:00:00
        #SBATCH --mem=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab

        import sys
        sys.path.append("{code_dir}")
        from workflow import control_ashs

        control_ashs.control_hipseg(
            "{subj_dict[subj]["t1-dir"]}",
            "{subj_dict[subj]["t2-dir"]}",
            "{subj_deriv}",
            "{subj_work}",
            "{atlas_dir}",
            "{sing_img}",
            "{subj}",
            "{subj_dict[subj]["t1-file"]}",
            "{subj_dict[subj]["t2-file"]}",
            "{atlas_str}",
        )
    """
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"ashs_{subj_num}.py")
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
        "-p",
        "--proj-dir",
        default="/home/data/madlab/McMakin_EMUR01",
        help=textwrap.dedent(
            """\
                /path/to/BIDS/project/dir,
                (default : %(default)s)
            """
        ),
        type=str,
    )
    parser.add_argument(
        "-w",
        "--scratch-dir",
        default="/scratch/madlab/McMakin_EMUR01/derivatives/ashs",
        help=textwrap.dedent(
            """\
                /path/to/scratch/dir,
                (default : %(default)s)
            """
        ),
        type=str,
    )
    parser.add_argument(
        "-ss",
        "--sess-str",
        default="ses-S1",
        help=textwrap.dedent(
            """\
                BIDS session str, used for organizing ASHS output,
                (default : %(default)s)
            """
        ),
        type=str,
    )
    parser.add_argument(
        "-n",
        "--batch-num",
        default=8,
        help=textwrap.dedent(
            """\
                number of subjects to submit at one time,
                (default : %(default)s)
            """
        ),
        type=int,
    )
    parser.add_argument(
        "-t1",
        "--t1-search",
        default="T1w",
        help=textwrap.dedent(
            """\
                String to identify T1w files,
                (default : %(default)s)
            """
        ),
        type=str,
    )
    parser.add_argument(
        "-t2",
        "--t2-search",
        default="PD",
        help=textwrap.dedent(
            """\
                String to identify T2w files,
                (default : %(default)s)
            """
        ),
        type=str,
    )
    parser.add_argument(
        "-a",
        "--atlas-dir",
        default="/home/data/madlab/atlases",
        help=textwrap.dedent(
            """\
                Absolute path to directory containing ASHS template directory,
                (default : %(default)s)
            """
        ),
        type=str,
    )
    parser.add_argument(
        "-as",
        "--atlas-str",
        default="ashs_atlas_magdeburg",
        help=textwrap.dedent(
            """\
                Name of ASHS template directory,
                (default : %(default)s)
            """
        ),
        type=str,
    )

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-s",
        "--sing-img",
        help="Path to singularity image of docker://nmuncy/ashs.",
        type=str,
        required=True,
    )
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
    """Schedule ASHS workflow."""
    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    scratch_dir = args.scratch_dir
    sess = args.sess_str
    batch_num = args.batch_num
    t1_search = args.t1_search
    t2_search = args.t2_search
    atlas_dir = args.atlas_dir
    atlas_str = args.atlas_str
    sing_img = args.sing_img
    code_dir = args.code_dir

    # set up
    log_dir = os.path.join(code_dir, "logs")
    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, "derivatives/ashs")

    # get completed logs
    df_log = pd.read_csv(os.path.join(log_dir, "completed_preprocessing.tsv"), sep="\t")

    # make subject dict of those who need ASHS output
    subj_list_all = df_log["subjID"].tolist()
    subj_dict = {}
    for subj in subj_list_all:

        # check log for missing left ASHS
        print(f"Checking {subj} for previous work ...")
        ind_subj = df_log.index[df_log["subjID"] == subj]
        ashs_missing = pd.isnull(df_log.loc[ind_subj, "ashs_L"]).bool()

        # check for T1,2w files
        t1_files = glob.glob(f"{dset_dir}/{subj}/**/*{t1_search}.nii*", recursive=True)
        t2_files = glob.glob(f"{dset_dir}/{subj}/**/*{t2_search}.nii*", recursive=True)
        if t1_files and t2_files and ashs_missing:

            # give list item in list for field map correction, multiple acquisitions
            print(f"\tAdding {subj} to working list (subj_dict).\n")
            subj_dict[subj] = {}
            subj_dict[subj]["t1-file"] = t1_files[-1].split("/")[-1]
            subj_dict[subj]["t1-dir"] = t1_files[-1].rsplit("/", 1)[0]
            subj_dict[subj]["t2-file"] = t2_files[-1].split("/")[-1]
            subj_dict[subj]["t2-dir"] = t2_files[-1].rsplit("/", 1)[0]

    # kill while loop if all subjects have output
    if len(subj_dict.keys()) == 0:
        return

    # submit jobs for N subjects that don't have output in deriv_dir
    current_time = datetime.now()
    slurm_dir = os.path.join(
        scratch_dir,
        f"""slurm_out/ashs_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    for subj in list(subj_dict)[:batch_num]:
        job_out, _ = submit_jobs(
            subj,
            subj_dict,
            os.path.join(deriv_dir, subj, sess),
            os.path.join(scratch_dir, subj, sess),
            atlas_str,
            atlas_dir,
            sing_img,
            slurm_dir,
            code_dir,
        )
        print(job_out)
        time.sleep(3)


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 or emuR01_unc required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
