#!/usr/bin/env python3

r"""Conduct group-level analyses on resting state data.

Construct a group intersection gray matter mask in template space,
and then run an A vs not-A analysis via ETAC on seed-based
correlation matrices.

More advanced group testing to be added in the future.

Final output is:
    <proj_dir>/derivatives/afni/analyses/FINAL_RS-<seed>*

Example
--------
code_dir=/home/nmuncy/compute/func_processing/func_processing
sbatch --job-name=runRSGroup \
    --output=${code_dir}/logs/runAfniRestGroup_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${code_dir}/cli/afni_resting_group.py \
    -c $code_dir \
    -s rPCC
"""

# %%
import os
import sys
from datetime import datetime
import textwrap
import glob
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter
import pandas as pd


# %%
def submit_jobs(
    seed, task, afni_dir, group_dir, group_data, slurm_dir, code_dir, do_blur
):
    """Schedule workflow for group analyses.

    Parameters
    ----------
    seed : str
        seed identifier from run_afni_resting.py,
        'rPCC' for decon_task-rest_rPCC_ztrans+tlrc
    task : str
        BIDS task string (task-rest)
    afni_dir : str
        location of project afni derivatives
    group_dir : str
        output location of work
    group_data : dict
        dictionary of files, paths
    slurm_dir : str
        output location for sbatch stdout/err
    code_dir : str
        path to clone of github.com/emu-project/func_processing.git
    do_blur : bool
        [T/F] whether blur was done in pre-processing

    Returns
    -------
    h_out, h_err : str
        stdout, stderr of sbatch submission
    """
    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=rsGroup
        #SBATCH --output={slurm_dir}/out_rsGroup.txt
        #SBATCH --time=10:00:00
        #SBATCH --mem=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab

        import os
        import sys
        sys.path.append("{code_dir}")
        from workflow import control_afni

        group_data = {group_data}
        group_data = control_afni.control_resting_group(
            "{seed}",
            "{task}",
            "{afni_dir}",
            "{group_dir}",
            group_data,
            {do_blur},
        )
        print(f"Job finished with group_data : \\n{{group_data}}")
    """

    # write script for review, run it
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"RS_{seed}_group.py")
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
        "--atlas-dir",
        type=str,
        default="/home/data/madlab/atlases/templateflow/tpl-MNIPediatricAsym/cohort-5",
        help=textwrap.dedent(
            """\
            Path to location of atlas GM mask
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
        "--blur",
        action="store_true",
        help=textwrap.dedent(
            """\
            Toggle of whether blurring was used in pre-processing.
            Boolean (True if "--blur", else False).
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
    required_args.add_argument(
        "-s",
        "--seed",
        required=True,
        help="Seed name, e.g. 'rPCC' for decon_task-rest_anaticor_rPCC_ztrans+tlrc",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Set up for workflow.

    Find subjects with required output, make a group_data
    dictionary, submit workflow.
    """
    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    atlas_dir = args.atlas_dir
    task = args.task
    seed = args.seed
    code_dir = args.code_dir
    do_blur = args.blur

    # set up
    log_dir = os.path.join(code_dir, "logs")
    afni_dir = os.path.join(proj_dir, "derivatives/afni")
    group_dir = os.path.join(afni_dir, "analyses")
    if not os.path.exists(group_dir):
        os.makedirs(group_dir)

    # get completed logs
    df_log = pd.read_csv(os.path.join(log_dir, "completed_preprocessing.tsv"), sep="\t")
    subj_list_all = df_log["subjID"].tolist()

    # start group_data with template gm mask
    group_data = {}
    tpl_gm = os.path.join(
        atlas_dir, "tpl-MNIPediatricAsym_cohort-5_res-2_label-GM_probseg.nii.gz"
    )
    assert os.path.exists(tpl_gm), f"Template GM not detected: {tpl_gm}"
    group_data["mask-gm"] = tpl_gm

    # make list of subjs with required data
    subj_list = []
    ztrans_list = []
    for subj in subj_list_all:
        print(f"Checking {subj} for required files ...")
        mask_exists = glob.glob(
            f"{afni_dir}/{subj}/**/anat/{subj}_*_{task}_*intersect_mask.nii.gz",
            recursive=True,
        )
        ztrans_exists = glob.glob(
            f"{afni_dir}/{subj}/**/func/decon_{task}_anaticor_{seed}_ztrans+tlrc.HEAD",
            recursive=True,
        )
        if mask_exists and ztrans_exists:
            print(f"\tAdding {subj} to group_data\n")
            subj_list.append(subj)
            ztrans_list.append(ztrans_exists[0].split(".")[0])
    assert len(subj_list) > 1, "Insufficient subject data found."
    group_data["subj-list"] = subj_list
    group_data["all-ztrans"] = ztrans_list

    # submit work
    current_time = datetime.now()
    slurm_dir = os.path.join(
        afni_dir,
        f"""slurm_out/afni_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    print(f"\ngroup_data : \n {group_data}")
    _, _ = submit_jobs(
        seed, task, afni_dir, group_dir, group_data, slurm_dir, code_dir, do_blur
    )


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
