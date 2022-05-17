#!/usr/bin/env python

"""Make required JSON files.

Set up directory for use by cli/afni_task_subj.py
--json-dir option, following format specified in
workflow.control_afni.control_deconvolution.

Example
-------
python tf2_mkJson.py \\
    -s ses-S2 \\
    -w /Users/nmuncy/Projects/func_processing/qc/no_valence \\
    -p /home/nmuncy/compute/Projects/func_processing/qc/no_valence \\
    -n noVal
"""

# %%
import os
import sys
import json
from argparse import ArgumentParser, RawTextHelpFormatter


# %%
def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-s", "--session", help="BIDS session str (ses-S2)", type=str, required=True,
    )
    required_args.add_argument(
        "-w", "--tf-dir", required=True, help="Path to generated timing files dir",
    )
    required_args.add_argument(
        "-n",
        "--decon-name",
        required=True,
        help="Deconvolution name (noVal for decon_<task>_noVal_*)",
    )
    required_args.add_argument(
        "-p",
        "--hpc-path",
        required=True,
        help="Path HPC destination, points to json dir",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():

    # get args
    args = get_args().parse_args()
    work_dir = args.tf_dir
    sess = args.session
    hpc_path = args.hpc_path
    name = args.decon_name

    # determine subjects
    subj_list = os.listdir(work_dir)
    subj_list.sort()

    # make json files as specified by workflow.control_afni.control_deconvolution
    for subj in subj_list:
        file_list = os.listdir(os.path.join(work_dir, subj, sess))
        file_list.sort()
        subj_dict = {name: {}}
        for h_file in file_list:
            beh = h_file.split("_")[-1].split(".")[0]
            subj_dict[name][beh] = os.path.join(hpc_path, subj, sess, h_file)
        with open(os.path.join(work_dir, f"{subj}_{name}.json"), "w") as jf:
            json.dump(subj_dict, jf)


if __name__ == "__main__":
    main()
