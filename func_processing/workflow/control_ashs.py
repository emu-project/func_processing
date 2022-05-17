"""Control module for running ASHS.

These functions will use T1- and T2-weighted files
to produce hippocampal subfield labels.
"""
# %%
import os
import sys
from func_processing.resources.ashs import hipseg


# %%
def control_hipseg(
    t1_dir,
    t2_dir,
    deriv_dir,
    work_dir,
    atlas_dir,
    sing_img,
    subj,
    t1_file,
    t2_file,
    atlas_str,
):
    """Segment hippocampal subfields via ASHS.

    Use the singularity of docker://nmuncy/ashs to produce hippocampal
    subfield labels in <deriv_dir>. Requires native T1- and T2-weighted
    NIfTI files (ref <anat_dir>). Segmentation intermediates are written
    to <work_dir>, and then removed after copyfing <work_dir>/final
    contents to <deriv_dir>.

    This work is equal to merely calling the resources.ashs.hipseg module, but
    written as a workflow for the sake of consistency.

    Parameters
    ----------
    t1_dir : str
        absolute path to directory containing T1-weighted file

    t2_dir : str
        absolute path to directory containing T2-weighted file

    deriv_dir : str
        absolute path to desired output location

    work_dir : str
        absolute path to desired working directory,
        relevant files are copied to deriv_dir

    atlas_dir : str
        absolute path to directory containing ASHS atlas

    sing_img : str
        /path/to/ashs_singularity.simg

    subj : str
        BIDs subject (sub-1234)

    t1_file : str
        file name of T1-weighted file (sub-1234_ses-S1_T1w.nii.gz)

    t2_file : str
        file name of T2-weighted file (sub-1234_ses-S1_T2w.nii.gz)

    atlas_str : str
        ASHS atlas directory, found within atlas_dir
        (ashs_atlas_magdeburg)

    Returns
    -------
    ashs_out : list
        final ASHS labels
    """
    ashs_out = hipseg.run_ashs(
        t1_dir,
        t2_dir,
        deriv_dir,
        work_dir,
        atlas_dir,
        sing_img,
        subj,
        t1_file,
        t2_file,
        atlas_str,
    )

    return ashs_out
