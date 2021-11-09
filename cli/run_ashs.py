#!/bin/env python

# SBATCH --job-name=runAshs
# SBATCH --output=runAshs_log
# SBATCH --time=75:00:00
# SBATCH --ntasks-per-node=1
# SBATCH --mem-per-cpu=4000
# SBATCH --partition=IB_44C_512G
# SBATCH --account=iacc_madlab
# SBATCH --qos=pq_madlab
# SBATCH --nodes=1

"""CLI for runnings project data through ASHS.

References a singularity image of docker://nmuncy/ashs,
this is a required argument.

This will determine which participants do not have
ASHS output in proj_dir/derivatives/ashs/sub..., and
then submit batchs of subjects. The script will wait
for an hour after each batch of submissions, and then
repeat.

Data files are located in dset, /scratch is used as a
working space, and output are written to derivatives.
Waiting each hour is based on number of jobs in squeue,
the job will only continue once the number of new line
characters in squeue falls below 3 (header + this job = 2).

Examples
--------
sbatch run_ashs.py \\
    -s /home/nmuncy/bin/singularities/ashs_latest.simg
"""
# %%
import os
import sys
import fnmatch
import glob
import time
import textwrap
from datetime import datetime
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter


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
    """Title.

    Desc.
    """

    subj_num = subj.split("-")[-1]

    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=p{subj_num}
        #SBATCH --output={slurm_dir}/out_{subj_num}.txt
        #SBATCH --time=01:00:00
        #SBATCH --ntasks-per-node=1
        #SBATCH --mem-per-cpu=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab
        #SBATCH --nodes=1

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
        "-w",
        "--scratch-dir",
        help="/path/to/scratch/dir, default=/scratch/madlab/emu_ashs",
        type=str,
        default="/scratch/madlab/emu_ashs",
    )
    parser.add_argument(
        "-ss",
        "--sess-str",
        help="BIDS session str, used for organizing ASHS output, default=ses-S1",
        type=str,
        default="ses-S1",
    )
    parser.add_argument(
        "-n",
        "--batch-num",
        help="number of subjects to submit at one time, default=8",
        type=int,
        default=8,
    )
    parser.add_argument(
        "-t1",
        "--t1-search",
        help="String to identify T1w files, default=T1w",
        type=str,
        default="T1w",
    )
    parser.add_argument(
        "-t2",
        "--t2-search",
        help="String to identify T2w files, default=PD",
        type=str,
        default="PD",
    )
    parser.add_argument(
        "-a",
        "--atlas-dir",
        help="Absolute path to directory containing ASHS template directory, default=/home/data/madlab/atlases",
        type=str,
        default="/home/data/madlab/atlases",
    )
    parser.add_argument(
        "-as",
        "--atlas-str",
        help="Name of ASHS template directory, default=ashs_atlas_magdeburg",
        type=str,
        default="ashs_atlas_magdeburg",
    )

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-s",
        "--sing-img",
        help="Path to singularity image of docker://nmuncy/ashs.",
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
    # scratch_dir = "/scratch/madlab/emu_ashs"
    # sess = "ses-S1"
    # batch_num = 3
    # t1_search = "T1w"
    # t2_search = "PD"
    # atlas_dir = "/home/data/madlab/atlases"
    # sing_img = "/home/nmuncy/bin/singularities/ashs_latest.simg"
    # atlas_str = "ashs_atlas_magdeburg"

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

    code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dset_dir = os.path.join(proj_dir, "dset")
    deriv_dir = os.path.join(proj_dir, "derivatives/ashs")
    wait_time = 3600

    # submit all subjects to ASHS
    while_count = 0
    work_status = True
    while work_status:

        # check to make sure no jobs are running,
        # account for this job
        sq_check = subprocess.Popen(
            "squeue -u $(whoami)", shell=True, stdout=subprocess.PIPE
        )
        out_lines = sq_check.communicate()[0].decode("utf-8")
        if not out_lines.count("\n") < 3:
            print("Waiting for jobs to finish.")
            time.sleep(wait_time)
            while_count += 1
            continue

        # make dict of dset subjects which have T1- and T2-weighted data
        # and do not have ASHS output
        subj_list_all = [x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")]
        subj_list_all.sort()
        subj_dict = {}
        for subj in subj_list_all:
            ashs_exists = os.path.exists(
                os.path.join(
                    deriv_dir, subj, sess, f"{subj}_left_lfseg_corr_usegray.nii.gz"
                )
            )
            t1_files = glob.glob(
                f"{dset_dir}/{subj}/**/*{t1_search}.nii*", recursive=True
            )
            t2_files = glob.glob(
                f"{dset_dir}/{subj}/**/*{t2_search}.nii*", recursive=True
            )
            if t1_files and t2_files and not ashs_exists:

                # give list item in list for field map correction, multiple acquisitions
                subj_dict[subj] = {}
                subj_dict[subj]["t1-file"] = t1_files[-1].split("/")[-1]
                subj_dict[subj]["t1-dir"] = t1_files[-1].rsplit("/", 1)[0]
                subj_dict[subj]["t2-file"] = t2_files[-1].split("/")[-1]
                subj_dict[subj]["t2-dir"] = t2_files[-1].rsplit("/", 1)[0]

        # kill while loop if all subjects have output, also don't
        # let job run longer than a few days
        if len(subj_dict.keys()) == 0 or while_count > 72:
            work_status = False

        # submit jobs for N subjects that don't have output in deriv_dir
        current_time = datetime.now()
        slurm_dir = os.path.join(
            scratch_dir,
            f"""slurm_out/ashs_{current_time.strftime("%y-%m-%d_%H:%M")}""",
        )
        if not os.path.exists(slurm_dir):
            os.makedirs(slurm_dir)

        for subj in list(subj_dict)[:batch_num]:
            job_out, job_err = submit_jobs(
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

        # pause while loop for an hour
        print(f"Waiting for {wait_time} seconds.")
        time.sleep(wait_time)
        while_count += 1


if __name__ == "__main__":
    main()
