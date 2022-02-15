"""Functions for making various masks.

Notes
-----
Requires "submit" module at same level.
"""
import os
from . import submit


def make_intersect_mask(work_dir, subj_num, afni_data):
    """Make EPI-struct intersection mask.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
     afni_data : dict
        should contain smoothed data from process.blur_epi

    Returns
    -------
    afni_data : dict
        updated with mask key "mask-int"

    Notes
    -----
    Requires afni_data["epi-blur*"] and afni_data["mask-brain"].
    """

    # get list of smoothed/blurred EPI data, determine mask strings
    num_epi = len([y for x, y in afni_data.items() if "epi-blur" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-blur?'] not found. Check resources.afni.process.blur_epi"

    assert afni_data[
        "mask-brain"
    ], "ERROR: afni_data['mask-brain'] not found. Check resources.afni.copy.copy_data."

    epi_list = [x for k, x in afni_data.items() if "epi-blur" in k]
    brain_mask = afni_data["mask-brain"]
    # intersect_mask = brain_mask.replace("desc-brain", "desc-intersect")
    sess = brain_mask.split("ses-")[1].split("/")[0]
    file_name = os.path.basename(brain_mask)
    file_path = os.path.dirname(brain_mask)
    subj, _, space, cohort, res, _, suff = file_name.split("_")
    intersect_mask = (
        f"{file_path}/{subj}_ses-{sess}_{space}_{cohort}_{res}_desc-intersect_{suff}"
    )

    if not os.path.exists(intersect_mask):

        # automask across all runs
        for run_file in epi_list:
            out_file = "tmp_mask.sub".join(run_file.rsplit("sub", 1))
            if not os.path.exists(out_file):
                print(f"Making {out_file} ...")
                h_cmd = f"""
                    3dAutomask -prefix {out_file} {run_file}
                """
                h_out, h_err = submit.submit_hpc_subprocess(h_cmd)

        # combine run masks, make inter mask
        print("Making intersection mask ...")
        h_cmd = f"""
            cd {work_dir}/func

            3dmask_tool \
                -inputs tmp_mask.*.nii.gz \
                -union \
                -prefix tmp_mask_allRuns.nii.gz

            3dmask_tool \
                -input tmp_mask_allRuns.nii.gz {brain_mask} \
                -inter \
                -prefix {intersect_mask}
        """
        job_name, job_id = submit.submit_hpc_sbatch(
            h_cmd, 1, 1, 1, f"{subj_num}uni", f"{work_dir}/sbatch_out"
        )
        print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

    # fill dict
    assert os.path.exists(
        intersect_mask
    ), f"{intersect_mask} failed to write, check resources.afni.masks.make_intersect_mask."
    afni_data["mask-int"] = intersect_mask

    return afni_data


def make_tissue_masks(work_dir, subj_num, afni_data, thresh=0.5):
    """Make tissue class masks.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
    afni_data : dict
        afni dictionary used for passing files
    thresh : float [default=0.5]
        value for thresholding probseg files

    Returns
    -------
    afni_data : dict
        updated with "mask-erodedGM", "mask-erodedWM" keys
        for eroded, binary gray and white matter masks

    Notes
    -----
    Requires afni_data["mask-prob"], afni_data["mask-brain"].
    """

    # determine GM, WM tissue list, mask string, set up switch
    # for mask naming
    num_prob = len([y for x, y in afni_data.items() if "mask-prob" in x])
    assert (
        num_prob > 0
    ), "ERROR: afni_data['mask-prob*'] not found. Check resources.afni.copy.copy_data."

    assert afni_data[
        "mask-brain"
    ], "ERROR: afni_data['mask-brain'] not found. Check resources.afni.copy.copy_data."

    tiss_list = [x for k, x in afni_data.items() if "mask-prob" in k]
    mask_str = afni_data["mask-brain"]
    switch_name = {
        "GM": mask_str.replace("desc-brain", "desc-GMe"),
        "WM": mask_str.replace("desc-brain", "desc-WMe"),
        "CSF": mask_str.replace("desc-brain", "desc-CSFe"),
    }

    # make eroded, binary tissue masks
    for tiss in tiss_list:

        # determine tissue type, mask name
        tiss_type = tiss.split("label-")[1].split("_")[0]
        mask_file = switch_name[tiss_type]

        # work
        if not os.path.exists(mask_file):
            tmp_file = "tmp_bin.sub".join(tiss.rsplit("sub", 1))
            print(f"Making binary tissue mask for {tiss} ...")
            h_cmd = f"""
                c3d \
                    {tiss} \
                    -thresh {thresh} 1 1 0 \
                    -o {tmp_file}

                3dmask_tool \
                    -input {tmp_file} \
                    -dilate_input -1 \
                    -prefix {mask_file}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 1, 1, f"{subj_num}tiss", f"{work_dir}/sbatch_out"
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # fill dict
        assert os.path.exists(
            mask_file
        ), f"{mask_file} failed to write, check resources.afni.masks.make_tissue_masks."
        afni_data[f"mask-eroded{tiss_type}"] = mask_file

    return afni_data


def make_minimum_masks(work_dir, subj_num, sess, task, afni_data):
    """Make a mask of where minimum signal exists in EPI space.

    Used to help with the scaling step, so low values do not
    bias the scale. Based off "3dTstat -min".

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
    sess : str
        BIDS session string (ses-A)
    task : str
        BIDS task string (task-test)
    afni_data : dict
        afni dictionary used for passing files

    Returns
    -------
    afni_dict : dict
        mask-min = mask of minimum value for task

    Notes
    -----
    Requires afni_data["epi-preproc*"], afni_data["mask-brain"].
    """

    # make masks of voxels where some data exists (mask_min)
    num_epi = len([y for x, y in afni_data.items() if "epi-preproc" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-blur?'] not found. Check resources.afni.copy.copy_data"

    assert afni_data[
        "mask-brain"
    ], "ERROR: afni_data['mask-brain'] not found. Check resources.afni.copy.copy_data."

    epi_pre = [x for k, x in afni_data.items() if "epi-preproc" in k]
    mask_str = afni_data["mask-brain"]
    mask_min = mask_str.replace("desc-brain", "desc-minval")
    mask_min = mask_min.replace(f"_{sess}", f"_{sess}_{task}")

    if not os.path.exists(mask_min):
        min_list = []
        for run in epi_pre:
            tmp_min_file = "tmp_mask_min.sub".join(run.rsplit("sub", 1))
            min_list.append(tmp_min_file)
            if not os.path.exists(tmp_min_file):
                tmp_bin_file = "tmp_mask_bin.sub".join(run.rsplit("sub", 1))
                print("Making various tmp_masks ...")
                h_cmd = f"""
                    3dcalc \
                        -overwrite \
                        -a {run} \
                        -expr 1 \
                        -prefix {tmp_bin_file}

                    3dTstat \
                        -min \
                        -prefix {tmp_min_file} \
                        {tmp_bin_file}
                """
                h_out, h_err = submit.submit_hpc_subprocess(h_cmd)

        print("Making minimum value mask ...")
        h_cmd = f"""
            cd {work_dir}/func

            3dMean \
                -datum short \
                -prefix tmp_mask_mean_{task}.nii.gz \
                {" ".join(min_list)}

            3dcalc \
                -a tmp_mask_mean_{task}.nii.gz \
                -expr 'step(a-0.999)' \
                -prefix {mask_min}
        """
        job_name, job_id = submit.submit_hpc_sbatch(
            h_cmd, 1, 1, 1, f"{subj_num}min", f"{work_dir}/sbatch_out"
        )
        print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

    assert os.path.exists(
        mask_min
    ), f"{mask_min} failed to write, check resources.afni.masks.make_minimum_masks."
    afni_data["mask-min"] = mask_min

    return afni_data
