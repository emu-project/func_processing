#!/bin/bash

function Usage {
    cat << USAGE

    Wrap func3_timing_files.R, which makes timing files.

    Timing files will be written to: 
        proj_dir/derivatives/afni/sub-1234/ses-A/timing_files

    Passed Arguments (func3_submit -> func3_timing_files.R):

        1: proj_dir -> 6: proj_dir
        2: subj -> 7: subj
        3: sess -> 8: sess
        4: task -> 9: task

    Notes:

        Timing files are AFNI-styled, currently using onset only.

    Usage:

        func3_submit.sh \\
            -p proj_dir \\
            -s ses-str \\
            -t task-str

    Required Arguments:

        -p <proj_dir> = /path/to/BIDS/project_dir
        -s <ses-str> = BIDS session string
        -t <task-str> = BIDS task string

    Example Usage:

        func3_submit.sh \\
            -p /scratch/madlab/emu_UNC \\
            -s ses-S2 \\
            -t test

USAGE
}

# assign variables
while getopts ":p:a:s:t:h" OPT; do
    case $OPT in
        p) proj_dir=${OPTARG}
            ;;
        s) sess=${OPTARG}
            ;;
        t) task=${OPTARG}
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

if [ -z "$proj_dir" ] || [ -z "$sess" ] || [ -z "$task" ]; then
    echo -e "\n \t ERROR: all required arguments not defined." >&2
    Usage
    exit 1
fi

if [ ! -d $proj_dir ]; then
    echo -e "\n \t ERROR: $proj_dir not found or is not a directory." >&2
    Usage
    exit 1
fi

cat << EOF

    Success! Checks passed, starting work with the following variables:

    proj_dir=$proj_dir
    sess=$sess
    task=$task

EOF


# work
module load r-3.5.1-gcc-8.2.0-djzshna

afni_dir=${proj_dir}/derivatives/afni
subj_list=(`ls $afni_dir | grep "sub-*"`)

for subj in ${subj_list[@]}; do
    echo -e "\t Starting R script for $subj ..."
    write_dir=${afni_dir}/${subj}/${sess}/timing_files
    mkdir -p $write_dir
    Rscript func3_timing_files.R $proj_dir $subj $sess $task
done
