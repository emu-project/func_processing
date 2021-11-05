"""Run ASHS to segment hippocampal subfields."""
# %%
import os
import sys

resource_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(resource_dir)

from afni import submit


# %%
def run_ashs(
    anat_dir, deriv_dir, atlas_dir, sing_img, subj, t1_file, t2_file, atlas_str
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

    Returns
    -------
    list
        ASHS output, contents of deriv_dir/final.
    """
    final_dir = os.path.join(deriv_dir, "final")
    if not os.path.exists(
        os.path.join(final_dir, f"{subj}_left_lfseg_corr_usegray.nii.gz")
    ):
        subj_num = subj.split("-")[1]
        h_cmd = f"""
            module load singularity-3.8.2
            singularity run --cleanenv \
                --bind {anat_dir}:/data_dir \
                --bind {deriv_dir}:/work_dir \
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
    return os.listdir(final_dir)


# %%
