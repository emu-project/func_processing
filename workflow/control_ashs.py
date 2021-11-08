"""Control module for running ASHS.

These functions will use T1- and T2-weighted files
to produce hippocampal subfield labels.
"""
# %%
import os
import sys

proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(proj_dir)

from resources.ashs import hipseg


# %%
def control_hipseg(
    anat_dir,
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
    anat_dir : str
        /path/to/BIDS/dset/sub-1234/ses-A/anat
    deriv_dir : str
        /path/to/BIDS/derivatives/ashs/sub-1234/ses-A
    work_dir : str
        /path/to/BIDS/derivatives/temporary/sub-1234/ses-A
        temp dir for writing ASHS output, relevant files are
        copied to deriv_dir
    atlas_dir : str
        /path/to/atlas/parent/dir
    sing_img : str
        /path/to/ashs_singularity.simg
    subj : str
        BIDs subject (sub-1234)
    t1_file : str
        file name of T1-weighted file (sub-1234_ses-S1_T1w.nii.gz)
        found within anat_dir
    t2_file : str
        file name of T2-weighted file (sub-1234_ses-S1_T2w.nii.gz)
        found within anat_dir
    atlas_str : str
        ASHS atlas directory, found within atlas_dir
        (ashs_atlas_magdeburg)

    Returns
    -------
    ashs_out : list
        final ASHS labels
    """
    ashs_out = hipseg.run_ashs(
        anat_dir,
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
