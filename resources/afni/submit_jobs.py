"""Functions to submit Bash commands as subprocesses.

Desc.

"""
import subprocess
import time


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

    Example
    -------

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


def submit_hpc_sbatch(command, wall_hours, mem_gig, num_proc, job_name, out_dir):
    """Submit job to slurm scheduler (sbatch).

    Sbatch submit a larger job with scheduled resources. Waits for
    job_name to no longer be found in squeue. Stderr/out written to
    out_dir/sbatch_<job_name>.err/out. Supports AFNI commands only

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
        location for sbatch_<job_name>.err/out

    Returns
    -------

    Example
    -------

    """
    # set stdout/err string, submit job
    sbatch_job = f"""
        sbatch \
        -J {job_name} \
        -t {wall_hours}:00:00 \
        --mem={mem_gig}000 \
        --ntasks-per-node={num_proc} \
        -p IB_44C_512G \
        -o {out_dir}/sbatch_{job_name}.out \
        -e {out_dir}/sbatch_{job_name}.err \
        --account iacc_madlab --qos pq_madlab \
        --wrap="module load afni-20.2.06
            {command}
        "
    """
    sbatch_response = subprocess.Popen(sbatch_job, shell=True, stdout=subprocess.PIPE)
    job_id = sbatch_response.communicate()[0].decode("utf-8")
    print(f"Submitted {job_name} as {job_id}")

    # wait (forever) until job finishes
    while_count = 0
    continue_status = True
    while continue_status:

        check_cmd = "squeue -u $(whoami)"
        sq_check = subprocess.Popen(check_cmd, shell=True, stdout=subprocess.PIPE)
        out_lines = sq_check.communicate()[0]
        b_decode = out_lines.decode("utf-8")

        if job_name not in b_decode:
            continue_status = False
        else:
            while_count += 1
            print(f"Wait count for {job_name}: {while_count}")
            time.sleep(3)
