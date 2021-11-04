"""Control module for running AFNI.

These functions will finish pre-processing following
fMRIprep, and then deconvolve EPI data.
"""
# %%
import os
import sys
import glob
import json

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.afni import copy, process, masks, motion, deconvolve


# %%
def control_preproc(deriv_dir, subj, sess, task, num_runs, tplflow_str):
    """Move data through AFNI pre-processing.

    Copy relevant files from derivatives/fmriprep to derivatives/afni,
    then blur and scale EPI data. Also creates EPI-T1 intersection
    and tissue class masks. Finally, generate motion mean, derivative,
    and censor files.

    Parameters
    ----------
    deriv_dir : str
        /path/to/BIDS/project/derivatives
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-S1)
    task : str
        BIDS task string (task-test)
    num_runs : int
        number of EPI runs for session (3)
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

    # setup directories
    prep_dir = os.path.join(deriv_dir, "fmriprep")
    afni_dir = os.path.join(deriv_dir, "afni")
    work_dir = os.path.join(afni_dir, subj, sess)
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    # get fMRIprep data
    afni_data = copy.copy_data(
        prep_dir, work_dir, subj, sess, task, num_runs, tplflow_str
    )

    # blur data
    subj_num = subj.split("-")[-1]
    afni_data = process.blur_epi(work_dir, subj_num, afni_data)

    # make masks
    afni_data = masks.make_intersect_mask(work_dir, subj_num, afni_data)
    afni_data = masks.make_tissue_masks(work_dir, subj_num, afni_data)

    # scale data
    afni_data = process.scale_epi(work_dir, subj_num, sess, task, afni_data)

    # make mean, deriv, censor motion files
    afni_data = motion.mot_files(work_dir, afni_data)

    # check for files
    assert "Missing" not in afni_data.values(), "Missing value (file) in afni_data."

    # clean
    for tmp_file in glob.glob(f"{work_dir}/tmp*"):
        os.remove(tmp_file)
    for sbatch_file in glob.glob(f"{work_dir}/sbatch*"):
        os.remove(sbatch_file)

    return afni_data


def control_deconvolution(deriv_dir, subj, sess, afni_data, decon_json, dur=2):
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
    deriv_dir : str
        /path/to/BIDS/project/derivatives
    subj : str
        BIDS subject string (sub-1234)
    sess : str
        BIDS session string (ses-S1)
    afni_data : dict
        mapping of AFNI data, returned by control_preproc
    decon_json : str
        /path/to/decon/plan.json
    dur : int/float
        duration of task to model [default=2]

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

    decon_plan.json should have the following format:
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
    """

    # setup directories
    afni_dir = os.path.join(deriv_dir, "afni")
    work_dir = os.path.join(afni_dir, subj, sess)

    with open(os.path.join(decon_json)) as jf:
        decon_plan = json.load(jf)

    # write deconvolution
    for decon_str in decon_plan:
        tf_dict = decon_plan[decon_str]
        afni_data = deconvolve.write_decon(dur, decon_str, tf_dict, afni_data, work_dir)

    # run deconvolution
    afni_data = deconvolve.run_reml(work_dir, afni_data)

    # check for files, clean
    assert "Missing" not in afni_data.values(), "Missing value (file) in afni_data."
    for sbatch_file in glob.glob(f"{work_dir}/sbatch*"):
        os.remove(sbatch_file)

    return afni_data
