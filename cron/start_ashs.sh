#!/bin/bash


function Usage {
    cat << USAGE

   Submitted via crontab, this scripts will first check
   whether previous jobs are still running, then determine
   whether singularity module is loaded (and will attempt
   to load it if not). Finally it will sbatch submit
   cli/run_ashs.py.

   Required Arguments:
    -s <sing_img> = path to singularity image of docker://nmuncy/ashs

   Usage:
    ./start_ashs.sh \\
        -s /home/nmuncy/bin/singularities/ashs_latest.simg

    Cron example:
        * 23 * * * cd /home/nmuncy/compute/func_processing/cron && \
            ./start_ashs.sh \
            -s /home/nmuncy/bin/singularities/ashs_latest.simg \
            >cron-ashs_out 2>cron-ashs_err

USAGE
}

# Check options
while getopts ":s:h" OPT; do
    case $OPT in
        s) sing_img=${OPTARG}
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

if [ -z $sing_img ]; then
    echo -e "\n\n \t ERROR: Missing input parameter for \"-s\"." >&2
    Usage
    exit 1
fi


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


# check environment for singularity
which singularity > /dev/null 2>&1; sing_found=$?
try_count=0
while [ $try_count -lt 3 ] && [ $sing_found != 0]; do
    echo "ERROR: did not find singularity in \$PATH,"
    echo -e "\tattempting to load module via option $try_count.\n"
    case $try_count in
        0) module load singularity-3.8.2
            ;;
        1) mod=`module avail sing* | awk '{print $5}'` && module load $mod
            ;;
        2) echo "Failed to load singularity, exiting." >&2
            exit 1
            ;;
    esac
    let try_count+=1
    which singularity > /dev/null 2>&1; sing_found=$?
done


# determine resolved path to code directory
h_dir=$(pwd)/..
proj_dir=$(builtin cd $h_dir; pwd)


# submit ashs CLI
cat <<- EOF

    Success! Starting cli/run_ashs.py with the following parameters:

    -s <sing_img> = $sing_img
    -c <code_dir> = $proj_dir

EOF

sbatch --job-name=runAshs \
    --output=runAshs_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${proj_dir}/cli/run_ashs.py \
    -s $sing_img \
    -c $proj_dir
