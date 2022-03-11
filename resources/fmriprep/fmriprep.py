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
def run_fmriprep(
    subj, deriv_dir, dset_dir, work_dir, sing_img, tplflow_dir, fs_license
):
    """Title.

    Parameters
    ----------
    sing_img : str
        /home/data/madlab/singularity-images/nipreps_fmriprep_20.2.3.sif

    Desc.
    """

    # for testing
    subj = "sub-4146"
    deriv_dir = "/scratch/madlab/nate_test/derivatives"
    dset_dir = "/scratch/madlab/nate_test/dset"
    work_dir = "/scratch/madlab/nate_test/scratch/sub-4146"
    bids_dir = "/scratch/madlab/nate_test/scratch/bids_layout"
    sing_img = "/home/data/madlab/singularity-images/nipreps_fmriprep_20.2.3.sif"
    tplflow_dir = "/home/data/madlab/singularity-images/templateflow"
    fs_license = "/home/nmuncy/bin/licenses/fs_license.txt"

    subj_num = subj.split("-")[1]
    fs_dir = os.path.join(deriv_dir, "freesurfer", subj)

    h_cmd = f"""
        module load singularity-3.8.2

        # set templateflow
        export SINGULARITYENV_TEMPLATEFLOW_HOME={tplflow_dir}

        # HPC hack
        export TMPDIR=/scratch/madlab/temp
        cd /

        # --bids-database-dir {bids_dir} \
        # --skip-bids-validation \
        # --fs-subjects-dir {fs_dir} \

        singularity run --cleanenv \
            --bind $HOME/templateflow:{tplflow_dir} \
            {sing_img} \
            {dset_dir} \
            {deriv_dir} \
            participant \
            --work-dir {work_dir} \
            --participant-label {subj_num} \
            --skull-strip-template MNIPediatricAsym:cohort-5 \
            --output-spaces MNIPediatricAsym:cohort-5:res-2 \
            --fs-license-file {fs_license} \
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
