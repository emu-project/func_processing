"""Functions for running fMRIprep.

Run FreeSurfer and fMRIprep.
"""

# %%
import os
import sys

resource_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(resource_dir)

from afni import submit


# %%
def run_freesurfer(subj, subj_t1, freesurfer_dir, work_dir):
    """Run FreeSurfer.

    Convert the subject's T1w file into mgz format and place
    in required location. Then run FreeSurfer.

    While 4 cpus is default for -parallel, -openmp supplied
    for ease of increasing resources. Make sure to update
    submit.submit_hpc_sbatch usage as well.

    Parameters
    ----------
    subj : str
        BIDS subject string
    subj_t1 : str
        path to subject's T1w file
    freesurfer_dir : str
        path to derivatives/freesurfer
    work_dir : str
        path to working/scratch/fmriprep/subj
    """
    subj_num = subj.split("-")[1]
    h_cmd = f"""
        module load freesurfer-7.1

        mri_convert {subj_t1} {freesurfer_dir}/{subj}/mri/orig/001.mgz
        recon-all \
            -subjid {subj} \
            -all \
            -sd {freesurfer_dir} \
            -parallel \
            -openmp 4
    """
    print(f"FreeSurfer command :\n\t {h_cmd}")
    _, _ = submit.submit_hpc_sbatch(h_cmd, 10, 4, 4, f"fs{subj_num}", work_dir)


# %%
def run_fmriprep(subj, scratch_deriv, scratch_dset, sing_img, tplflow_dir, fs_license):
    """Run fMRIprep.

    Utilize singularity image of nipreps/fmriprep. The spaces
    is currently hardcoded for the EMU project. Also references
    the FreeSurfer priors that should have previously been
    generated.

    Parameters
    ----------
    subj : str
        BIDS subject string
    scratch_deriv : str
        path to /scratch/foo/derivatives
    scratch_dset : str
        path to /scratch/foo/dset
    sing_img : str
        path to fmriprep singularity image
    tplflow_dir : str
        path to templateflow directory
    fs_license : str
        path to FreeSurfer license
    """
    # set up paths
    subj_num = subj.split("-")[1]
    fs_dir = os.path.join(scratch_deriv, "freesurfer")
    work_dir = os.path.join(scratch_deriv, "work", subj)
    bids_dir = os.path.join(work_dir, "bids_layout")

    # set up environment for HPC issues
    merged_env = os.environ
    env = {
        "TMPDIR": "/scratch/madlab/temp/",
        "SINGULARITYENV_TEMPLATEFLOW_HOME": tplflow_dir,
    }
    merged_env.update(env)

    # write, submit command
    h_cmd = f"""
        singularity run --cleanenv \
            --bind {scratch_dset}:/data \
            --bind {scratch_deriv}:/out \
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
    _, _ = submit.submit_hpc_sbatch(
        h_cmd, 20, 4, 4, f"fp{subj_num}", work_dir, merged_env
    )
