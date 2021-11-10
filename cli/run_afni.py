#!/usr/bin/env python

"""Title.

Desc.

"""
# %%
import os
import sys
import json
import fnmatch
import glob
from datetime import datetime
import textwrap
import subprocess


# %%
def submit_jobs(
    deriv_dir, subj, sess, task, decon_json, tplflow_str, code_dir, slurm_dir
):
    """Title.

    Desc.
    """

    subj_num = subj.split("-")[-1]

    h_cmd = f"""\
        #!/bin/env {sys.executable}

        #SBATCH --job-name=p{subj_num}
        #SBATCH --output={slurm_dir}/out_{subj_num}.txt
        #SBATCH --time=10:00:00
        #SBATCH --mem=4000
        #SBATCH --partition=IB_44C_512G
        #SBATCH --account=iacc_madlab
        #SBATCH --qos=pq_madlab

        import sys
        sys.path.append("{code_dir}")
        from workflow import control_afni

        afni_data = control_afni.control_preproc(
            "{deriv_dir}",
            "{subj}",
            "{sess}",
            "{task}",
            "{tplflow_str}",
        )

        afni_data = control_afni.control_deconvolution(
            "{deriv_dir}",
            "{subj}",
            "{sess}",
            afni_data,
            "{decon_json}",
        )

        print(f"Finished with \\n {{afni_data}}")
    """
    cmd_dedent = textwrap.dedent(h_cmd)
    py_script = os.path.join(slurm_dir, f"preproc_decon_{subj_num}.py")
    with open(py_script, "w") as ps:
        ps.write(cmd_dedent)

    sbatch_response = subprocess.Popen(
        f"sbatch {py_script}", shell=True, stdout=subprocess.PIPE
    )
    h_out, h_err = sbatch_response.communicate()
    return (h_out, h_err)


# %%
def main():

    # For testing
    proj_dir = "/home/data/madlab/McMakin_EMUR01"
    tplflow_str = "space-MNIPediatricAsym_cohort-5_res-2"
    sess = "ses-S2"
    task = "task-test"
    timing_dir = "/home/nmuncy/compute/func_processing/tests/"
    code_dir = "/home/nmuncy/compute/func_processing"

    # set up
    deriv_dir = os.path.join(proj_dir, "derivatives")
    prep_dir = os.path.join(deriv_dir, "fmriprep")
    afni_dir = os.path.join(deriv_dir, "afni")

    # list subjects in fmriprep dir
    subj_list_all = [
        x
        for x in os.listdir(prep_dir)
        if fnmatch.fnmatch(x, "sub-*") and not fnmatch.fnmatch(x, "*html")
    ]
    subj_list_all.sort()

    # make list of subjects who have fmriprep output and are
    # missing afni output
    subj_list = []
    decon_dict = {}
    for subj in subj_list_all[1:2]:

        # check for fmriprep output
        anat_check = glob.glob(
            f"{prep_dir}/{subj}/**/*_{tplflow_str}_desc-preproc_T1w.nii.gz",
            recursive=True,
        )
        func_check = glob.glob(
            f"{prep_dir}/{subj}/**/*{task}*{tplflow_str}_desc-preproc_bold.nii.gz",
            recursive=True,
        )

        # check whether each planned decon exists
        afni_check = []
        decon_glob = glob.glob(os.path.join(timing_dir, f"{subj}*.json"))
        assert decon_glob, f"No decon plan found for {subj} in {timing_dir}"
        with open(decon_glob[0]) as jf:
            decon_plan = json.load(jf)
        for decon_str in decon_plan.keys():
            afni_check.append(
                os.path.exists(
                    os.path.join(
                        afni_dir,
                        subj,
                        sess,
                        f"decon_{task}_{decon_str}_stats_REML+tlrc.HEAD",
                    )
                )
            )

        # append subj_list if fmriprep data exists and a planned
        # decon is missing
        if anat_check and func_check and False in afni_check:
            subj_list.append(subj)
            decon_dict[subj] = decon_glob[0]

    # do preproc/decon for each subject
    current_time = datetime.now()
    slurm_dir = os.path.join(
        afni_dir,
        f"""slurm_out/afni_{current_time.strftime("%y-%m-%d_%H:%M")}""",
    )
    if not os.path.exists(slurm_dir):
        os.makedirs(slurm_dir)

    for subj in subj_list:
        submit_jobs(
            deriv_dir,
            subj,
            sess,
            task,
            decon_dict[subj],
            tplflow_str,
            code_dir,
            slurm_dir,
        )


if __name__ == "__main__":
    main()
