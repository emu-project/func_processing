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
    epi_list = [x for k, x in afni_data.items() if "epi-blur" in k]
    brain_mask = afni_data["mask-brain"]
    intersect_mask = brain_mask.replace("desc-brain", "desc-intersect")

    if not os.path.exists(os.path.join(work_dir, intersect_mask)):

        # automask across all runs
        for run_file in epi_list:
            out_file = f"""func/tmp_mask.{run_file.split("/")[1]}"""
            if not os.path.exists(os.path.join(work_dir, out_file)):
                print("Making EPI mask ...")
                h_cmd = f"""
                    cd {work_dir}
                    3dAutomask -prefix {out_file} {run_file}
                """
                h_out, h_err = submit.submit_hpc_subprocess(h_cmd)

        # combine run masks, make inter mask
        print("Making intersection mask ...")
        h_cmd = f"""
            cd {work_dir}

            3dmask_tool \
                -inputs func/tmp_mask.*.nii.gz \
                -union \
                -prefix func/tmp_mask_allRuns.nii.gz

            3dmask_tool \
                -input func/tmp_mask_allRuns.nii.gz {brain_mask} \
                -inter \
                -prefix {intersect_mask}
        """
        job_name, job_id = submit.submit_hpc_sbatch(
            h_cmd, 1, 1, 1, f"{subj_num}uni", work_dir
        )
        print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

    # fill dict
    assert os.path.exists(
        os.path.join(work_dir, intersect_mask)
    ), f"{intersect_mask} failed to write, check resources.afni.masks.make_intersect_mask."
    afni_data["mask-int"] = intersect_mask

    return afni_data


def make_tissue_masks(work_dir, subj_num, afni_data, thresh=0.5):
    """Make tissue masks.

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
    tiss_list = [x for k, x in afni_data.items() if "mask-prob" in k]
    mask_str = afni_data["mask-brain"]
    switch_name = {
        "GM": mask_str.replace("desc-brain", "desc-GMe"),
        "WM": mask_str.replace("desc-brain", "desc-WMe"),
    }

    # make eroded, binary tissue masks
    for tiss in tiss_list:

        # determine tissue type, mask name
        tiss_type = tiss.split("label-")[1].split("_")[0]
        mask_file = switch_name[tiss_type]

        # work
        if not os.path.exists(os.path.join(work_dir, mask_file)):
            tmp_file = f"""anat/tmp_bin_{tiss.split("/")[1]}"""
            print(f"Making binary tissue mask for {tiss} ...")
            h_cmd = f"""
                cd {work_dir}

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
                h_cmd, 1, 1, 1, f"{subj_num}tiss", work_dir
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # fill dict
        assert os.path.exists(
            os.path.join(work_dir, mask_file)
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
    epi_pre = [x for k, x in afni_data.items() if "epi-preproc" in k]

    mask_str = afni_data["mask-brain"]
    mask_min = mask_str.replace("desc-brain", "desc-minval")
    mask_min = mask_min.replace(sess, f"{sess}_{task}")

    if not os.path.exists(os.path.join(work_dir, mask_min)):
        min_list = []
        for run in epi_pre:
            tmp_min_file = f"""func/tmp_mask_min.{run.split("/")[1]}"""
            min_list.append(tmp_min_file)
            if not os.path.exists(os.path.join(work_dir, f"tmp_mask_min.{run}")):
                tmp_bin_file = f"""func/tmp_mask_bin.{run.split("/")[1]}"""
                print("Making various masks ...")
                h_cmd = f"""
                    cd {work_dir}

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
            cd {work_dir}

            3dMean \
                -datum short \
                -prefix func/tmp_mask_mean_{task}.nii.gz \
                {" ".join(min_list)}

            3dcalc \
                -a func/tmp_mask_mean_{task}.nii.gz \
                -expr 'step(a-0.999)' \
                -prefix {mask_min}
        """
        job_name, job_id = submit.submit_hpc_sbatch(
            h_cmd, 1, 1, 1, f"{subj_num}min", work_dir
        )
        print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

    assert os.path.exists(
        os.path.join(work_dir, mask_min)
    ), f"{mask_min} failed to write, check resources.afni.process.scale_epi."
    afni_data["mask-min"] = mask_min

    return afni_data
