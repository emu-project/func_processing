#!/usr/bin/env python

"""Check for completed data.

Check <proj_dir> for a completed data, and generate/update
logs/completed_preprocessing.tsv.

Requires internet connection for git pulling/pushing.
"""

# %%
import os
import sys

# from pathlib import Path
import textwrap
from argparse import ArgumentParser, RawTextHelpFormatter


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
    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-p",
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

    # For testing
    pat_github_emu = os.environ["TOKEN_GITHUB_EMU"]
    proj_dir = "/home/data/madlab/McMakin_EMUR01"

    # orient self, update logs
    # code_dir = str(Path(__file__).parent.parent.absolute())
    code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(code_dir)
    sys.path.append(code_dir)
    print(sys.path)
    from resources.reports.check_complete import check_preproc

    check_preproc(proj_dir, code_dir, pat_github_emu)


if __name__ == "__main__":
    main()
