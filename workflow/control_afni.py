"""Control module for running AFNI.

These functions will finish pre-processing following
fMRIprep, and then deconvolve EPI data.
"""
# %%
import os
import sys
import glob

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.afni import copy, process, masks, motion, deconvolve


# %%
def control_preproc(
    prep_dir, afni_dir, subj, sess, task, tplflow_str,
):
    """Move data through AFNI pre-processing.

    Copy relevant files from derivatives/fmriprep to derivatives/afni,
    then blur and scale EPI data. Also creates EPI-T1 intersection
    and tissue class masks. Finally, generate motion mean, derivative,
    and censor files.

    Parameters
    ----------
    prep_dir : str
        /path/to/BIDS/project/derivatives/fmriprep
    afni_dir : str
        /path/to/BIDS/project/derivatives/afni
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-S1)
    task : str
        BIDS task string (task-test)
    tplflow_str = str
        template ID string, for finding fMRIprep output in
        template space (space-MNIPediatricAsym_cohort-5_res-2)

    Returns
    -------
    afni_data : dict
        dictionary containing mappings for AFNI files

        struct-t1 = pre-processed T1w
        mask-brain = brain mask
        mask-probGM = gray matter probability label
        mask-probWM = white matter probability label
        mask-erodedGM = gray matter eroded mask
        mask-erodedWM = white matter eroded mask
        mask-int = EPI-structural intersection mask
        mask-min = mask of EPI space with >minimum signal
        epi-preproc? = pre-processed EPI run-?
        epi-blur? = blurred/smoothed EPI run-?
        epi-scale? = scaled EPI run-?
        mot-confound? = confounds timeseries for run-?
        mot-mean = mean motion for task (6dof)
        mot-deriv = derivative motion for task (6dof)
        mot-censor = binary censor vector for task
    """

    # # for testing
    # prep_dir = "/home/data/madlab/McMakin_EMUR01/derivatives/fmriprep"
    # afni_dir = "/scratch/madlab/McMakin_EMUR01/derivatives/afni"
    # subj = "sub-4146"
    # sess = "ses-S2"
    # task = "task-rest"
    # tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"

    # setup directories
    work_dir = os.path.join(afni_dir, subj, sess)
    anat_dir = os.path.join(work_dir, "anat")
    func_dir = os.path.join(work_dir, "func")
    sbatch_dir = os.path.join(work_dir, "sbatch_out")
    for h_dir in [anat_dir, func_dir, sbatch_dir]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # get fMRIprep data
    afni_data = copy.copy_data(prep_dir, work_dir, subj, task, tplflow_str)

    # blur data
    subj_num = subj.split("-")[-1]
    afni_data = process.blur_epi(work_dir, subj_num, afni_data)

    # make masks
    afni_data = masks.make_intersect_mask(work_dir, subj_num, afni_data, sess, task)
    afni_data = masks.make_tissue_masks(work_dir, subj_num, afni_data)
    afni_data = masks.make_minimum_masks(work_dir, subj_num, sess, task, afni_data)

    # scale data
    afni_data = process.scale_epi(work_dir, subj_num, afni_data)

    # make mean, deriv, censor motion files
    afni_data = motion.mot_files(work_dir, afni_data, task)

    return afni_data


def control_deconvolution(
    afni_data, afni_dir, dset_dir, subj, sess, task, dur, decon_plan,
):
    """Generate and run planned deconvolutions.

    Use AFNI's 3dDeconvolve and 3dREMLfit to deconvolve EPI
    timeseries. This is oriented from the <decon_json> input.
    First, a deconvolution script is generated, saved
    (decon_<task>_<decon_title>.sh), and ran to generate
    AFNI's X.files and REML script (decon_<task>_<decon_title>_stats.REML_cmd).
    Then a nuissance file is generated, and finally 3dREMlfit
    deconvolves the EPI data.

    Will make a nuissance file for each <task>, and condcut a
    deconvolution for each key (<decon_title>) in decon_json. See
    `Notes` below.

    Parameters
    ----------
    afni_data : dict
        mapping of AFNI data, returned by control_preproc
    afni_dir : str
        /path/to/BIDS/project/derivatives/afni
    dset_dir : str
        /path/to/BIDS/project/dset
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-S1)
    task : str
        BIDS task string (task-test)
    dur : int/float/str
        duration of task to model (2)
    decon_plan : dict
        mapping of behvavior to timing files for planned
        deconvolutions, see notes below [default=None]

    Returns
    -------
    afni_data : dict
        updated with decon output
        dcn-<decon_title> = decon_<task>_<decon_title>_stats.REML_cmd
        epi-nuiss = nuissance signal file
        rml-<decon_title> = deconvolved file (decon_<task>_<decon_title>_stats_REML+tlrc)

    Notes
    -----
    Only onset timing files accepted, not married onset:duration! Timing files
    must be AFNI formatted, (one row/run for each beahvior).

    decon_plan should have the following format:
        {"Decon Tile": {
            "BehA": "/path/to/timing_behA.txt",
            "BehB": "/path/to/timing_behB.txt",
            "BehC": "/path/to/timing_behC.txt",
            }
        }

    Example:
        {"NegNeuPosTargLureFoil": {
            "negTH": "/path/to/negative_target_hit.txt",
            "negTM": "/path/to/negative_target_miss.txt",
            "negLC": "/path/to/negative_lure_cr.txt",
            }
        }

    [decon_plan=None] yields decon_<task>_UniqueBehs*
    """

    # setup directories
    work_dir = os.path.join(afni_dir, subj, sess)

    # get default timing files if none supplied
    if not decon_plan:
        decon_plan = deconvolve.timing_files(dset_dir, afni_dir, subj, sess, task)

    # generate decon matrices, scripts
    for decon_name, tf_dict in decon_plan.items():
        afni_data = deconvolve.write_decon(
            decon_name, tf_dict, afni_data, work_dir, dur
        )

    # run various reml scripts
    afni_data = deconvolve.run_reml(work_dir, afni_data)

    # clean
    for tmp_file in glob.glob(f"{work_dir}/**/tmp*", recursive=True):
        os.remove(tmp_file)

    return afni_data


def control_resting(afni_data, afni_dir, subj, sess):
    """Generate and control resting state regressions.

    Based on example 11 of afni_proc.py and s17.proc.FT.rest.11
    of afni_data6. Projects regression matrix, and generates various
    metrics like SNR, GCOR, etc.

    Parameters
    ----------
    afni_data : dict
        mapping of AFNI data, returned by control_preproc
    afni_dir : str
        /path/to/BIDS/project/derivatives/afni
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-S1)
    """

    # setup dir
    work_dir = os.path.join(afni_dir, subj, sess)

    # generate regression matrix, determine snr/corr/noise
    afni_data = deconvolve.regress_resting(afni_data, work_dir)
    afni_data = process.resting_metrics(afni_data, work_dir)

    # clean
    for tmp_file in glob.glob(f"{work_dir}/**/tmp*", recursive=True):
        os.remove(tmp_file)

    return afni_data
