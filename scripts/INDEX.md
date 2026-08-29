# INDEX — scripts

- `archive_run.py`: non-destructively archives a run’s config and filtered artifacts through staged atomic publication.
- `run_intake_workflow.py`: validates one immutable Intake launch manifest, preflights the selected Provider/browser, archives the previous active run, promotes the selected config, and executes `WorkflowRunner`.
- `collect_browser_evidence.mjs`: serves the generated site on an ephemeral loopback port and stores real Edge/Chrome desktop DOM, overflow, console, screenshot, and SHA-256 evidence.
- `start-site-intake.bat`: desktop launcher for the production Intake page.
