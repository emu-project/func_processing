#!/usr/bin/env python

"""Title.

Final output is:
    <proj_dir>/derivatives/afni/analyses/FINAL_<behA>-<behB>_*

Examples
--------
code_dir="$(dirname "$(pwd)")"
sbatch --job-name=runTaskGroup \\
    --output=${code_dir}/logs/runAfniTaskGroup_log \\
    --mem-per-cpu=4000 \\
    --partition=IB_44C_512G \\
    --account=iacc_madlab \\
    --qos=pq_madlab \\
    afni_task_group.py \\
    -c $code_dir \\
    -s ses-S1 \\
    -t task-study \\
    -d decon_task-study_UniqueBehs_stats_REML+tlrc \\
    -b neg neu
"""

# %%
import os
import sys
from datetime import datetime
import pandas as pd
import textwrap
import glob
import subprocess
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def submit_jobs(
    beh_list, task, sess, afni_dir, group_dir, group_data, slurm_dir, code_dir
):
    """Schedule workflow for group analyses.

    Parameters
    ----------


    Returns
    -------
    h_out, h_err : str
        stdout, stderr of sbatch submission
    """

    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=taskGroup
        #SBATCH --output={slurm_dir}/out_taskGroup.txt
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
        beh_list = {beh_list}
        group_data = control_afni.control_task_group(
            beh_list,
            "{task}",
            "{sess}",
            "{afni_dir}",
            "{group_dir}",
            group_data,
        )
        print(f"Job finished with group_data : \\n{{group_data}}")
    """

    # write script for review, run it
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, "Task_behAB_group.py")
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

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-c",
        "--code-dir",
        required=True,
        help="Path to clone of github.com/emu-project/func_processing.git",
    )
    required_args.add_argument(
        "-s", "--session", required=True, help="BIDS session (ses-S1)",
    )
    required_args.add_argument(
        "-t", "--task", required=True, help="BIDS task (task-study)",
    )
    required_args.add_argument(
        "-d",
        "--dcn-str",
        required=True,
        help="Decon string (decon_task-study_UniqueBehs_stats_REML+tlrc)",
    )
    required_args.add_argument(
        "-b",
        "--behaviors",
        nargs=2,
        required=True,
        help=textwrap.dedent(
            """\
            Two behaviors, matching decon sub-brick labels
            e.g. neg neu for neg#0_Coef, neu#0_Coef
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

    Find subjects with required output, make a group_data
    dictionary, submit workflow.
    """

    # receive passed args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    atlas_dir = args.atlas_dir
    code_dir = args.code_dir
    task = args.task
    sess = args.session
    decon_str = args.dcn_str
    beh_list = args.behaviors

    # set up
    log_dir = os.path.join(code_dir, "logs")
    afni_dir = os.path.join(proj_dir, "derivatives/afni")
    group_dir = os.path.join(afni_dir, "analyses")
    if not os.path.exists(group_dir):
        os.makedirs(group_dir)

    # get completed logs
    df_log = pd.read_csv(os.path.join(log_dir, "completed_preprocessing.tsv"), sep="\t")
    subj_list_all = df_log["subjID"].tolist()

    # start group_data with template gm mask, decon string
    group_data = {}
    tpl_gm = os.path.join(
        atlas_dir, "tpl-MNIPediatricAsym_cohort-5_res-2_label-GM_probseg.nii.gz"
    )
    assert os.path.exists(tpl_gm), f"Template GM not detected: {tpl_gm}"
    group_data["mask-gm"] = tpl_gm
    group_data["dcn-file"] = decon_str

    # make list of subjs with required data
    subj_list = []
    for subj in subj_list_all:
        print(f"Checking {subj} for required files ...")
        mask_exists = glob.glob(
            f"{afni_dir}/{subj}/**/anat/{subj}_*_{task}_*intersect_mask.nii.gz",
            recursive=True,
        )
        decon_exists = glob.glob(f"{afni_dir}/{subj}/{sess}/func/{decon_str}.HEAD",)
        if mask_exists and decon_exists:
            print(f"\tAdding {subj} to group_data\n")
            subj_list.append(subj)
    assert len(subj_list) > 1, "Insufficient subject data found."
    group_data["subj-list"] = subj_list

    # submit work
    current_time = datetime.now()
    slurm_dir = os.path.join(
        afni_dir, f"""slurm_out/afni_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    print(f"\ngroup_data : \n {group_data}")
    h_out, h_err = submit_jobs(
        beh_list, task, sess, afni_dir, group_dir, group_data, slurm_dir, code_dir
    )


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 or emuR01_unc required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
