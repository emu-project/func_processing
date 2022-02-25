"""Functions for group-level analyses.

Makes group masks, conducts group statistics.
"""

# %%
import os
import glob
from . import submit


# %%
def int_mask(task, deriv_dir, group_data, group_dir):
    """Create group gray matter intersection mask.

    Parameters
    ----------
    task : str
        BIDS task string (task-rest)
    deriv_dir : str
        location of project AFNI derivatives
    group_data : dict
        passed files
    group_dir : str
        output location of work

    Returns
    -------
    group_data : dict
        updated with the field
        mask-int = GM intersect mask
    """

    # check for req files, unpack
    assert group_data[
        "mask-gm"
    ], "ERROR: required template GM mask not found, check cli.run_afni_resting_group.py"
    assert group_data[
        "subj-list"
    ], "ERROR: required subject list not found, check cli.run_afni_resting_group.py"
    gm_mask = group_data["mask-gm"]
    subj_list = group_data["subj-list"]

    # make group intersection mask from all subjs who have intersect mask
    group_mask = os.path.join(
        group_dir, "tpl-MNIPediatricAsym_cohort-5_res-2_desc-grpIntx_mask.nii.gz"
    )
    if not os.path.exists(group_mask):
        mask_list = []
        for subj in subj_list:
            mask_file = sorted(
                glob.glob(
                    f"{deriv_dir}/{subj}/**/anat/{subj}_*_{task}_*intersect_mask.nii.gz",
                    recursive=True,
                )
            )
            if mask_file:
                mask_list.append(mask_file[0])

        # make mask
        h_cmd = f"""
            3dmask_tool \
                -frac 1 \
                -prefix {group_mask} \
                -input {" ".join(mask_list)}
        """
        h_out, h_err = submit.submit_hpc_subprocess(h_cmd)
    assert os.path.exists(
        group_mask
    ), f"Failed to write {group_mask}, check resources.afni.group.int_mask."

    # multiply intersection mask by template GM mask
    final_mask = group_mask.replace("grpIntx", "grpIntxGM")
    if not os.path.exists(final_mask):
        h_cmd = f"""
            c3d \
                {group_mask} {gm_mask} \
                -reslice-identity \
                -o {group_dir}/tmp_gm.nii.gz

            c3d \
                {group_dir}/tmp_gm.nii.gz {group_mask} \
                -multiply \
                -o {final_mask}

            c3d \
                {final_mask} \
                -thresh 0.5 1 1 0 \
                -o {final_mask} \
                && rm {group_dir}/tmp_gm.nii.gz
        """
        h_out, h_err = submit.submit_hpc_subprocess(h_cmd)
    assert os.path.exists(
        final_mask
    ), f"Failed to write {final_mask}, check resources.afni.group.int_mask."
    group_data["mask-int"] = final_mask
    return group_data


def resting_etac(seed, group_data, group_dir):
    """Conduct A vs not-A via ETAC.

    Parameters
    ----------
    seed : str
        seed name (rPCC)
    group_data : dict
        dictionary of various files
    group_dir : str
        location of output directory

    Returns
    -------
    group_data : dict
        updated with the field
        S<seed>-etac = final ETAC output file
    """
    int_mask = group_data["mask-int"]
    group_files = group_data["all-ztrans"]
    final_file = f"FINAL_RS-{seed}"
    h_cmd = f"""
        cd {group_dir}
        3dttest++ \
            -mask {int_mask} \
            -prefix {final_file} \
            -prefix_clustsim {final_file}_clustsim \
            -ETAC \
            -ETAC_opt NN=2:sid=2:hpow=0:pthr=0.01,0.005,0.002,0.001:name=etac \
            -setA \
            {" ".join(group_files)}
    """
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 20, 4, 10, "rsETAC", f"{group_dir}"
    )
    etac_file = (
        f"{group_dir}/{final_file}_clustsim.etac.ETACmask.global.2sid.5perc.nii.gz"
    )
    assert os.path.exists(
        etac_file
    ), "ERROR: ETAC failed. Check resources.afni.group.resting_etac."
    group_data[f"S{seed}-etac"] = etac_file
    return group_data
