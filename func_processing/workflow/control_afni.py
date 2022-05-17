"""Control module for running AFNI.

These functions will finish pre-processing following
fMRIprep, and then deconvolve EPI data. Also supports
resting state and group-level analyses.
"""
# %%
import os
import sys
import glob
from func_processing.resources.afni import copy
from func_processing.resources.afni import process
from func_processing.resources.afni import masks
from func_processing.resources.afni import motion
from func_processing.resources.afni import deconvolve
from func_processing.resources.afni import group


# %%
def control_preproc(prep_dir, afni_dir, subj, sess, task, tplflow_str, do_blur):
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

    tplflow_str : str
        template ID string, for finding fMRIprep output in
        template space (space-MNIPediatricAsym_cohort-5_res-2)

    do_blur : bool
        [T/F] whether to blur as part of pre-processing

    Returns
    -------
    afni_data : dict
        dictionary containing mappings for AFNI files

        afni_data keys:

        - [struct-t1] = pre-processed T1w

        - [mask-brain] = brain mask

        - [mask-probGM] = gray matter probability label

        - [mask-probWM] = white matter probability label

        - [mask-erodedGM] = gray matter eroded mask

        - [mask-erodedWM] = white matter eroded mask

        - [mask-int] = EPI-structural intersection mask

        - [mask-min] = mask of EPI space with >minimum signal

        - [epi-preproc?] = pre-processed EPI run-?

        - [epi-blur?] = blurred/smoothed EPI run-?, if do_blur = T

        - [epi-scale?] = scaled EPI run-?

        - [mot-confound?] = confounds timeseries for run-?

        - [mot-mean] = mean motion for task (6dof)

        - [mot-deriv] = derivative motion for task (6dof)

        - [mot-censor] = binary censor vector for task
    """
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
    if do_blur:
        afni_data = process.blur_epi(work_dir, subj_num, afni_data)

    # make masks
    afni_data = masks.make_intersect_mask(
        work_dir, subj_num, afni_data, sess, task, do_blur
    )
    afni_data = masks.make_tissue_masks(work_dir, subj_num, afni_data)
    afni_data = masks.make_minimum_masks(work_dir, subj_num, task, afni_data)

    # scale data
    afni_data = process.scale_epi(work_dir, subj_num, afni_data, do_blur)

    # make mean, deriv, censor motion files
    afni_data = motion.mot_files(work_dir, afni_data, task)

    return afni_data


def control_deconvolution(
    afni_data,
    afni_dir,
    dset_dir,
    subj,
    sess,
    task,
    dur,
    decon_plan,
    kp_interm,
    decon_method="new",
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
        deconvolutions, see notes below

        [default=None, yields decon_<task>_UniqueBehs]

    kp_interm : bool
        [T/F] whether to keep (T) or remove (F) intemediates

    Returns
    -------
    afni_data : dict
        updated with decon output

        added afni_data keys:

        - [dcn-<decon_title>] = decon_<task>_<decon_title>_stats.REML_cmd

        - [epi-nuiss] = nuissance signal file

        - [rml-<decon_title>] = deconvolved file (decon_<task>_<decon_title>_stats_REML+tlrc)

    Notes
    -----
    Only onset timing files accepted, not married onset:duration! Timing files
    must be AFNI formatted, (one row/run for each beahvior). See example in
    qc/no_valence.

    decon_plan should have the following format:

    {"Decon Tile": {

    "BehA": "/path/to/timing_behA.txt",

    "BehB": "/path/to/timing_behB.txt",

    "BehC": "/path/to/timing_behC.txt"}}

    Example:

    {"NegNeuPosTargLureFoil": {

    "negTH": "/path/to/negative_target_hit.txt",

    "negTM": "/path/to/negative_target_miss.txt",

    "negLC": "/path/to/negative_lure_cr.txt"}}
    """
    # setup directories
    work_dir = os.path.join(afni_dir, subj, sess)

    # get default timing files if none supplied
    if not decon_plan:
        decon_plan = deconvolve.timing_files(dset_dir, afni_dir, subj, sess, task)

    # generate decon matrices, scripts
    for decon_name, tf_dict in decon_plan.items():
        if decon_method == "new":
            afni_data = deconvolve.write_new_decon(
                decon_name, tf_dict, afni_data, work_dir, dur
            )
        else:
            afni_data = deconvolve.write_decon(
                decon_name, tf_dict, afni_data, work_dir, dur
            )

    # run various reml scripts
    afni_data = deconvolve.run_reml(work_dir, afni_data)

    # clean
    if not kp_interm:
        for tmp_file in glob.glob(f"{work_dir}/**/tmp*", recursive=True):
            os.remove(tmp_file)

    return afni_data


def control_resting(afni_data, afni_dir, subj, sess, coord_dict, kp_interm):
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

    coord_dict : dict
        seed name, coordinates

        {"rPCC": "5 -55 25"}

    kp_interm : bool
        [T/F] whether to keep (T) or remove (F) intemediates

    Returns
    -------
    afni_data : dict
        updated with generated files

        added keys to afni_data:

        - [reg-matrix] = epi projection matrix

        - [S<seed>-ztrans] = Z-transformed seed-based correlation matrix
    """
    # setup dir
    work_dir = os.path.join(afni_dir, subj, sess)

    # generate regression matrix, determine snr/corr/noise
    afni_data = deconvolve.regress_resting(afni_data, work_dir)
    afni_data = process.resting_metrics(afni_data, work_dir)
    afni_data = process.resting_seed(coord_dict, afni_data, work_dir)

    # clean
    if not kp_interm:
        for tmp_file in glob.glob(f"{work_dir}/**/tmp*", recursive=True):
            os.remove(tmp_file)

    return afni_data


def control_resting_group(seed, task, deriv_dir, group_dir, group_data, do_blur):
    """Conduct group-level analyses.

    Construct group GM intersection mask, then run on subject
    correlation matrices.

    Parameters
    ----------
    seed : str
        seed name (rPCC)

    task : str
        BIDS string (task-rest)

    deriv_dir : str
        location of project AFNI derivatives

    group_dir : str
        output location of work

    group_data : dict
        contains keys pointing to required files

        required keys:

        - [mask-gm] = gray matter mask

        - [subj-list] = list of subjects

        - [all-ztrans] = list of Ztrans files

    do_blur : bool
        [T/F] whether blur was done in pre-processing

    Returns
    -------
    group_data : dict
        updated with the fields for generated files

        added afni_data keys:

        - [mask-int] = gray matter intersection mask

        - [S<seed>-etac] = seed stat output
    """
    group_data = group.int_mask(task, deriv_dir, group_data, group_dir)
    group_data = group.resting_etac(seed, group_data, group_dir, do_blur)
    return group_data


def control_task_group(beh_list, task, sess, deriv_dir, group_dir, group_data, do_blur):
    """Conduct group-level analyses.

    Construct group GM intersection mask, then run A-vs-B ETAC.

    Parameters
    ----------
    beh_list : list
        list of 2 behaviors which match sub-brick name

        e.g. neg for neg#0_Coef

    task : str
        BIDS string (task-test)

    sess : str
        BIDS session (ses-S2)

    deriv_dir : str
        location of project AFNI derivatives

    group_dir : str
        output location of work

    group_data : dict
        contains keys pointing to required files

        required keys:

        - [mask-gm] = gray matter mask

        - [subj-list] = list of subjects

        - [dcn-file] = decon file string

    do_blur : bool
        [T/F] whether blur was done in pre-processing

    Returns
    -------
    group_data : dict
        updated with keys for generated files

        added group_data keys:

        - [mask-int] = gray matter intersection mask

        - [behAB-etac] = etac stat output
    """
    group_data = group.int_mask(task, deriv_dir, group_data, group_dir)
    group_data = group.task_etac(
        beh_list, deriv_dir, sess, group_data, group_dir, do_blur
    )
    return group_data
