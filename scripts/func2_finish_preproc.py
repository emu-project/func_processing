# %%
"""Finish pre-processing on EPI data.

Copy relevant files from derivatives/fmriprep to derivatives/afni,
then blur and scale EPI data. Also creates EPI-T1 intersection
and tissue class masks.

Notes
-----
Requires AFNI and c3d.

Examples
--------
func2_finish_preproc.py \
    -p sub-4020 \
    -t test \
    -s sess-S2 \
    -n 3 \
    -d /scratch/madlab/emu_UNC/derivatives
"""

import os
import sys
import glob
import subprocess
import time
import fnmatch
import math
import shutil
from argparse import ArgumentParser
from func0_setup import _copyfile_patched


# %%
def func_sbatch(command, wall_hours, mem_gig, num_proc, h_str, work_dir):
    """Submit job to slurm as subprocess, wait for job to finish

    Parameters
    ----------
    command : str
        bash code to be scheduled
    wall_hours : int
        number of desired walltime hours
    mem_gig : int
        amount of desired RAM
    num_proc : int
        number of desired processors
    h_str : str
        job name
    work_dir : str
        location for sbatch_writeOut_err/out

    Returns
    -------
    str
        exit message that job finished

    """
    # set stdout/err string, submit job
    full_name = f"{work_dir}/sbatch_writeOut_{h_str}"
    sbatch_job = f"""
        sbatch \
        -J {h_str} -t {wall_hours}:00:00 --mem={mem_gig}000 --ntasks-per-node={num_proc} \
        -p IB_44C_512G -o {full_name}.out -e {full_name}.err \
        --account iacc_madlab --qos pq_madlab \
        --wrap="module load afni-20.2.06 \n {command}"
    """
    sbatch_response = subprocess.Popen(sbatch_job, shell=True, stdout=subprocess.PIPE)
    job_id = sbatch_response.communicate()[0]
    print(job_id, h_str, sbatch_job)

    # wait (forever) until job finishes
    while_count = 0
    break_status = False
    while not break_status:

        check_cmd = "squeue -u $(whoami)"
        sq_check = subprocess.Popen(check_cmd, shell=True, stdout=subprocess.PIPE)
        out_lines = sq_check.communicate()[0]
        b_decode = out_lines.decode("utf-8")

        if h_str not in b_decode:
            break_status = True
        else:
            while_count += 1
            print(f"Wait count for sbatch job {h_str}: {while_count}")
            time.sleep(3)

    print(f"Sbatch job {h_str} finished")


# %%
def copy_data(prep_dir, work_dir, subj, sess, task, num_runs):
    """Get relevant fMRIprep files, rename.

    Copies select fMRIprep files into AFNI format.

    Parameters
    ----------
    prep_dir : str
        /path/to/derivatives/fmriprep
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj : str
        sub-1234
    sess : str
        ses-A
    task : str
        test for task-test
    num_runs : int
        number of EPI runs

    Notes
    -----
    MRI output : structural
        struct_head+tlrc
        struct_mask+tlrc
        final_mask_WM_prob.nii.gz
        final_mask_WM_prob.nii.gz
    MRI output : functional
        run-?_<task>_preproc+tlrc
    file output : tsv
        run-?_motion_all.tsv
    """
    # set vars, dict
    # TODO receive tpl_ref str, rather than hardcode.
    tpl_ref = "space-MNIPediatricAsym_cohort-5_res-2"
    anat_str = f"{subj}_{sess}_{tpl_ref}"
    func_str = f"{subj}_{sess}_task-{task}"
    copy_dict = {
        "anat": {
            "tmp_struct_head.nii.gz": f"{anat_str}_desc-preproc_T1w.nii.gz",
            "tmp_struct_mask.nii.gz": f"{anat_str}_desc-brain_mask.nii.gz",
            "final_mask_GM_prob.nii.gz": f"{anat_str}_label-GM_probseg.nii.gz",
            "final_mask_WM_prob.nii.gz": f"{anat_str}_label-WM_probseg.nii.gz",
        },
        "func": {},
    }

    # add preproc bold, confound TS to copy_dicts
    for run in range(0, num_runs):
        h_run = f"run-{run+1}"

        copy_dict["func"][
            f"tmp_{h_run}_{task}_preproc.nii.gz"
        ] = f"{func_str}_{h_run}_{tpl_ref}_desc-preproc_bold.nii.gz"

        copy_dict["func"][
            f"{h_run}_motion_all.tsv"
        ] = f"{func_str}_{h_run}_desc-confounds_timeseries.tsv"

    # copy data
    for scan_type in copy_dict:
        source_dir = os.path.join(prep_dir, subj, sess, scan_type)
        for h_file in copy_dict[scan_type]:
            in_file = os.path.join(source_dir, copy_dict[scan_type][h_file])
            out_file = os.path.join(work_dir, h_file)
            if not os.path.exists(os.path.join(work_dir, h_file)):
                shutil.copyfile(in_file, out_file)

    # 3dcopy data
    tmp_list = [x for x in os.listdir(work_dir) if fnmatch.fnmatch(x, "tmp_*")]
    for tmp_file in tmp_list:
        in_file = os.path.join(work_dir, tmp_file)
        h_str = tmp_file.split(".")[0].split("_", 1)[1]
        out_file = os.path.join(work_dir, f"{h_str}+tlrc")
        if not os.path.exists(f"{out_file}.HEAD"):
            h_cmd = f"""
                module load afni-20.2.06
                3dcopy {in_file} {out_file} && rm {in_file}
            """
            h_cp = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
            h_cp.wait()


# %%
def mk_epi_list(work_dir):
    """Helper function to make list of EPI data"""
    epi_list = [
        x.split("_pre")[0]
        for x in os.listdir(work_dir)
        if fnmatch.fnmatch(x, "*preproc+tlrc.HEAD")
    ]
    epi_list.sort()
    return epi_list


# %%
def blur_epi(work_dir, subj_num, blur_mult=1.5):
    """Blur EPI data

    Blur pre-processed EPI runs.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
    blur-mult : int
        blur kernel multiplier (default = 1.5)
        e.g. vox=2, blur_mult=1.5, blur size is 3 (will round float up to nearest int)

    Notes
    -----
    MRI output : functional
        run-1_<task>_blur+tlrc
    """

    # get list of epi files
    epi_list = mk_epi_list(work_dir)

    # blur each
    for run in epi_list:
        if not os.path.exists(os.path.join(work_dir, f"{run}_blur+tlrc.HEAD")):

            # calc voxel dim i
            h_cmd = f"""
                module load afni-20.2.06
                3dinfo -dk {work_dir}/{run}_preproc+tlrc
            """
            h_gs = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
            h_gs_out = h_gs.communicate()[0]
            grid_size = h_gs_out.decode("utf-8").strip()
            blur_size = math.ceil(blur_mult * float(grid_size))

            # do blur
            h_cmd = f"""
                cd {work_dir}
                3dmerge \
                    -1blur_fwhm {blur_size} \
                    -doall \
                    -prefix {run}_blur \
                    {run}_preproc+tlrc
            """
            func_sbatch(h_cmd, 1, 1, 1, f"{subj_num}blur", work_dir)


# %%
def make_masks(work_dir, subj_num):
    """Make various masks.

    Make EPI-struct intersection and tissue masks.

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name

    Notes
    -----
    MRI output : structural
        mask_epi_anat+tlrc
        final_mask_WM_eroded+tlrc
        final_mask_GM_eroded+tlrc
    """

    # get list of EPI data
    epi_list = mk_epi_list(work_dir)

    if not os.path.exists(os.path.join(work_dir, "mask_epi_anat+tlrc.HEAD")):

        # automask across all runs
        for run in epi_list:
            if not os.path.exists(
                os.path.join(work_dir, f"tmp_mask.{run}_blur+tlrc.HEAD")
            ):
                h_cmd = f"""
                    module load afni-20.2.06
                    cd {work_dir}
                    3dAutomask -prefix tmp_mask.{run} {run}_blur+tlrc
                """
                h_mask = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
                h_mask.wait()

        # combine run masks, make inter mask
        h_cmd = f"""
            cd {work_dir}

            3dmask_tool \
                -inputs tmp_mask.*+tlrc.HEAD \
                -union \
                -prefix tmp_mask_allRuns

            3dmask_tool \
                -input tmp_mask_allRuns+tlrc struct_mask+tlrc \
                -inter \
                -prefix mask_epi_anat
        """
        func_sbatch(h_cmd, 1, 1, 1, f"{subj_num}uni", work_dir)

    # Make tissue-class masks
    tiss_list = ["WM", "GM"]
    for tiss in tiss_list:
        if not os.path.exists(
            os.path.join(work_dir, f"final_mask_{tiss}_eroded+tlrc.HEAD")
        ):
            h_cmd = f"""
                module load c3d-1.0.0-gcc-8.2.0
                cd {work_dir}

                c3d \
                    final_mask_{tiss}_prob.nii.gz \
                    -thresh 0.5 1 1 0 \
                    -o tmp_{tiss}_bin.nii.gz

                3dmask_tool \
                    -input tmp_{tiss}_bin.nii.gz \
                    -dilate_input -1 \
                    -prefix final_mask_{tiss}_eroded

                3drefit -space MNI final_mask_{tiss}_eroded+orig
                3drefit -view tlrc final_mask_{tiss}_eroded+orig
            """
            func_sbatch(h_cmd, 1, 1, 1, f"{subj_num}tiss", work_dir)


# %%
def scale_epi(work_dir, subj_num, task):
    """Scale EPI runs

    Parameters
    ----------
    work_dir : str
        /path/to/derivatives/afni/sub-1234/ses-A
    subj_num : int/str
        subject identifier, for sbatch job name
    task : str
        test for task-test

    Notes
    -----
    MRI output : structural
        <task>_minVal_mask+tlrc
    MRI output : functional
        run-?_<task>_scale+tlrc
    """

    # get epi list
    epi_list = mk_epi_list(work_dir)

    # make masks of voxels where some data exists
    # TODO update here for multiple phases/tasks
    for run in epi_list:
        if not os.path.exists(os.path.join(work_dir, f"tmp_{run}_mask+tlrc.HEAD")):
            h_cmd = f"""
                module load afni-20.2.06
                cd {work_dir}

                3dcalc \
                    -overwrite \
                    -a {run}_preproc+tlrc \
                    -expr 1 \
                    -prefix tmp_{run}_mask

                3dTstat \
                    -min \
                    -prefix tmp_{run}_min \
                    tmp_{run}_mask+tlrc
            """
            h_min = subprocess.Popen(h_cmd, shell=True, stdout=subprocess.PIPE)
            h_min.wait()

    # make masks of where some minimum value of data exists
    if not os.path.exists(os.path.join(work_dir, f"{task}_minVal_mask+tlrc.HEAD")):
        h_cmd = f"""
            cd {work_dir}

            3dMean \
                -datum short \
                -prefix tmp_mean_{task} \
                tmp_run-{{1..{len(epi_list)}}}_{task}_min+tlrc

            3dcalc \
                -a tmp_mean_{task}+tlrc \
                -expr 'step(a-0.999)' \
                -prefix {task}_minVal_mask
        """
        func_sbatch(h_cmd, 1, 1, 1, f"{subj_num}min", work_dir)

    # scale data timeseries
    # TODO update here for multiple phases/tasks
    for run in epi_list:
        if not os.path.exists(os.path.join(work_dir, f"{run}_scale+tlrc.HEAD")):
            h_cmd = f"""
                cd {work_dir}

                3dTstat -prefix tmp_tstat_{run} {run}_blur+tlrc

                3dcalc -a {run}_blur+tlrc \
                    -b tmp_tstat_{run}+tlrc \
                    -c {task}_minVal_mask+tlrc \
                    -expr 'c * min(200, a/b*100)*step(a)*step(b)' \
                    -prefix {run}_scale
            """
            func_sbatch(h_cmd, 1, 1, 1, f"{subj_num}scale", work_dir)


def get_args():
    """Get and parse arguments"""
    parser = ArgumentParser("Receive bash CLI args")
    requiredNamed = parser.add_argument_group("required named arguments")
    requiredNamed.add_argument(
        "-p", "--part-id", help="Participant ID (sub-1234)", type=str, required=True,
    )
    requiredNamed.add_argument(
        "-t",
        "--task-str",
        help="BIDS task-string (test, for task-test)",
        type=str,
        required=True,
    )
    requiredNamed.add_argument(
        "-s", "--sess-str", help="BIDS ses-string (ses-S2)", type=str, required=True,
    )
    requiredNamed.add_argument(
        "-n", "--num-runs", help="Number of EPI runs (int)", type=int, required=True,
    )
    requiredNamed.add_argument(
        "-d",
        "--deriv-dir",
        help="/path/to/project/derivatives",
        type=str,
        required=True,
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser


# %%
def main():
    """Move data through pre-processing - orchestrate functions."""

    # # For testing
    # proj_dir = "/scratch/madlab/emu_UNC"
    # prep_dir = os.path.join(proj_dir, "derivatives/fmriprep")
    # afni_dir = os.path.join(proj_dir, "derivatives/afni")

    # subj = "sub-4020"
    # sess = "ses-S2"
    # task = "test"
    # num_runs = 3

    # get passed arguments
    args = get_args().parse_args()
    subj = args.part_id
    sess = args.sess_str
    task = args.task_str
    num_runs = args.num_runs
    deriv_dir = args.deriv_dir

    # setup directories
    prep_dir = os.path.join(deriv_dir, "fmriprep")
    afni_dir = os.path.join(deriv_dir, "afni")
    work_dir = os.path.join(afni_dir, subj, sess)
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)

    # get fMRIprep data
    if not os.path.exists(os.path.join(work_dir, "struct_head+tlrc.HEAD")):
        copy_data(prep_dir, work_dir, subj, sess, task, num_runs)

    # blur data
    subj_num = subj.split("-")[-1]
    if not os.path.exists(os.path.join(work_dir, f"run-1_{task}_blur+tlrc.HEAD")):
        blur_epi(work_dir, subj_num)

    # make subject intersection mask
    if not os.path.exists(os.path.join(work_dir, "final_mask_WM_eroded+tlrc.HEAD")):
        make_masks(work_dir, subj_num)

    # scale data
    if not os.path.exists(os.path.join(work_dir, f"run-1_{task}_scale+tlrc.HEAD")):
        scale_epi(work_dir, subj_num, task)

    # clean
    if os.path.exists(os.path.join(work_dir, f"run-1_{task}_scale+tlrc.HEAD")):
        for tmp_file in glob.glob(f"{work_dir}/tmp*"):
            os.remove(tmp_file)


if __name__ == "__main__":
    main()
