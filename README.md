# func_processing
Pipeline used to take functional data from DICOMs through group-level analyses. Organization is as follows:

- cli: **User-level entrypoint.** Contains scripts to start AFNI, ASHS, fMRIprep, FreeSurfer, refacing, and data checking workflows.
- cron: Outdated. Automate cli. Can be used to schedule/automate cli usage.
- dockerfiles: Contains Dockerfile and scripts used for generating, running docker.
- docs: Resources for formal documentation, via sphinx. Instructions in build_docs.txt.
- logs: Mainly for completed_preprocessing.tsv, other output logs written here.
- qc: Files/scripts for conducting qc on pipeline workflows for non-default options. Also serves as example of user-specified timing files.
- resources: Location of modules for AFNI, ASHS, FreeSurfer, fMRIprep, and reports.
- tests: Outdated. Unit and module tests.
- workflow: Manages resources, controlled by cli.

See [Wiki](https://github.com/emu-project/func_processing/wiki) for details and description (under construction).

Module documentation [here](https://func-processing.readthedocs.io/en/latest), assuming sphinx is cooperative.
