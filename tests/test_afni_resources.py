#!/usr/bin/env python3

r"""Test resources of AFNI pipeline.

Use to test pre-processing, task deconvolution,
and resting state correlation projection.

Using non-default [--test-preproc] allows to test portions
of pre-processing. Using optional [--test-task-decon]
and [--test-rest-decon] allows for testing of portion or
full deconvoution/regression.

Output files are written to <scratch_dir>/afni/<subj>/<sess>.

Examples
--------
# test pre-procesing
code_dir="$(dirname "$(pwd)")"
sbatch --job-name=runAfniTest \
    --output=${code_dir}/tests/runAfniTest_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    test_afni_resources.py \
    -p sub-4146 \
    -s ses-S2 \
    -t task-test

# test portion of pre-processing
<sbatch syntax> \
    test_afni_resources.py \
    -p sub-4146 \
    -s ses-S2 \
    -t task-test \
    --test-preproc 3

# test pre-processing + task deconvolution
<sbatch syntax> \
    test_afni_resources.py \
    -p sub-4146 \
    -s ses-S2 \
    -t task-test \
    --do_blur \
    --test-task-decon 2

# test pre-processing + part resting deconvolution
<sbatch syntax> \
    test_afni_resources.py \
    -p sub-4146 \
    -s ses-S2 \
    -t task-rest \
    --test-rest-decon 1
"""

# %%
import os
import sys
import textwrap
from argparse import ArgumentParser, RawTextHelpFormatter

code_dir = os.path.dirname(sys.path[1])
sys.path.append(code_dir)
from resources.afni import copy, deconvolve, masks, motion, process


def test_preproc_steps(
    prep_dir, work_dir, subj, sess, task, tplflow_str, test_preproc, do_blur
):
    """Test pre-processing steps.

    Number of steps tested is controlled by int test_preproc.

    Parameters
    ----------
    prep_dir : str
        location of derivatives/fmriprep directory
    work_dir : str
        path to subject's working derivative dir
    subj : str
        BIDS subject string
    sess : str
        BIDS session string
    task : str
        BIDS task string
    tplflow_str : str
        templateflow atlas identifier
    test_preproc : int
        steps to test
    do_blur : bool
        whether to blur as part of pre-processing

    Returns
    -------
    afni_data : dict
        updated with fields containing paths to generated files
    """
    # get fMRIprep data
    afni_data = copy.copy_data(prep_dir, work_dir, subj, task, tplflow_str)
    if test_preproc == 1:
        print(f"\ncopy.copy_data for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    # blur data
    subj_num = subj.split("-")[-1]
    if do_blur:
        afni_data = process.blur_epi(work_dir, subj_num, afni_data)

    # make masks
    afni_data = masks.make_intersect_mask(
        work_dir, subj_num, afni_data, sess, task, do_blur
    )
    afni_data = masks.make_tissue_masks(work_dir, subj_num, afni_data)
    afni_data = masks.make_minimum_masks(work_dir, subj_num, task, afni_data)
    if test_preproc == 2:
        print(f"\nmasks for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    # scale data
    afni_data = process.scale_epi(work_dir, subj_num, afni_data, do_blur)
    if test_preproc == 3:
        print(f"\nprocess.scale_epi for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    # make mean, deriv, censor motion files
    afni_data = motion.mot_files(work_dir, afni_data, task)
    if test_preproc == 4:
        print(f"\nmotion.mot_files for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    return afni_data


def test_decon(
    proj_dir,
    work_dir,
    scratch_dir,
    decon_plan,
    subj,
    sess,
    task,
    test_task_decon,
    afni_data,
    dur=2,
):
    """Test task deconvolution.

    Number of steps tested is controlled by int test_task_decon.

    Parameters
    ----------
    proj_dir : str
        location of BIDS project directory
    work_dir : str
        path to subject's working derivative dir
    scratch_dir : str
        path to parent scratch derivatives dir
    decon_plan : None/dict
        dictionary pointing to timing files. See qc/no_valence
    subj : str
        BIDS subject string
    sess : str
        BIDS session string
    task : str
        BIDS task string
    test_task_decon : int
        steps to test
    afni_data : dict
        contains references to req files
    dur : int/float
        behavior length (seconds)

    Returns
    -------
    afni_data : dict
        updated with fields containing paths to generated files
    """
    # get default timing files if none supplied
    if not decon_plan:
        dset_dir = os.path.join(proj_dir, "dset")
        decon_plan = deconvolve.timing_files(dset_dir, scratch_dir, subj, sess, task)

    # generate decon matrices, scripts
    for decon_name, tf_dict in decon_plan.items():
        afni_data = deconvolve.write_new_decon(
            decon_name, tf_dict, afni_data, work_dir, dur
        )
    if test_task_decon == 1:
        print(f"\ndeconvolve.write_new_decon for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    # run various reml scripts
    afni_data = deconvolve.run_reml(work_dir, afni_data)
    return afni_data


def test_rest(work_dir, afni_data, test_rest_decon, subj):
    """Test task deconvolution.

    Number of steps tested is controlled by int test_rest_decon.

    Parameters
    ----------
    work_dir : str
        path to subject's working derivative dir
    afni_data : dict
        contains references to req files
    test_rest_decon : int
        steps to test
    subj : str
        BIDS subject string

    Returns
    -------
    afni_data : dict
        updated with fields containing paths to generated files
    """
    afni_data = deconvolve.regress_resting(afni_data, work_dir)
    if test_rest_decon == 1:
        print(f"\ndeconvolve.regress_resting for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    afni_data = process.resting_metrics(afni_data, work_dir)
    if test_rest_decon == 2:
        print(f"\nprocess.resting_metrics for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    coord_dict = {"rPCC": "5 -55 25"}
    afni_data = process.resting_seed(coord_dict, afni_data, work_dir)
    return afni_data


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
        "--scratch-dir",
        type=str,
        default="/scratch/madlab/McMakin_EMUR01/derivatives/afni",
        help=textwrap.dedent(
            """\
            Path to location for making AFNI intermediates
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--tplflow-str",
        type=str,
        default="space-MNIPediatricAsym_cohort-5_res-2",
        help=textwrap.dedent(
            """\
            template ID string, for finding fMRIprep output in template space,
            (default : %(default)s)
        """
        ),
    )
    parser.add_argument(
        "--test-preproc",
        type=int,
        default=5,
        help=textwrap.dedent(
            """\
            Number of pre-processing steps to test:
                0 = setup
                1 = copy data
                2 = make masks
                3 = scale data
                4 = make motion
                5 = all
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--do-blur",
        action="store_true",
        help=textwrap.dedent(
            """\
            Toggle of whether to use blurring option in pre-processing.
            Boolean (True if "--blur", else False).
            """
        ),
    )
    parser.add_argument(
        "--test-task-decon",
        type=int,
        default=None,
        help=textwrap.dedent(
            """\
            Use for testing task deconvolution, requires [--test-preproc 5]:
                1 = write decon script, generate X-files
                2 = 1, run decon
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--decon-plan",
        type=str,
        default=None,
        help=textwrap.dedent(
            """\
            Path to directory containing JSON deconvolution plans for each
            subject. Must be titled <subject>*.json. See notes in
            workflow.control_afni.control_deconvolution for description
            of dictionary format. Default (None) results in all unique
            behaviors modeled (decon_<task>_UniqueBehs*).
            (default : %(default)s)
            """
        ),
    )
    parser.add_argument(
        "--test-rest-decon",
        type=int,
        default=None,
        help=textwrap.dedent(
            """\
            Use for testing rest deconvolution, requires [--test-preproc 5]:
                1 = project regression matrix
                2 = 1, calculate resting metrics
                3 = 1-2, project seed-based correlation matrix
            (default : %(default)s)
            """
        ),
    )

    required_args = parser.add_argument_group("Required Arguments")
    required_args.add_argument(
        "-p",
        "--subj",
        help="BIDS subject string (sub-1234)",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-s",
        "--session",
        help="BIDS session str (ses-S2)",
        type=str,
        required=True,
    )
    required_args.add_argument(
        "-t",
        "--task",
        help="BIDS EPI task str (task-test)",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


def main():
    """Receive and check args, submit test functions."""
    # get args
    args = get_args().parse_args()
    proj_dir = args.proj_dir
    scratch_dir = args.scratch_dir
    subj = args.subj
    sess = args.session
    task = args.task
    tplflow_str = args.tplflow_str
    test_preproc = args.test_preproc
    do_blur = args.do_blur
    test_task_decon = args.test_task_decon
    decon_plan = args.decon_plan
    test_rest_decon = args.test_rest_decon

    # check dependent args
    if test_task_decon or test_rest_decon:
        assert test_preproc == 5, "--test-preproc 5 required to test deconvolutions."

    # setup
    prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")
    work_dir = os.path.join(scratch_dir, subj, sess)
    anat_dir = os.path.join(work_dir, "anat")
    func_dir = os.path.join(work_dir, "func")
    sbatch_dir = os.path.join(work_dir, "sbatch_out")
    for h_dir in [anat_dir, func_dir, sbatch_dir]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # test preproc resources
    if test_preproc == 0:
        print(f"\nSetup for {subj} complete.")
        return

    afni_data = test_preproc_steps(
        prep_dir, work_dir, subj, sess, task, tplflow_str, test_preproc, do_blur
    )

    # test task decon resources
    if test_task_decon:
        afni_data = test_decon(
            proj_dir,
            work_dir,
            scratch_dir,
            decon_plan,
            subj,
            sess,
            task,
            test_task_decon,
            afni_data,
        )
        print(f"\nTask decon test for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return

    if test_rest_decon:
        afni_data = test_rest(work_dir, afni_data, test_rest_decon, subj)
        print(f"\nRest decon test for {subj} complete.")
        print(f"\nafni_data : {afni_data}")
        return


if __name__ == "__main__":

    # require environment
    env_found = [x for x in sys.path if "emuR01" in x]
    if not env_found:
        print("\nERROR: madlab conda env emuR01 required.")
        print("\tHint: $madlab_env emuR01\n")
        sys.exit()
    main()
