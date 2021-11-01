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
    """

    # get list of smoothed/blurred EPI data, determine mask strings
    epi_list = [x for k, x in afni_data.items() if "epi-blur" in k]
    brain_mask = afni_data["mask-brain"]
    intersect_mask = brain_mask.replace("desc-brain", "desc-intersect")

    if not os.path.exists(os.path.join(work_dir, intersect_mask)):

        # automask across all runs
        for run_file in epi_list:
            if not os.path.exists(os.path.join(work_dir, f"tmp_mask.{run_file}")):
                print("Making EPI mask ...")
                h_cmd = f"""
                    cd {work_dir}
                    3dAutomask -prefix tmp_mask.{run_file} {run_file}
                """
                h_out, h_err = submit.submit_hpc_subprocess(h_cmd)

        # combine run masks, make inter mask
        print("Making intersection mask ...")
        h_cmd = f"""
            cd {work_dir}

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
            h_cmd, 1, 1, 1, f"{subj_num}uni", work_dir
        )
        print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

    # fill dict
    if os.path.exists(os.path.join(work_dir, intersect_mask)):
        afni_data["mask-int"] = intersect_mask
    else:
        afni_data["mask-int"] = "Missing"

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
        should contain smoothed data from process.blur_epi
    thresh : float [default=0.5]
        value for thresholding probseg files

    Returns
    -------
    afni_data : dict
        updated with "mask-erodedGM", "mask-erodedWM" keys
        for eroded, binary masks
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
            print(f"Making binary tissue mask for {tiss} ...")
            h_cmd = f"""
                cd {work_dir}

                c3d \
                    {tiss} \
                    -thresh {thresh} 1 1 0 \
                    -o tmp_bin_{tiss}

                3dmask_tool \
                    -input tmp_bin_{tiss} \
                    -dilate_input -1 \
                    -prefix {mask_file}
            """
            job_name, job_id = submit.submit_hpc_sbatch(
                h_cmd, 1, 1, 1, f"{subj_num}tiss", work_dir
            )
            print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # fill dict
        if os.path.exists(os.path.join(work_dir, mask_file)):
            afni_data[f"mask-eroded{tiss_type}"] = mask_file
        else:
            afni_data[f"mask-eroded{tiss_type}"] = "Missing"

    return afni_data
