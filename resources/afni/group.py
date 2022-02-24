"""Title.

Desc
"""

# %%
import os
import glob
from . import submit


# %%
def resting_seed(coord_dict, afni_data, work_dir):
    """Title.

    Desc
    """
    # unpack afni_data to get file, reference strings
    reg_file = afni_data["reg-matrix"]
    int_mask = afni_data["mask-int"]
    file_censor = afni_data["mot-censor"]
    subj_num = reg_file.split("sub-")[-1].split("/")[0]

    # make seed for coordinates, get timeseries
    for seed, coord in coord_dict.items():
        seed_file = int_mask.replace("desc-intersect", f"desc-RS{seed}")
        seed_ts = file_censor.replace("desc-censor", f"desc-RS{seed}")
        if not os.path.exists(seed_file):
            print(f"Making Seed {seed}\n")
            h_cmd = f"""
                echo {coord} > {work_dir}/anat/tmp.txt
                3dUndump \
                    -prefix {seed_file} \
                    -master {reg_file} \
                    -srad 2 \
                    -xyz {work_dir}/tmp.txt

                3dROIstats \
                    -quiet \
                    -mask {seed_file} \
                    {reg_file} > {seed_ts}
            """
            h_out, h_err = submit.submit_hpc_subprocess(h_cmd)
        assert os.path.exists(seed_file), f"Failed to write {seed_file}"

    # project correlation matrix, z-transform
    for seed in coord_dict:
        corr_file = reg_file.replace("+tlrc", f"_{seed}_corr")
        ztrans_file = reg_file.replace("+tlrc", f"_{seed}_ztrans")
        seed_ts = file_censor.replace("desc-censor", f"desc-RS{seed}")
        if not os.path.exists(f"{ztrans_file}+tlrc.HEAD"):
            print(f"Making Ztrans  {ztrans_file}\n")
            h_cmd = f"""
                3dTcorr1D \
                    -mask {int_mask} \
                    -prefix {corr_file} \
                    {reg_file} \
                    {seed_ts}

                3dcalc \
                    -a {corr_file}+tlrc \
                    -expr 'log((1+a)/(1-a))/2' \
                    -prefix {ztrans_file}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 4, 1, f"{subj_num}Ztran", f"{work_dir}/sbatch_out"
            )
        assert os.path.exists(
            f"{ztrans_file}+tlrc.HEAD"
        ), f"Failed to write {ztrans_file}+tlrc.HEAD"
        afni_data[f"S{seed}-ztrans"] = f"{ztrans_file}+tlrc"
    return afni_data


def int_mask(task, deriv_dir, group_data, group_dir):
    """Title.

    Desc
    """

    # check for req files
    assert group_data["mask-gm"], "ERROR: required template GM mask not found."
    assert group_data["subj-list"], "ERROR: required subject list not found."
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
    assert os.path.exists(group_mask), f"Failed to write {group_mask}"

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
    assert os.path.exists(final_mask), f"Failed to write {final_mask}"
    group_data["mask-int"] = final_mask
    return group_data


def resting_etac(seed, group_data, group_dir):
    """Title.

    Desc
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
            {group_files}
    """
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 20, 4, 10, "rsETAC", f"{group_dir}"
    )
