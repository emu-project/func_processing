#!/bin/bash

function Usage {
    cat << USAGE

    Runs automated hippocampal subfield segmentation (ASHS)
    using T1- and T2-weighted files. Bootstrap skipped (-B).

    Usage:

        docker run \\
	        -v </path/to/dset>:/data_dir \\
            -v </path/to/derivatives>:/work_dir \\
            -v </path/to/atlas/dir>:/atlas_dir \\
            nmuncy/ashs \\
            -i <file_str> \\
            -g <t1w.nii> \\
            -f <t2w.nii> \\
            -a <atlas_str>

    Required Arguments:

    	-v </path/to/dset> = absolute path to localhost dset/subject/session/anat directory
        -v </path/to/derivatives> = absolute path to localhost derivatives directory
        -v </path/to/atlas/dir> = absolute path to localhost parent directory of ASHS atlas
        -i = subject string
        -g = absolute path to localhost T1-weighted NIfTI
        -f = absolute path to localhost T2-weighted NIfTI
        -a = ASHS atlas name

    Example Usage:

        docker run \\
	        -v /home/data/dset/sub-1234/ses-A/anat:/data_dir \\
            -v /home/data/derivatives/ashs/sub-1234/ses-A:/work_dir \\
            -v /home/atlases:/atlas_dir \\
            nmuncy/ashs \\
            -i sub-1234 \\
            -g sub-1234_ses-A_T1w.nii.gz \\
            -f sub-1234_ses-A_T2w.nii.gz \\
            -a ashs_atlas_magdeburg
USAGE
}

while getopts ":i:g:f:a:h" OPT
    do
    case $OPT in
        i) subj=${OPTARG}
            ;;
        g) t1_file=${OPTARG}
            ;;
        f) t2_file=${OPTARG}
            ;;
        a) ashs_atlas=${OPTARG}
			;;
        h)
            Usage
            exit 0
            ;;
        \?) echo -e "\n \t ERROR: invalid option, printing help ..." >&2
            Usage
            exit 1
            ;;
    esac
done

# Print help
if [ $OPTIND == 1 ]; then
    Usage
    exit 0
fi

# Make sure required args have values
function Error {
    case $1 in
        subj) h_ret="-i"
            ;;
        t1_file) h_ret="-g"
            ;;
        t2_file) h_ret="-f"
            ;;
        ashs_atlas) h_ret="-a"
            ;;
        *)
            echo -n "Unknown option."
            ;;
    esac
    echo -e "\n\n \t ERROR: Missing input parameter for \"${h_ret}\"." >&2
    Usage
    exit 1
}

for opt in subj t1_file t2_file ashs_atlas; do
    h_opt=$(eval echo \${$opt})
    if [ -z $h_opt ]; then
        Error $opt
    fi
done

cat << EOF

    Success! Checks passed, starting work with the following variables:

    -I (subject) = $subj
    -a (atlas) = /atlas_dir/$ashs_atlas
    -g (t1_file) = /data_file/$t1_file
    -f (t2_file) = /data_file/$t2_file
    -w (work_dir) = /work_dir
    -B (skip bootstrap)

EOF

# work
echo -e "\n Running ASHS, capturing stderr/out to /work_dir/ashs_log. \n"
${ASHS_ROOT}/bin/ashs_main.sh \
	-I $subj \
	-a /atlas_dir/$ashs_atlas \
	-g /data_dir/$t1_file \
	-f /data_dir/$t2_file \
    -B \
	-w /work_dir |& tee /work_dir/ashs_log
