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

    For EPI data of a specific task.

    Parameters
    ----------
    task : str
        BIDS task string (task-rest)

    deriv_dir : str
        location of project AFNI derivatives

    group_data : dict
        contains keys pointing to required files

        required keys:

        - [mask-gm] = gray matter mask

        - [subj-list] = list of subjects

    group_dir : str
        output location of work

    Returns
    -------
    group_data : dict
        updated with the intersection field

        added group_data key:

        - [mask-int] = GM intersect mask
    """
    # check for req files, unpack
    assert group_data[
        "mask-gm"
    ], "ERROR: required template GM mask not found, check cli.afni_resting_group.py"
    assert group_data[
        "subj-list"
    ], "ERROR: required subject list not found, check cli.afni_resting_group.py"
    gm_mask = group_data["mask-gm"]
    subj_list = group_data["subj-list"]

    # make group intersection mask from all subjs who have intersect mask
    group_mask = os.path.join(
        group_dir,
        f"tpl-MNIPediatricAsym_cohort-5_res-2_{task}_desc-grpIntx_mask.nii.gz",
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
        _, _ = submit.submit_hpc_subprocess(h_cmd)
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
        _, _ = submit.submit_hpc_subprocess(h_cmd)
    assert os.path.exists(
        final_mask
    ), f"Failed to write {final_mask}, check resources.afni.group.int_mask."
    group_data["mask-int"] = final_mask
    return group_data


def resting_etac(seed, group_data, group_dir, do_blur):
    """Conduct A vs not-A via ETAC.

    Parameters
    ----------
    seed : str
        seed name (rPCC)

    group_data : dict
        contains keys pointing to required files

        required keys:

        - [all-ztrans] = list of Ztrans files

        - [mask-int] = group GM intersection mask

    group_dir : str
        location of output directory

    do_blur : bool
        [T/F] whether blur was done in pre-processing

    Returns
    -------
    group_data : dict
        updated with the generated files

        added group_data keys:

        - [S<seed>-etac] = final ETAC output file
    """
    # check req args
    assert group_data[
        "all-ztrans"
    ], "ERROR: required group_data['all-ztrans'] not found, check cli.afni_resting_group.py"
    assert group_data[
        "mask-int"
    ], "ERROR: required group_data['mask-int'] not found, check resources.afni.group.int_mask"

    # unpack group_data
    intx_mask = group_data["mask-int"]
    group_files = group_data["all-ztrans"]
    final_file = f"FINAL_RS-{seed}"

    # build ETAC, write for review
    # TODO determine blur sizes rather than hardcode
    etac_blur = "0" if do_blur else "4 8"
    h_cmd = f"""
        cd {group_dir}
        3dttest++ \\
            -mask {intx_mask} \\
            -prefix {final_file} \\
            -prefix_clustsim {final_file}_clustsim \\
            -ETAC \\
            -ETAC_blur {etac_blur} \\
            -ETAC_opt NN=2:sid=2:hpow=0:pthr=0.01,0.005,0.002,0.001:name=etac \\
            -setA \\
            {" ".join(group_files)}
    """
    etac_script = os.path.join(group_dir, f"{final_file}.sh")
    with open(etac_script, "w") as script:
        script.write(h_cmd)

    # run if needed
    etac_file = os.path.join(
        group_dir, f"{final_file}_clustsim.etac.ETACmask.global.2sid.5perc.nii.gz"
    )
    if not os.path.exists(etac_file):
        print(f"\nRunning ETAC script {etac_script}")
        _, _ = submit.submit_hpc_sbatch(h_cmd, 20, 4, 10, "rsETAC", group_dir)

    # check for output, return
    assert os.path.exists(
        etac_file
    ), "ERROR: ETAC failed. Check resources.afni.group.resting_etac."
    group_data[f"S{seed}-etac"] = etac_file
    return group_data


def task_etac(beh_list, deriv_dir, sess, group_data, group_dir, do_blur):
    """Conduct A vs B via ETAC.

    Write and then run an ETAC command (3dttest++) to compare
    behavior A to behavior B.

    Parameters
    ----------
    beh_list : list
        two behaviors for setA, setB

    deriv_dir : str
        path to project afni derivatives

    sess : str
        BIDS session (ses-S2)

    group_data : dict
        contains keys pointing to required files

        required keys:

        - [subj-list] = list of subjects

        - [mask-int] = group GM intersection mask

        - [dcn-file] = decon file string

    do_blur : bool
        [T/F] whether blur was done in pre-processing

    Returns
    -------
    group_data : dict
        updated with generated files

        added group_data keys:

        - [behAB-etac] = final output ETAC file
    """
    # check req args
    assert (
        len(beh_list) == 2
    ), "ERROR: inappropriate number of behaviors passed in beh_list."
    assert group_data[
        "subj-list"
    ], "ERROR: required subject list not found, check cli.afni_task_group.py"
    assert group_data[
        "mask-int"
    ], "ERROR: required intx mask not found, check resources.afni.group.int_mask."
    assert group_data[
        "dcn-file"
    ], "ERROR: required decon string not found, check cli.afni_task_group.py"

    # unpack
    subj_list = group_data["subj-list"]
    intx_mask = group_data["mask-int"]
    dcn_file = group_data["dcn-file"]

    # determine which subjects have both behs
    set_a = []
    set_b = []
    beh_a, beh_b = beh_list
    for subj in subj_list:
        print(f"Checking {subj} for behaviors {beh_a}, {beh_b} ...")
        subj_dcn = os.path.join(deriv_dir, subj, sess, "func", dcn_file)
        a_out, _ = submit.submit_hpc_subprocess(
            f"3dinfo -label2index '{beh_a}#0_Coef' {subj_dcn}"
        )
        b_out, _ = submit.submit_hpc_subprocess(
            f"3dinfo -label2index '{beh_b}#0_Coef' {subj_dcn}"
        )
        a_decode = a_out.decode("utf-8").strip()
        b_decode = b_out.decode("utf-8").strip()
        print(a_decode, b_decode)
        if a_decode and b_decode:
            print(f"\tAdding {subj} to ETAC sets\n")
            set_a.append(subj)
            set_a.append(f"{subj_dcn}'[{a_decode}]'")
            set_b.append(subj)
            set_b.append(f"{subj_dcn}'[{b_decode}]'")
    print(f"Set A: \n{set_a} \n\nSet B: \n{set_b}")
    assert (
        len(set_a) > 1
    ), "Insufficient subject data found, check resources.afni.group.task_etac."

    # build ETAC, write for review
    final_file = f"FINAL_{beh_a}-{beh_b}"
    # TODO determine blur sizes rather than hardcode
    etac_blur = "0" if do_blur else "4 8"
    h_cmd = f"""
        cd {group_dir}
        3dttest++ \\
            -paired \\
            -mask {intx_mask} \\
            -prefix {final_file} \\
            -prefix_clustsim {final_file}_clustsim \\
            -ETAC \\
            -ETAC_blur {etac_blur} \\
            -ETAC_opt NN=2:sid=2:hpow=0:pthr=0.01,0.005,0.002,0.001:name=etac \\
            -setA {beh_a} \\
            {" ".join(set_a)} \\
            -setB {beh_b} \\
            {" ".join(set_b)}
    """
    etac_script = os.path.join(group_dir, f"{final_file}.sh")
    with open(etac_script, "w") as script:
        script.write(h_cmd)

    # run if needed
    etac_file = os.path.join(
        group_dir, f"{final_file}_clustsim.etac.ETACmask.global.2sid.5perc.nii.gz"
    )
    if not os.path.exists(etac_file):
        print(f"\nRunning ETAC script {etac_script}")
        _, _ = submit.submit_hpc_sbatch(h_cmd, 20, 4, 10, "taskETAC", group_dir)

    # check for output, return
    assert os.path.exists(
        etac_file
    ), f"ERROR: failed to write {etac_file}, check resources.afni.group.task_etac."
    group_data["behAB-etac"] = etac_file
    return group_data
