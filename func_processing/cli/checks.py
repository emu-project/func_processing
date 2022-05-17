#!/usr/bin/env python3

r"""Check for completed data.

Check <proj_dir> for a completed data, and generate/update
logs/completed_preprocessing.tsv. Can be run locally on NAS
or on the HPC via [-p].

Requires internet connection for git pulling/pushing, so run
the HPC login node.

Examples
--------
check -t $TOKEN_GITHUB_EMU

check \
    -p /Volumes/homes/MaDLab/projects/McMakin_EMUR01 \
    -t TOKEN_GITHUB_EMU
"""

# %%
import os
import sys
import textwrap
from argparse import ArgumentParser, RawTextHelpFormatter
from ..resources.reports.check_complete import check_preproc


# %%
def get_args():
    """Get and parse arguments."""
    parser = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    parser.add_argument(
        "-p",
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
        "-n",
        "--new-df",
        action="store_true",
        help=textwrap.dedent(
            """\
            Whether to generate new log, use when new fields
            added to resources.reports.check_complete.
            """
        ),
    )

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-t",
        "--pat",
        help="Personal Access Token for github.com/emu-project",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Run checks resource."""
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    pat_github_emu = args.pat
    new_df = args.new_df

    # orient self, update logs
    code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    print(code_dir)
    # sys.path.append(code_dir)
    # from resources.reports.check_complete import check_preproc

    check_preproc(proj_dir, code_dir, pat_github_emu, new_df)


if __name__ == "__main__":

    # require environment for HPC (linux) only
    if sys.platform == "linux":
        env_found = [x for x in sys.path if "emuR01" in x]
        if not env_found:
            print("\nERROR: madlab conda env emuR01 required.")
            print("\tHint: $madlab_env emuR01\n")
            sys.exit()
    main()
