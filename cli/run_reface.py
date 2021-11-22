#!/usr/bin/env python

"""CLI for running de/refacing of project data.

Submit a batch of subjects for de/refacing.

Examples
--------
sbatch --job-name=runDeface \\
    --output=runDeface_log \\
    --mem-per-cpu=4000 \\
    --partition=IB_44C_512G \\
    --account=iacc_madlab \\
    --qos=pq_madlab \\
    run_reface.py \\
    -c /home/nmuncy/compute/func_processing
"""
# %%
import os
import sys
import fnmatch
import glob
import time
import subprocess
import textwrap
from datetime import datetime
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def submit_jobs(subj, sess, t1_file, proj_dir, method, code_dir, slurm_dir):
    """Submit refacing module.

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
        from resources.afni import process

        process.reface("{subj}", "{sess}", "{t1_file}", "{proj_dir}", "{method}")
    """
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"deface_{subj_num}.py")
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
    # method = "reface"
    # batch_num = 1
    # code_dir = "/home/nmuncy/compute/func_processing"

    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    batch_num = args.batch_num
    method = args.method
    code_dir = args.code_dir

    # set up
    scratch_dir = os.path.join(
        proj_dir.replace("/home/data", "/scratch"), "derivatives", "afni"
    )
    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, f"derivatives/{method}")
    if not os.path.exists(deriv_dir):
        os.makedirs(deriv_dir)

    # make subject dict of those who need defaced output
    subj_list_all = [x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")]
    subj_list_all.sort()
    subj_dict = {}
    for subj in subj_list_all:

        t1_files = sorted(glob.glob(f"{dset_dir}/{subj}/**/*T1w.nii*", recursive=True))
        t1_file = t1_files[-1].split("/")[-1]
        sess = t1_file.split("_")[1]

        deface_exists = os.path.exists(
            os.path.join(
                deriv_dir, subj, sess, t1_file.replace("_T1w", f"_desc-{method}_T1w")
            )
        )

        if t1_files and not deface_exists:
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
        job_out, job_err = submit_jobs(
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
    main()