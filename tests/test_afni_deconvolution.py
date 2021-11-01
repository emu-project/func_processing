"""

Notes
-----
Requires AFNI and c3d.

Examples
--------
test_afni_deconvolution.py \\

"""
# %%
import os
import sys
import glob
import json
from argparse import ArgumentParser, RawTextHelpFormatter

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.afni import deconvolve


# %%
def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    requiredNamed = parser.add_argument_group("required named arguments")
    requiredNamed.add_argument(
        "-p",
        "--part-id",
        help="Participant ID (sub-1234)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-t",
        "--task-str",
        help="BIDS task-string (task-test)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-s",
        "--sess-str",
        help="BIDS ses-string (ses-S2)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-d",
        "--deriv-dir",
        help="/path/to/project/derivatives",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Move data through AFNI pre-processing."""

    # # For testing
    deriv_dir = "/scratch/madlab/emu_test/derivatives"
    subj = "sub-4002"
    sess = "ses-S2"
    task = "task-test"

    # # get passed arguments
    # args = get_args().parse_args()
    # subj = args.part_id
    # sess = args.sess_str
    # task = args.task_str
    # deriv_dir = args.deriv_dir

    # setup directories
    afni_dir = os.path.join(deriv_dir, "afni")
    work_dir = os.path.join(afni_dir, subj, sess)
    timing_dir = os.path.join(deriv_dir, "timing_files", subj, sess)

    # make tf_dict
    time_list = [x for x in os.listdir(timing_dir)]
    time_list.sort()
    decon_str = time_list[0].split("_")[2]
    tf_dict = {}
    for time_file in time_list:
        beh = time_file.split("_")[-1].split(".")[0]
        tf_dict[beh] = os.path.join(timing_dir, time_file)

    with open(os.path.join(work_dir, "afni_data.json")) as jf:
        afni_data = json.load(jf)

    # write deconvolution
    afni_data = deconvolve.write_decon(2, decon_str, tf_dict, afni_data, work_dir)


if __name__ == "__main__":
    main()
