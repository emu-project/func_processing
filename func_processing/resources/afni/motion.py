"""Make motion, censor files for deconvolution.

Use fMRIprep desc-confounds_timeseries.tsv to make
mean motion, derivative motion, and censor files.
Censor includes volume preceding motion event.
"""

import os
import json
import pandas as pd


def mot_files(work_dir, afni_data, task):
    """Constuct motion and censor files.

    Mine <fMRIprep>_desc-confounds_timeseries.tsv for motion events, make
    motion files for mean (6df) and derivative (6df) motion events. Also,
    create motion censor file. Volume preceding a motion event is also
    censored. Finally, report the number of censored volumes.

    I'm not sure if motion is demeaned or not, given that
    it is output by fMRIprep (mined from confounds.tsv file).

    Parameters
    ----------
    work_dir : str
        /path/to/project_dir/derivatives/afni/sub-1234/ses-A

    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [mot-confound<1..N>] = fmriprep motion confound timeseries

    task : str
        BIDS task string (task-test)

    Returns
    -------
    afni_data : dict
        updated with names of motion files

        added afni_data keys:

        - [mot-mean] = motion mean file

        - [mot-deriv] = motion derivative file

        - [mot-censor] = binary censory vector

    Notes
    -----
    As runs do not have an equal number of volumes, motion/censor files
    for each run are concatenated into a single file rather than
    managing zero padding.

    Writes 1D files - AFNI reads tsv as containing a header!
    """
    # determine relevant col labels
    mean_labels = [
        "trans_x",
        "trans_y",
        "trans_z",
        "rot_x",
        "rot_y",
        "rot_z",
    ]

    drv_labels = [
        "trans_x_derivative1",
        "trans_y_derivative1",
        "trans_z_derivative1",
        "rot_x_derivative1",
        "rot_y_derivative1",
        "rot_z_derivative1",
    ]

    # start empty lists to append
    mean_cat = []
    deriv_cat = []
    censor_cat = []
    censor_inv = []

    num_mot = len([y for x, y in afni_data.items() if "mot-confound" in x])
    assert (
        num_mot > 0
    ), "ERROR: afni_data['mot-confound?'] not found. Check resources.afni.copy.copy_data"

    mot_list = [x for k, x in afni_data.items() if "mot-confound" in k]
    mot_str = mot_list[0].replace("run-1_", "")
    if not os.path.exists(
        os.path.join(
            work_dir, mot_str.replace("confounds", "censor").replace(".tsv", ".1D")
        )
    ):
        print("Making motion mean, derivative, censor files ...")
        for mot_file in mot_list:

            # read in data
            df_all = pd.read_csv(os.path.join(work_dir, mot_file), sep="\t")

            # make motion mean file, round to 6 sig figs
            df_mean = df_all[mean_labels].copy()
            df_mean = df_mean.round(6)
            mean_cat.append(df_mean)

            # make motion deriv file
            df_drv = df_all[drv_labels].copy()
            df_drv = df_drv.fillna(0)
            df_drv = df_drv.round(6)
            deriv_cat.append(df_drv)

            # make motion censor file - sum columns,
            # invert binary, exclude preceding volume
            df_cen = df_all.filter(regex="motion_outlier")
            df_cen["sum"] = df_cen.iloc[:, :].sum(1)
            df_cen = df_cen.astype(int)
            df_cen = df_cen.replace({0: 1, 1: 0})
            zero_pos = df_cen.index[df_cen["sum"] == 0].tolist()
            zero_fill = [x - 1 for x in zero_pos]
            if -1 in zero_fill:
                zero_fill.remove(-1)
            df_cen.loc[zero_fill, "sum"] = 0
            censor_cat.append(df_cen)

            # reinvert for use with resources.afni.deconvolve.write_new_decon
            df_inv = df_cen.replace({0: 1, 1: 0})
            censor_inv.append(df_inv)

        # cat files into singule file rather than pad zeros for e/run
        df_mean_cat = pd.concat(mean_cat, ignore_index=True)
        df_deriv_cat = pd.concat(deriv_cat, ignore_index=True)
        df_censor_cat = pd.concat(censor_cat, ignore_index=True)
        df_censor_inv = pd.concat(censor_inv, ignore_index=True)

        # determine BIDS string, write tsvs, make sure
        # output value is float (not scientific notation)
        df_mean_cat.to_csv(
            os.path.join(
                work_dir,
                f"""{mot_str.replace("confounds", "mean").replace(".tsv", ".1D")}""",
            ),
            sep="\t",
            index=False,
            header=False,
            float_format="%.6f",
        )
        df_deriv_cat.to_csv(
            os.path.join(
                work_dir,
                f"""{mot_str.replace("confounds", "deriv").replace(".tsv", ".1D")}""",
            ),
            sep="\t",
            index=False,
            header=False,
            float_format="%.6f",
        )
        df_censor_cat.to_csv(
            os.path.join(
                work_dir,
                f"""{mot_str.replace("confounds", "censor").replace(".tsv", ".1D")}""",
            ),
            sep="\t",
            index=False,
            header=False,
            columns=["sum"],
        )
        df_censor_inv.to_csv(
            os.path.join(
                work_dir,
                f"""{mot_str.replace("confounds", "censorInv").replace(".tsv", ".1D")}""",
            ),
            sep="\t",
            index=False,
            header=False,
            columns=["sum"],
        )

        # determine number censored volumes
        num_vol = df_censor_cat["sum"].sum()
        num_tot = len(df_censor_cat)
        cen_dict = {
            "total_volumes": int(num_tot),
            "included_volumes": int(num_vol),
            "proportion_excluded": round(1 - (num_vol / num_tot), 3),
        }
        with open(
            os.path.join(work_dir, f"func/info_{task}_censored_volumes.json"), "w"
        ) as jfile:
            json.dump(cen_dict, jfile)

    # update afni_data
    afni_data[
        "mot-mean"
    ] = f"""{mot_str.replace("confounds", "mean").replace(".tsv", ".1D")}"""
    afni_data[
        "mot-deriv"
    ] = f"""{mot_str.replace("confounds", "deriv").replace(".tsv", ".1D")}"""
    afni_data[
        "mot-censor"
    ] = f"""{mot_str.replace("confounds", "censor").replace(".tsv", ".1D")}"""
    afni_data[
        "mot-censorInv"
    ] = f"""{mot_str.replace("confounds", "censorInv").replace(".tsv", ".1D")}"""

    return afni_data
