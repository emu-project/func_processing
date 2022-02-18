#!/bin/bash

function Usage {
    cat <<USAGE

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
        -c </code/dir> = path to clone of emu-project/func_processing.git

    Optional Arguments:
        -u [y/n] = update repo [n]

    Usage:
        ./start_afni.sh \\
            -p \$TOKEN_GITHUB_EMU \\
            -s ses-S1 \\
            -t task-study \\
            -c /home/nmuncy/compute/func_processing

    Cron example:
        * */6 * * * TOKEN=$(cat /home/nmuncy/.ssh/pat_github_emu); \
            cd /home/nmuncy/compute/func_processing/cron && \
            ./start_afni.sh \
            -p $TOKEN \
            -s ses-S1 \
            -t task-study \
            -c /home/nmuncy/compute/func_processing \
            >cron_out 2>cron_err

USAGE
}

# Start record
currentDate=$(date)
echo "************************"
echo "Cron Start: $currentDate"
echo "************************"

# Check options
update_repo=n

while getopts ":c:p:s:t:u:h" OPT; do
    case $OPT in
    c)
        code_dir=${OPTARG}
        ;;
    p)
        token=${OPTARG}
        ;;
    s)
        sess=${OPTARG}
        ;;
    t)
        task=${OPTARG}
        ;;
    u)
        update_repo=${OPTARG}
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

# Make sure required args have values
function Error {
    case $1 in
    code_dir)
        h_ret="-c"
        ;;
    token)
        h_ret="-p"
        ;;
    sess)
        h_ret="-s"
        ;;
    task)
        h_ret="-t"
        ;;
    *)
        echo -n "Unknown option."
        ;;
    esac
    echo -e "\n\n \t ERROR: Missing input parameter for \"${h_ret}\", or error using argument." >&2
    Usage
    exit 1
}

for opt in code_dir token sess task; do
    h_opt=$(eval echo \${$opt})
    if [ -z $h_opt ]; then
        Error $opt
    fi
done

# check that previous jobs are done
num_jobs=$(squeue -u $(whoami) | wc -l)
if [ $num_jobs -gt 2 ]; then
    echo "Jobs still running, exiting ..."
    exit 0
fi

# pull repo
if [ $update_repo == "y" ]; then
    cd $proj_dir
    echo -e "\nUpdating $proj_dir"
    git fetch https://${token}:x-oauth-basic@github.com/emu-project/func_processing.git
fi

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

# submit afni CLI
cat <<-EOF

    Success! Starting ${code_dir}/cli/run_afni.py
    with the following parameters:
        -s <sess> = $sess
        -t <task> = $task
        -c <code_dir> = $code_dir

EOF

sbatch \
    --job-name=runAfni \
    --output=${code_dir}/logs/runAfni_${sess}_log \
    --mem-per-cpu=4000 \
    --partition=IB_44C_512G \
    --account=iacc_madlab \
    --qos=pq_madlab \
    ${code_dir}/cli/run_afni_task.py \
    -s $sess \
    -t $task \
    -c $code_dir
