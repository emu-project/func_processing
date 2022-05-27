def main():
    """Print entrypoint help."""

    print(
        """
    Trigger cli script help with the following entrypoints:
        
        entry       ->  script
        -----           ------
        ashs        ->  cli.ashs
        check       ->  cli.checks
        fmriprep    ->  cli.fmriprep
        reface      ->  cli.reface
        rs_group    ->  cli.afni_resting_group
        rs_subj     ->  cli.afni_resting_subj
        task_group  ->  cli.afni_task_group
        task_subj   ->  cli.afni_task_subj        
    """
    )


if __name__ == "__main__":
    main()

