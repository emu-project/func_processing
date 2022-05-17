#!/bin/bash

function Usage {
    cat <<USAGE

    Submitted via crontab, this script will first check
    whether previous jobs are still running. Next it submit
    cli/run_reface.py via sbatch.

    Required Arguments:
        -c </code/dir> = path to clone of emu-project/func_processing.git

    Optional Arguments:
        -m [deface/reface/reface_plus] = method of adjusting face, reface is default.
            references -mode_{reface|reface_plus|deface} option of @afni_refacer_run.
        -h = print this help

    Usage:
        ./start_ashs.sh -c /home/nmuncy/compute/func_processing

    Cron example:
        * */4 * * * cd /home/nmuncy/compute/func_processing/cron && \
            ./start_reface.sh \
            -c /home/nmuncy/compute/func_processing \
            >cron-reface_out 2>cron-reface_err

USAGE
}

# Start record
currentDate=$(date)
echo "************************"
echo "Cron Start: $currentDate"
echo "************************"

# Set, get options
method=reface

while getopts ":c:m:h" OPT; do
    case $OPT in
    m)
        method=${OPTARG}
        ;;
    c)
        code_dir=${OPTARG}
        ;;
    h)
        Usage
        exit 0
        ;;
    \?)
        echo -e "\n \t ERROR: invalid option." >&2
        Usage
        exit 1
        ;;
    esac
done

if [ $OPTIND == 1 ]; then
    Usage
    exit 0
fi

# verify options
if [ ! -d $code_dir ]; then
    echo -e "\n \t ERROR: input for -c missing or is not a directory." >&2
    Usage
    exit 1
fi
echo -e "\n \t \$code_dir: $code_dir"

case $method in
reface)
    echo -e "\n \t Method: $method"
    ;;
reface_plus)
    echo -e "\n \t Method: $method"
    ;;
deface)
    echo -e "\n \t Method: $method"
    ;;
*)
    echo "ERROR: unrecognized method \"$method\", see -m help."
    Usage
    exit 1
    ;;
esac

# verify environment
try_count=0
unset conda_found
search_python() {
    which python | grep "emuR01_madlab_env" >/dev/null 2>&1
    return $?
}
search_python
conda_found=$?
while [ $try_count -lt 2 ] && [ $conda_found != 0 ]; do
    echo "ERROR: did not find conda env emuR01_madlab_env,"
    echo -e "\tattempting resolution $try_count.\n"
    case $try_count in
    0)
        madlab_env emuR01
        ;;
    1)
        source ~/.bashrc && madlab_env emuR01
        ;;
    2)
        echo "Failed to load conda env emuR01_madlab_env." >&2
        echo "Please configure environment according to github.com/fiumadlab/madlab_env.git" >&2
        echo "Exiting." >&2
        exit 1
        ;;
    esac
    let try_count+=1
    search_python
    conda_found=$?
done
echo -e "\nPython path: $(which python)"

# check that previous jobs are done
num_jobs=$(squeue -u $(whoami) | wc -l)
if [ $num_jobs -gt 1 ]; then
    echo -e "\n \t Jobs still running, exiting ..."
    exit 0
fi

# submit reface CLI
cat <<-EOF

    Success! Starting $code_dir/cli/run_reface.py
    with the following parameters:
        -m <method> = $method
        -c <code_dir> = $code_dir

EOF

sbatch --job-name=runReface \
    --output=${code_dir}/logs/runReface_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${code_dir}/cli/run_reface.py \
    -c $code_dir
