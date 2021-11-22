#!/bin/bash


function Usage {
    cat << USAGE

    Submitted via crontab, this script will first check
    whether previous jobs are still running. Next it submit
    cli/run_reface.py via sbatch.

    -m options reference afni_refacer_run modes, reface is default.
        -mode_{reface|reface_plus|deface}

   Optional Arguments:
        -m [deface/reface/reface_plus] = method of adjusting face.
        -h = print this help

   Usage:
    ./start_ashs.sh

    Cron example:
        * */4 * * * cd /home/nmuncy/compute/func_processing/cron && \
            ./start_reface.sh \
            >cron-reface_out 2>cron-reface_err

USAGE
}

# Check options
method=reface
while getopts ":m:h" OPT; do
    case $OPT in
        m) method=${OPTARG}
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

case $method in
    reface) echo "Method == reface"
        ;;
    reface_plus) echo "Method == reface_plus"
        ;;
    deface) echo "Method == deface"
        ;;
    *) echo "ERROR: unrecognized method \"$method\", see -m help."
        Usage
        exit 1
        ;;
esac


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


# submit ashs CLI
cat <<- EOF

    Success! Starting cli/run_reface.py with the following parameters:

    -m <method> = $method
    -c <code_dir> = $proj_dir

EOF

sbatch --job-name=runReface \
    --output=runReface_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${proj_dir}/cli/run_reface.py \
    -c $proj_dir
