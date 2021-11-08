"""Run ASHS to segment hippocampal subfields."""
# %%
import os
import sys
import shutil

resource_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(resource_dir)

from afni import submit


# %%
def run_ashs(
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
    """Run automatic hippocampal subfield segmentation.

    Use singularity image of docker://nmuncy/ashs to generate
    HC subfield labels.

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

    Raises
    ------
    FileNotFoundError
        If ASHS is run but files are not detected in work_dir/final.

    Returns
    -------
    list
        final ASHS files
    """
    # set up
    for h_dir in [deriv_dir, work_dir]:
        if not os.path.exists(h_dir):
            os.makedirs(h_dir)

    # run ASHS if needed
    if not os.path.exists(
        os.path.join(deriv_dir, f"{subj}_left_lfseg_corr_usegray.nii.gz")
    ):
        subj_num = subj.split("-")[1]
        h_cmd = f"""
            module load singularity-3.8.2
            singularity run --cleanenv \
                --bind {anat_dir}:/data_dir \
                --bind {work_dir}:/work_dir \
                --bind {atlas_dir}:/atlas_dir \
                {sing_img} \
                -i {subj} \
                -g {t1_file} \
                -f {t2_file} \
                -a {atlas_str}
        """
        job_name, job_id = submit.submit_hpc_sbatch(
            h_cmd, 2, 4, 6, f"ashs{subj_num}", deriv_dir
        )
        print(f"""Finished {job_name} as job {job_id.split(" ")[-1]}""")

        # move relevant files
        ashs_out = [x for x in os.listdir(os.path.join(work_dir, "final"))]
        if len(ashs_out) == 0:
            raise FileNotFoundError(f"No files found in {work_dir}/final.")
        for ashs_file in ashs_out:
            shutil.copyfile(
                os.path.join(work_dir, "final", ashs_file),
                os.path.join(deriv_dir, ashs_file),
            )

    # clean up
    if os.path.exists(
        os.path.join(deriv_dir, f"{subj}_left_lfseg_corr_usegray.nii.gz")
    ) and os.path.exists(
        os.path.join(work_dir, "final", f"{subj}_left_lfseg_corr_usegray.nii.gz")
    ):
        shutil.rmtree(work_dir)

    # return list of ASHS output
    return os.listdir(deriv_dir)


# %%
