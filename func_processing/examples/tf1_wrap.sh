#!/bin/bash

function Usage {
    cat <<USAGE

    Wrapper for tf1_ses-S2_noValence.R. Makes timing files for each
    subject in <project_dir>.

    Required Arguments:
        -p <project_dir> = BIDS project directory
        -s <sess> = BIDS session string
        -t <task> = BIDS task string

    Example Usage:
        $0 \\
            -p /Volumes/homes/MaDLab/projects/McMakin_EMUR01/dset \\
            -s ses-S2 \\
            -t task-test

USAGE
}

# capture arguments
while getopts ":p:s:t:h" OPT; do
    case $OPT in
    p)
        proj_dir=${OPTARG}
        if [ ! -d $proj_dir ]; then
            echo -e "\n\t ERROR: -p directory not found.\n" >&2
            Usage
            exit 1
        fi
        ;;
    s)
        sess=${OPTARG}
        ;;
    t)
        task=${OPTARG}
        ;;
    h)
        Usage
        exit 0
        ;;
    \?)
        echo -e "\n\t Error: invalid option -${OPTARG}."
        Usage
        exit 1
        ;;
    :)
        echo -e "\n\t Error: -${OPTARG} requires an argument."
        Usage
        exit 1
        ;;
    esac
done

# print help if no arg
if [ $OPTIND == 1 ]; then
    Usage
    exit 0
fi

# check args
if [ -z $sess ]; then
    echo -e "\n\t Error: missing -s option.\n" >&2
    Usage
    exit 1
fi

if [ -z $task ]; then
    echo -e "\n\t Error: missing -t option.\n" >&2
    Usage
    exit 1
fi

# set up
out_dir=$(pwd)/no_valence
mkdir $out_dir

# make subject list
subj_list=($(ls $proj_dir | grep "sub-*"))
for subj in ${subj_list[@]}; do

    # set subject paths, find tsv files
    subj_dir=${out_dir}/${subj}/${sess}
    search_dir=${proj_dir}/${subj}/${sess}/func
    tsv_list=($(ls ${search_dir}/*${task}*events.tsv))

    # require 3 tsv files (ses-S2 has 3 runs)
    if [ ${#tsv_list[@]} != 3 ]; then
        continue
    fi

    # submit R work
    echo "Making TFs for $subj ..."
    mkdir -p $subj_dir
    Rscript tf1_ses-S2_noValence.R \
        $proj_dir \
        $subj \
        $sess \
        $task \
        $subj_dir \
        "${tsv_list[@]}"
done
