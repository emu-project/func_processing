"""Functions to submit Bash commands as subprocesses.

Submit bash commands as a subprocess, either on the same
node (submit_hpc_subprocess) or on a scheduled node
(submit_hpc_sbatch). Used for wrapping AFNI and c3d
commands.
"""
import subprocess
import os


def submit_hpc_subprocess(bash_command):
    """Submit quick job as subprocess.

    Run a quick job as a subprocess and capture stdout/err. Use
    for AFNI and c3d commands.

    Parameters
    ----------
    bash_command : str
        Bash syntax, to be executed

    Returns
    -------
    (job_out, job_err) : tuple of str
        job_out = subprocess stdout

        job_err = subprocess stderr

    Example
    -------
    submit_hpc_subprocess("afni -ver")

    """
    h_cmd = f"""
        module load afni-20.2.06
        module load c3d-1.0.0-gcc-8.2.0
        {bash_command}
    """
    h_sp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
    job_out, job_err = h_sp.communicate()
    h_sp.wait()
    return (job_out, job_err)


def submit_hpc_sbatch(
    command, wall_hours, mem_gig, num_proc, job_name, out_dir, env_input=None
):
    """Submit job to slurm scheduler (sbatch).

    Sbatch submit a larger job with scheduled resources. Waits for
    job_name to no longer be found in squeue. Stderr/out written to
    out_dir/sbatch_<job_name>.err/out. Supports AFNI and c3d commands.

    Parameters
    ----------
    command : str
        Bash code to be scheduled

    wall_hours : int
        number of desired walltime hours

    mem_gig : int
        amount of desired RAM

    num_proc : int
        number of desired processors

    job_name : str
        job name

    out_dir : str
        location for <job_name>.err/out

    env_input : dict
        user-specified environment for certain software (e.g. fMRIprep)

    Returns
    -------
    (job_name, job_id) : tuple of str
        job_name = scheduled job name

        job_id = scheduled job ID

    Example
    -------
    submit_hpc_sbatch("afni -ver")
    """
    sbatch_job = f"""
        sbatch \
        -J {job_name} \
        -t {wall_hours}:00:00 \
        --cpus-per-task={num_proc} \
        --mem-per-cpu={mem_gig}000 \
        -p IB_44C_512G \
        -o {out_dir}/{job_name}.out \
        -e {out_dir}/{job_name}.err \
        --account iacc_madlab --qos pq_madlab \
        --wait \
        --wrap="module load afni-20.2.06
            module load c3d-1.0.0-gcc-8.2.0
            {command}
        "
    """
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    sbatch_response = subprocess.Popen(
        sbatch_job, shell=True, stdout=subprocess.PIPE, env=env_input
    )
    job_id = sbatch_response.communicate()[0].decode("utf-8")
    return (job_name, job_id)
