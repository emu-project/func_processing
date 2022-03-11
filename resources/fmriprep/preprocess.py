"""Functions for running fMRIprep.

Run FreeSurfer and fMRIprep.
"""

# %%
import os
import sys
import glob

resource_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(resource_dir)

from afni import submit


# %%
def run_freesurfer(subj, subj_t1, freesurfer_dir, scratch_dir):
    """Run FreeSurfer.

    Parameters
    ----------
    subj : str
        BIDS subject string
    subj_t1 : str
        path to subject's T1w file
    freesurfer_dir : str
        path to derivatives/freesurfer
    scratch_dir : str
        path to working/scratch directory
    """
    subj_num = subj.split("-")[1]
    h_cmd = f"""
        module load freesurfer-7.1

        # I find generating the 001.mgz to be a bit more stable
        # than the "recon-all -i" option
        mkdir -p {freesurfer_dir}/{subj}/mri/orig
        mri_convert {subj_t1} {freesurfer_dir}/{subj}/mri/orig/001.mgz

        recon-all \
            -subjid {subj} \
            -all \
            -sd {freesurfer_dir} \
            -parallel \
            -openmp 4
    """
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 10, 4, 4, f"fs{subj_num}", scratch_dir
    )
    check_file = os.path.join(freesurfer_dir, subj, "mri/aparc+aseg.mgz")
    assert os.path.exists(
        check_file
    ), f"FreeSurfer failed on {subj}, check resources.freesurfer.freesurfer.run_freesurfer."


# %%
def run_fmriprep(
    subj, deriv_dir, dset_dir, work_dir, sing_img, tplflow_dir, fs_license
):
    """Run fMRIprep.

    Utilize singularity image of nipreps/fmriprep

    Parameters
    ----------
    subj : str
        BIDS subject string
    deriv_dir : str
        path to project derivatives directory
    dset_dir : str
        path to project dset directory
    work_dir : str
        path to working/scratch directory
    sing_img : str
        path to fmriprep singularity image
    tplflow_dir : str
        path to templateflow directory
    fs_license : str
        path to FreeSurfer license
    """
    # set up paths
    subj_num = subj.split("-")[1]
    fs_dir = os.path.join(deriv_dir, "freesurfer", subj)
    bids_dir = os.path.join(deriv_dir, "scratch/bids_layout")

    # set up environment for HPC issues
    merged_env = os.environ
    env = {
        "TMPDIR": "/scratch/madlab/temp/",
        "SINGULARITYENV_TEMPLATEFLOW_HOME": tplflow_dir,
    }
    merged_env.update(env)

    h_cmd = f"""
        singularity run --cleanenv \
            --bind {dset_dir}:/data \
            --bind {deriv_dir}:/out \
            {sing_img} \
            /data \
            /out \
            participant \
            --work-dir {work_dir} \
            --participant-label {subj_num} \
            --skull-strip-template MNIPediatricAsym:cohort-5 \
            --output-spaces MNIPediatricAsym:cohort-5:res-2 \
            --fs-license-file {fs_license} \
            --fs-subjects-dir {fs_dir} \
            --skip-bids-validation \
            --bids-database-dir {bids_dir} \
            --nthreads 4 \
            --omp-nthreads 4 \
            --stop-on-first-crash
    """
    print(f"fMRIprep command :\n\t {h_cmd}")
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 10, 4, 4, f"fprep{subj_num}", work_dir, merged_env
    )
    t1_found = glob.glob(
        f"{deriv_dir}/fmriprep/{subj}/**/*desc-preproc_T1w.nii.gz", recursive=True
    )
    assert t1_found, "fMRIprep failed, check resources.fmriprep.fmriprep.run_fmriprep."
