"""Functions for making various masks."""
import os
from . import submit


def make_intersect_mask(
    work_dir,
    subj_num,
    afni_data,
    sess,
    task,
    do_blur,
    c_frac="0.5",
    nbr_type="NN2",
    n_nbr=17,
):
    """Make EPI-struct intersection mask.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A

    subj_num : int/str
        subject identifier, for sbatch job name

     afni_data : dict
        contains keys pointing to required files

        required keys:

        - [mask-brain] = anatomic brain mask

        conditionally required keys:

        - do_blur = T when [epi-blur<1..N>] = list of blurred EPI files

        - do_blur = F when [epi-blur<1..N>] = list of fmriprep preprocessed files

    sess : str
        BIDS session string (ses-S1)

    task : str
        BIDS task string (task-study)

    do_blur : bool
        [T/F] whether to blur as part of pre-processing

    c_frac : str, float
        input for 3dAutomask -clfrac option

    nbr_type : str
        3dAutomask nearest neighbors argument

    n_nbr : int
        input for 3dAutomask -nbhrs option

    Returns
    -------
    afni_data : dict
        updated with files

        added afni_data keys:

        - [mask-int] = subject epi-anat intersection mask
    """
    # get required EPI, mask files
    if do_blur:
        num_epi = len([y for x, y in afni_data.items() if "epi-blur" in x])
        assert (
            num_epi > 0
        ), "ERROR: afni_data['epi-blur?'] not found. Check resources.afni.process.blur_epi"
        epi_list = [x for k, x in afni_data.items() if "epi-blur" in k]
    else:
        num_epi = len([y for x, y in afni_data.items() if "epi-preproc" in x])
        assert (
            num_epi > 0
        ), "ERROR: afni_data['epi-preproc?'] not found. Check resources.afni.copy.copy_data."
        epi_list = [x for k, x in afni_data.items() if "epi-preproc" in k]

    assert afni_data[
        "mask-brain"
    ], "ERROR: afni_data['mask-brain'] not found. Check resources.afni.copy.copy_data."
    brain_mask = afni_data["mask-brain"]

    # set up
    file_name = os.path.basename(brain_mask)
    file_path = os.path.dirname(brain_mask)
    subj, _, space, cohort, res, _, suff = file_name.split("_")
    intersect_mask = (
        f"{file_path}/{subj}_{sess}_{task}_{space}_{cohort}_{res}_desc-intersect_{suff}"
    )

    # work
    if not os.path.exists(intersect_mask):

        # automask across all runs
        for run_file in epi_list:
            out_file = "tmp_mask.sub".join(run_file.rsplit("sub", 1))
            if not os.path.exists(out_file):
                print(f"Making {out_file} ...")
                h_cmd = f"""
                    3dAutomask \
                        -clfrac {c_frac} \
                        -{nbr_type} \
                        -nbhrs {n_nbr} \
                        -prefix {out_file} \
                        {run_file}
                """
                _, _ = submit.submit_hpc_subprocess(h_cmd)

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
        contains keys pointing to required files

        required keys:

        - [mask-prob<GM|CSF|WM>] = tissue probability masks

        - [mask-brain] = anatomic brain mask

    thresh : float [default=0.5]
        value for thresholding probseg files

    Returns
    -------
    afni_data : dict
        adds keys for generated files

        added afni_data keys:

        - [mask-eroded<GM|WM|CSF>] = eroded gray, white matter, CSF masks
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

        # determine tissue type, mask name, skip GM masks
        tiss_type = tiss.split("label-")[1].split("_")[0]
        if tiss_type == "GM":
            continue

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


def make_minimum_masks(work_dir, subj_num, task, afni_data):
    """Make a mask of where minimum signal exists in EPI space.

    Used to help with the scaling step, so low values do not
    bias the scale. Based off "3dTstat -min".

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A

    subj_num : int/str
        subject identifier, for sbatch job name

    task : str
        BIDS task string (task-test)

    afni_data : dict
        contains keys pointing to required files

        required keys:

        - [epi-preproc<1..N>] = fmriprep pre-processed files

        - [mask-brain] = anatomic brain mask

    Returns
    -------
    afni_dict : dict
        adds keys for generated files

        added afni_data keys:

        - [mask-min] = mask of minimum value for task
    """
    # make masks of voxels where some data exists (mask_min)
    num_epi = len([y for x, y in afni_data.items() if "epi-preproc" in x])
    assert (
        num_epi > 0
    ), "ERROR: afni_data['epi-preproc?'] not found. Check resources.afni.copy.copy_data"

    assert afni_data[
        "mask-brain"
    ], "ERROR: afni_data['mask-brain'] not found. Check resources.afni.copy.copy_data."

    epi_pre = [x for k, x in afni_data.items() if "epi-preproc" in k]
    mask_min = afni_data["mask-brain"]
    rep_dict = {"desc-brain": "desc-minval", "_space": f"_{task}_space"}
    for key, value in rep_dict.items():
        mask_min = mask_min.replace(key, value)

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
                _, _ = submit.submit_hpc_subprocess(h_cmd)

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
