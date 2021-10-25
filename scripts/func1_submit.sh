#!/bin/bash

function Usage {
    cat << USAGE

    Wrap func1_fmriprep.sh, supply needed arguments.

    Creates an sbatch submission to run fMRIprep on a number of participants. Stdout/err
    are captured in <project_dir>/derivatives/Slurm_out/fmriprep_<time-stamp> for each 
    subject.

    Passed Arguments (func1_submit -> func1_fmriprep):

        1: subject (int) -> label
        2: sing_img -> sing_img
        3: project_dir -> project_dir
        4: fs_license -> fs_license
        5: tplflow_dir -> tplflow_dir

    Notes:

        1) func1_fmriprep is currently hardcoded to reference MNIPediatricAsym:cohort-5:res-2.
        This is relevant for the -r option.

        2) if fMRIprep fails on a subject, the next crontab job will resubmit the same subject.
        This could probably be updated in the future.

    Usage:

        func1_submit.sh \\
            -f fs_license.txt \\
            -i file.simg \\
            -m int \\
            -p project_dir \\
            -r space-str \\
            -s ses-str \\
            -t task-str \\
            -x tplflow_dir

    Required Arguments:

        -f <fs_license.txt> = FreeSurfer license
        -i <file.simg> = singularity image for fMRIprep
        -m <int> = integer, maximum number of participants to submit to sbatch
        -p <project_dir> = location of BIDS-structured project directory
        -r <space-str> = templateflow reference space string, for checking whether
            fMRIprep output alread exists
        -s <ses-str> = BIDS session string
        -t <task-str> = BIDS task string
        -x <tplflow_dir> = path to templateflow location on HPC

    Example Usage:

        func1_submit.sh \\
            -f ~/bin/licenses/fs_license.txt \\
            -i /home/nmuncy/bin/singularities/nipreps_fmriprep_20.2.3.simg \\
            -p /scratch/madlab/emu_UNC \\
            -m 8 \\
            -s ses-S2 \\
            -t task-test \\
            -r space-MNIPediatricAsym_cohort-5_res-2 \\
            -x /home/data/madlab/singularity-images/templateflow

USAGE
}


# assign variables
while getopts ":f:i:p:m:s:t:r:x:h" OPT; do
    case $OPT in
        f) fs_license=${OPTARG}
            ;;
        i) sing_img=${OPTARG}
            ;;
        p) proj_dir=${OPTARG}
            ;;
        m) max_num=${OPTARG}
            ;;
        s) sess=${OPTARG}
            ;;
        t) task=${OPTARG}
            ;;
        r) space=${OPTARG}
            ;;
        x) tplflow_dir=${OPTARG}
            ;;
        h)
            Usage
            exit 0
            ;;
        \?) echo -e "\n \t ERROR: invalid option." >&2
            Usage
            exit 1
            ;;
    esac
done


# check inputs
if [ $OPTIND == 1 ]; then
    Usage
    exit 0
fi

if [ -z "$fs_license" ] || \
    [ -z "$sing_img" ] || \
    [ -z "$proj_dir" ] || \
    [ -z "$max_num" ] || \
    [ -z "$sess" ] || \
    [ -z "$task" ] || \
    [ -z "$space" ] || \
    [ -z "$tplflow_dir" ]; then
    echo -e "\n \t ERROR: all required arguments not defined." >&2
    Usage
    exit 1
fi

if [ ! -f $fs_license ] || [ ! -f $sing_img ]; then
    echo -e "\n \t ERROR: FreeSurfer License or singularity.img not found." >&2
    Usage
    exit 1
fi

if [ ! -d $proj_dir ]; then
    echo -e "\n \t ERROR: $proj_dir not found or is not a directory." >&2
    Usage
    exit 1
fi

if [ ! -d $tplflow_dir ]; then
    echo -e "\n \t ERROR: $tplflow_dir not found or is not a directory." >&2
    Usage
    exit 1
fi

cat << EOF

    Success! Checks passed, starting work with the following variables:

    fs_license=$fs_license
    sing_img=$sing_img
    proj_dir=$proj_dir
    max_num=$max_num
    sess=$sess
    task=$task
    space=$space
    tplflow_dir=$tplflow_dir

EOF


# Set up
dset_dir=${proj_dir}/dset
deriv_dir=${proj_dir}/derivatives

# find number of subjects who don't have fmriprep output
unset subj_all subj_list
subj_all=(`ls $dset_dir | grep "sub-*"`)
for subj in ${subj_all[@]}; do
    check_file=${deriv_dir}/fmriprep/${subj}/${sess}/func/${subj}_${sess}_${task}_run-1_${space}_desc-preproc_bold.nii.gz
    if [ ! -f $check_file ]; then
        subj_list+=(${subj})
    fi
    if [ ${#subj_list[@]} == $max_num ]; then
        break
    fi
done

# submit jobs
time=`date '+%Y_%m_%d-%H_%M'`
out_dir=${deriv_dir}/Slurm_out/fmriprep_${time}
mkdir -p $out_dir

for subj in ${subj_list[@]}; do

    # clean previous attempts
    for check in freesurfer tmp_work fmriprep; do
        if [ -d ${deriv_dir}/${check}/${subj} ]; then
            rm -r ${deriv_dir}/${check}/${subj}*
        fi
    done

    # submit jobs
    sbatch \
        -e ${out_dir}/err_${subj}.txt \
        -o ${out_dir}/out_${subj}.txt \
        func1_fmriprep.sh \
            ${subj#*-} \
            $sing_img \
            $proj_dir \
            $fs_license
    sleep 1
done
