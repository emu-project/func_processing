#!/bin/bash


function Usage {
    cat << USAGE

    Submitted via crontab, this script will first check
    whether previous jobs are still running, then update
    the repo in case changes have been made. Next it will
    check to make sure we are using a MaDLab python env
    of some sort (whether "conda" exists in PYTHONPATH),
    and finally it will submit cli/run_afni.py via sbatch.

    Required Arguments:
        -p <pat_token> = personal access token for github.com/emu-project
        -s <session> = BIDS session (ses-S1)
        -t <task> = BIDS task, corresponding to session (task-study)

    Usage:
        ./start_afni.sh \\
            -p \$TOKEN_GITHUB_EMU \\
            -s ses-S1 \\
            -t task-study

USAGE
}


# Check options
while getopts ":p:s:t:h" OPT; do
    case $OPT in
        p) token=${OPTARG}
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

if [ $OPTIND == 1 ]; then
    Usage
    exit 0
fi


# Make sure required args have values
function Error {
    case $1 in
        token) h_ret="-p"
            ;;
        sess) h_ret="-s"
            ;;
        task) h_ret="-t"
            ;;
        *)
            echo -n "Unknown option."
            ;;
    esac
    echo -e "\n\n \t ERROR: Missing input parameter for \"${h_ret}\", or error using argument." >&2
    Usage
    exit 1
}

for opt in token sess task; do
    h_opt=$(eval echo \${$opt})
    if [ -z $h_opt ]; then
        Error $opt
    fi
done


# Start record
currentDate=`date`
echo "************************"
echo "Cron Start: $currentDate"
echo "************************"


# check that previous jobs are done
num_jobs=`squeue -u $(whoami) | wc -l`
if [ $num_jobs -gt 1 ]; then
    echo "Jobs still running, exiting ..."
    exit 0
fi


# determine resolved path to code directory
h_dir=$(pwd)/..
proj_dir=$(builtin cd $h_dir; pwd)


# pull repo
cd $proj_dir
echo -e "\nUpdating $proj_dir"
git pull https://${token}:x-oauth-basic@github.com/emu-project/func_processing.git --branch dev-afni


# verify environment
try_count=0; unset conda_found
search_python () {
    which python | grep "conda" > /dev/null 2>&1
    return $?
}
search_python; conda_found=$?
while [ $try_count -lt 4 ] && [ $conda_found != 0 ]; do
    echo "ERROR: did not find conda in PYTHONPATH,"
    echo -e "\tattempting resolution $try_count.\n"
    case $try_count in
        0) source ~/.bash_profile
            ;;
        1) source ~/.bashrc
            ;;
        2) PYTHONPATH=~/miniconda3/bin:/home/data/madlab/scripts && export PYTHONPATH
            ;;
        3) echo "Failed to find conda when PYTHONPATH=$PYTHONPATH, exiting."
            exit 1
            ;;
    esac
    let try_count+=1
    search_python; conda_found=$?
done
echo -e "\nPython path: $(which python)"


# submit afni CLI
cat << EOF

    Success! Starting run_afni with the following parameters:

    -s <sess> = $sess
    -t <task> = $task
    -c <proj_dir> = $proj_dir

EOF

# sbatch \
#     --job-name=runAfni \
#     --output=runAfni_log \
#     --mem-per-cpu=4000 \
#     --partition=IB_44C_512G \
#     --account=iacc_madlab \
#     --qos=pq_madlab \
#     ${proj_dir}/cli/run_afni.py \
#     -s $sess \
#     -t $task \
#     -c $proj_dir \
