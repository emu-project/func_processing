"""Title.

Desc.
"""

# %%
import os
import sys
import glob

resource_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(resource_dir)

from afni import submit


# %%
def run_fmriprep(subj, deriv_dir, dset_dir, work_dir, sing_img, tpflow_dir, fs_license):
    """Title.

    Parameters
    ----------
    sing_img : str
        /home/data/madlab/singularity-images/nipreps_fmriprep_20.2.3.sif

    Desc.
    """
    subj_num = subj.split("-")[1]
    fs_dir = os.path.join(deriv_dir, "freesurfer", subj)

    h_cmd = f"""
        module load singularity-3.8.2

        # set global vars for fmriprep
        export SINGULARITYENV_TEMPLATEFLOW_HOME={tpflow_dir}
        export FS_LICENSE={fs_license}

        # HPC hack
        export TMPDIR=/scratch/madlab/temp
        cd /

        singularity run --cleanenv {sing_img} \
            {dset_dir} \
            {deriv_dir} \
            participant \
            --work-dir {work_dir} \
            --participant-label {subj_num} \
            --skull-strip-template MNIPediatricAsym:cohort-5 \
            --output-spaces MNIPediatricAsym:cohort-5:res-2 \
            --fs-license-file $FS_LICENSE \
            --fs-subjects-dir {fs_dir} \
            --skip-bids-validation \
            --nthreads 4 \
            --omp-nthreads 4 \
            --clean-workdir \
            --stop-on-first-crash
    """
    print(f"fMRIprep command :\n\t {h_cmd}")
    job_name, job_id = submit.submit_hpc_sbatch(
        h_cmd, 10, 4, 4, f"fprep{subj_num}", work_dir
    )
    t1_found = glob.glob(
        f"{deriv_dir}/fmriprep/{subj}/**/*desc-preproc_T1w.nii.gz", recursive=True
    )
    assert t1_found, "fMRIprep failed, check resources.fmriprep.fmriprep.run_fmriprep."
