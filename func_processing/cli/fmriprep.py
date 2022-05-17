#!/usr/bin/env python3

r"""CLI for runnings project data through fMRIprep.

A subject list is created for those who need fMRIprep output.
Then, the workflow for a batch of participants are submitted
to slurm. First FreeSurfer is run on participants, then fMRIprep.

Templateflow directory is updated from one in /home/data/madlab/atlases
to combat the purging in /scratch.

Processing is conducted in /scratch, and then copied out to the main
projects directory.

Example
--------
code_dir=/home/nmuncy/compute/func_processing/func_processing
sbatch --job-name=runPrep \
    --output=${code_dir}/logs/runPrep_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${code_dir}/cli/fmriprep.py \
    -c $code_dir
"""

# %%
import os
import sys
import glob
import fnmatch
import time
import textwrap
from datetime import datetime
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def submit_jobs(
    subj,
    proj_dir,
    scratch_dir,
    sing_img,
    tplflow_dir,
    fs_license,
    slurm_dir,
    code_dir,
):
    """Schedule workflow jobs with slurm.

    Parameters
    ----------
    subj : str
        BIDS subject string
    proj_dir : str
        Path to BIDS project directory
    scratch_dir : str
        Path to working/scratch directory
    sing_img : str
        Path to fmriprep singularity iamge
    tplflow_dir : str
        Path to templateflow directory
    fs_license : str
        Path to FreeSurfer license
    slurm_dir : str
        path to location for capturing sbatch stdout/err
    code_dir : str
        path to clone of github.com/emu-project/func_processing.git

    Returns
    -------
    tuple
        stdout, stderr
    """
    # generate workflow script
    subj_num = subj.split("-")[-1]
    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=p{subj_num}
        #SBATCH --output={slurm_dir}/out_{subj_num}.txt
        #SBATCH --time=20:00:00
        #SBATCH --mem=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab

        import sys
        import os
        import subprocess
        import shutil
        sys.path.append("{code_dir}")
        from workflow import control_fmriprep

        path_dict = control_fmriprep.control_fmriprep(
            "{subj}",
            "{proj_dir}",
            "{scratch_dir}",
            "{sing_img}",
            "{tplflow_dir}",
            "{fs_license}",
        )

        # copy freesurfer data to project directory
        subj_fsurf = os.path.join(path_dict["scratch-fsurf"], "{subj}")
        h_cmd = f"cp -r {{subj_fsurf}} {{path_dict['proj-deriv']}}/freesurfer"
        h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
        h_cp.communicate()

        # copy fmriprep data to project directory
        subj_fprep = os.path.join(path_dict["scratch-fprep"], "{subj}")
        h_cmd = f"cp -r {{subj_fprep}}* {{path_dict['proj-deriv']}}/fmriprep"
        h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
        h_cp.communicate()

        # turn out the lights
        shutil.rmtree(subj_fsurf)
        shutil.rmtree(subj_fprep)
        shutil.rmtree(path_dict["scratch-work"])
    """

    # write script for review
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"fmriprep_{subj_num}.py")
    with open(py_script, "w") as h_script:
        h_script.write(cmd_dedent)

    # execute script
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
            Path to BIDS project directory
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--sing-img",
        type=str,
        default="/home/data/madlab/singularity-images/nipreps_fmriprep_20.2.3.sif",
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
        default="/scratch/madlab/templateflow2",
        help=textwrap.dedent(
            """\
            Location of templateflow directory
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--scratch-dir",
        type=str,
        default="/scratch/madlab/McMakin_EMUR01",
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
        default="/scratch/madlab/license.txt",
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
        help="Path to func_procesing package of github.com/emu-project/func_processing.git",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Schedule fMRIprep workflow."""
    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    scratch_dir = args.scratch_dir
    sing_img = args.sing_img
    tplflow_dir = args.tplflow_dir
    fs_license = args.fs_license
    batch_num = args.batch_num
    code_dir = args.code_dir

    # set up - get subject lists and make scratch dirs
    dset_dir = os.path.join(proj_dir, "dset")
    subj_list_all = [x for x in os.listdir(dset_dir) if fnmatch.fnmatch(x, "sub-*")]
    subj_list_all.sort()

    scratch_deriv = os.path.join(scratch_dir, "derivatives")
    scratch_dset = os.path.join(scratch_dir, "dset")
    for h_dir in [scratch_deriv, scratch_dset]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # patch - combat /scratch purge by updating templateflow dir
    print(f"\nCombating /scratch purge of {tplflow_dir} ...\n")
    h_cmd = f"cp -r /home/data/madlab/atlases/templateflow/* {tplflow_dir}/"
    h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
    h_cp.communicate()

    # make subject dict of those who need fMRIprep output
    subj_list = []
    for subj in subj_list_all:

        # check for missing fMRIprep output
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
        print("No subjects needing fMRIprep detected, exiting.")
        return
    print(f"Submitting jobs for:\n\t {' '.join(subj_list)}\n")

    # submit jobs for N subjects that don't have output in deriv_dir
    current_time = datetime.now()
    slurm_dir = os.path.join(
        scratch_dir,
        f"""slurm_out/fmriprep_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    for subj in subj_list[:batch_num]:
        job_out, _ = submit_jobs(
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
