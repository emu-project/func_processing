"""Control module for running AFNI's reface.

Replaces subject T1w face with composite.
"""
# %%
import os
import sys
from func_processing.resources.afni import process


# %%
def control_reface(subj, sess, t1_file, proj_dir, method):
    """Control de/refacing of T1-weighted files.

    Parameters
    ----------
    subj : str
        BIDS subject string (sub-1234)

    sess : str
        BIDS session string (ses-A)

    t1_file : str
        file name of T1-weighted file
        (sub-1234_ses-A_T1w.nii.gz)

    proj_dir : str
        path to BIDS project dir
        (/path/to/BIDS/proj)

    method : str
        "deface", "reface", or "reface_plus" method

    Returns
    -------
    msg_out : str
        Success message
    """
    msg_out = process.reface(subj, sess, t1_file, proj_dir, method)
    return msg_out
