# func_processing
Pipeline used to take functional data from DICOMs through group-level analyses. 

## Entry Points
Following `python setup.py install` or `python setup.py develop`, use the following entry points to trigger cli.

- `check` : print help, run `cli.checks`
- `ashs` : trigger help of `cli.ashs`
- `reface` : trigger help of `cli.reface`
- `fmriprep` : trigger help of `cli.fmriprep`
- `task_subj` : trigger help of `cli.afni_task_subj`
- `rs_subj` : trigger help of `cli.afni_resting_subj`
- `task_group` : trigger help of `cli.afni_task_group`
- `rs_group` : trigger help of `cli.afni_resting_group`

## Project organization

Top Level

- dockerfiles : Dockerfile, shell script backup
- docs : Project documentation, for [ReadTheDocs](https://emu-func-processing.readthedocs.io/en/latest/), assuming sphinx is cooperative. Build instruction found in build_docs.txt. 
- func_processing : Main package

func_processing

- cli : Contains scripts to start AFNI, ASHS, fMRIprep, FreeSurfer, refacing, and data checking workflows.
- examples : Contains example scripts and files.
- logs : Mainly for completed_preprocessing.tsv, other output logs written here.
- resources : Location of modules for AFNI, ASHS, FreeSurfer, fMRIprep, and reports.
- tests : Scripts for testing resources and workflows.
- tools : Location for auxiliary/shell scripts. Currently contains (outdated) cron scripts
- workflow : Manages resources, controlled by cli.

See [Wiki](https://github.com/emu-project/func_processing/wiki) for details and description, now a little outdated due to refactoring.
