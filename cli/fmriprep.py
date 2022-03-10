#!/usr/bin/env python

"""CLI for runnings project data through fMRIprep.

Example
--------
code_dir="$(dirname "$(pwd)")"
sbatch --job-name=runAshs \\
    --output=${code_dir}/logs/runPrep_log \\
    --mem-per-cpu=4000 \\
    --partition=IB_44C_512G \\
    --account=iacc_madlab \\
    --qos=pq_madlab \\
    fmriprep.py \\
    -c $code_dir
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


# %%
def submit_jobs(
    subj, proj_dir, scratch_dir, sing_img, tplflow_dir, fs_license, slurm_dir, code_dir,
):
    """Title.

    Desc.
    """

    # generate workflow script
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
        from workflow import control_fmriprep

        control_fmriprep.control_fmriprep(
            "{subj}",
            "{proj_dir}",
            "{scratch_dir}",
            "{sing_img}",
            "{tplflow_dir}",
            "{fs_license}",
        )
    """

    # write script for review
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"fmriprep_{subj_num}.py")
    with open(py_script, "w") as ps:
        ps.write(cmd_dedent)

    # execute script
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
        "--project-dir",
        type=str,
        default="/scratch/madlab/nate_test",
        help=textwrap.dedent(
            """\
            Path to BIDS project directory
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--sing-img",
        type=str,
        default="/home/nmuncy/bin/singularities/nipreps_fmriprep_20.2.3.simg",
        help=textwrap.dedent(
            """\
            fMRIprep singularity image
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--tplflow-dir",
        type=str,
        default="/home/data/madlab/singularity-images/templateflow",
        help=textwrap.dedent(
            """\
            Location of templateflow directory
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default="/scratch/madlab/nate_test/scratch",
        help=textwrap.dedent(
            """\
            Scratch working directory, for intermediates
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--fs-license",
        type=str,
        default="/home/nmuncy/bin/licenses/fs_license.txt",
        help=textwrap.dedent(
            """\
            FreeSurfer license
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

    required_args = parser.add_argument_group("Required Arguments")
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

    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    scratch_dir = args.work_dir
    sing_img = args.sing_img
    tplflow_dir = args.tplflow_dir
    fs_license = args.fs_license
    batch_num = args.batch_num
    code_dir = args.code_dir

    # set up
    dset_dir = os.path.join(proj_dir, "dset")
    subj_list_all = sorted(glob.glob(f"{dset_dir}/sub-*"))

    # make subject dict of those who need fMRIprep output
    subj_list = []
    for subj in subj_list_all:

        # check log for missing left ASHS
        print(f"Checking {subj} for previous work ...")
        subj_fmriprep = os.path.join(proj_dir, "derivatives/fmriprep", subj)
        t1_exists = glob.glob(
            f"{subj_fmriprep}/**/*desc-preproc_T1w.nii.gz", recursive=True
        )
        if not t1_exists:
            print(f"\tAdding {subj} to working list (subj_list).\n")
            subj_list.append(subj)

    # kill while loop if all subjects have output
    if len(subj_list) == 0:
        return

    # submit jobs for N subjects that don't have output in deriv_dir
    current_time = datetime.now()
    slurm_dir = os.path.join(
        scratch_dir,
        f"""slurm_out/fmriprep_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    for subj in subj_list[:batch_num]:
        job_out, job_err = submit_jobs(
            subj,
            proj_dir,
            scratch_dir,
            sing_img,
            tplflow_dir,
            fs_license,
            slurm_dir,
            code_dir,
        )
        print(job_out)
        time.sleep(3)


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
