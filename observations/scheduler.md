# Running the registered paper observation

The scheduled workflow reads one frozen implementation and appends evidence to the public branch `observations/weekly-allocation-v1`. Its initial `registration.json` records the full implementation commit (`revision`), SHA-256 of the exact protocol bytes (`protocol_sha256`) and UTC registration time (`registered_at`). The repository Actions variable `PAPER_REGISTRATION_SHA` must match that commit. Activation follows the public registration and rehearsal checks. The driver verifies both checkouts and the hash before processing any observation. The executing workflow must also match its frozen bytes.

The cron clock has one permanently skipped job. It allocates no runner. Its completion triggers the recorder through GitHub’s `workflow_run` event, which carries repository visibility, the clock commit and its creation time. Server-side conditions require the canonical public repository before allocating a machine. The driver checks the same fields and rejects a clock created on an earlier UTC date, even if the delayed job starts on another eligible Monday. GitHub supplies the cron expression and run creation time. It does not attest the exact instant at which the scheduler intended to enqueue the run. The recorder uses its actual UTC clock for every financial deadline.

Before setting `PAPER_REGISTRATION_SHA`, run the read-only hosted qualification with `gh workflow run paper-clock.yml --ref main`. Verify both the skipped clock job and the downstream rehearsal job. The rehearsal checks real event metadata, rejects that manual run as research input, and exercises the driver and recorder against disposable synthetic state. Its token can only read the repository. It never opens the public observation branch or contacts a market source. Only a scheduled clock can drive the observation writer. A manual run remains a rehearsal even after registration.

| Job | UTC schedule | Eligibility |
| --- | --- | --- |
| Decision | Monday 00:07 | The recorder enforces its completed-close input and decision deadline. The job publishes the decision to the record branch. |
| Fill | Monday 00:41 | The job verifies that its validated checkout is the current remote record before 00:45, then waits once until 00:46:15 for the exact 00:45 fixing. Receipt must fall within five minutes of the fixing. |
| Closing marks | Daily 03:17 | The recorder applies the registered mark windows and reconciles missed cycles. It retains actual receipt times and recovery status. |

GitHub can delay or drop scheduled runs. A fill job arriving at or after the fixing skips the market request. When no qualifying fill occurs, the next reconciliation records the miss and the accounts carry their existing positions. Manual dispatch, job reruns and fork workflows are ineligible. A restart begins from a validated public branch. If a push has an uncertain outcome, read the branch on the next scheduled cycle. Do not fabricate a timely event from an earlier clock or replay a missed trade.

The workflow uses the repository’s existing commit-pinned checkout and Python actions, a standard GitHub-hosted Ubuntu runner, and the release’s pinned NumPy and SciPy. It has no paid services, uploaded job artifacts or dependency cache. Each run has a 13-minute deadline, one fill wait of at most 390 seconds, and at most three market-source requests with no retry. Pushes are fast-forwards; existing event files and registration cannot be edited by the driver. The complete public state is capped at 5,000,000 bytes. The state branch holds small, separately committed event files and one replaceable status projection. The frozen implementation checkout discards its Git credential after fetching. The record checkout uses the job token to publish evidence. A separate terminal job has permission to disable the clock and then the recorder only after a validated closing projection has reached the remote branch and been read back.

Repository operators must disable the schedule before a transition to private visibility, paid runners, or changed licensing. The workflow checks actual repository visibility before it reads any market data. GitHub can disable public scheduled workflows for inactivity; a service interruption remains part of the record. Inspect the workflow history and append an operational explanation where needed. A lost window never extends the horizon. [GitHub schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) · [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)

For independent readback, clone the record with full history. In a clean toolkit checkout at the implementation revision in its registration, use an environment with the v0.5.0 dependencies and run:

```sh
git clone --single-branch --branch observations/weekly-allocation-v1 https://github.com/hnt119/agenthon-quant-lab.git ../allocation-record
PYTHONPATH=src:. python -B -m observations.verify_record ../allocation-record
```

Readback verifies the protocol hash, UTC timing, immutable event chain and status projection, replays balances and costs, and checks that each recorded public witness commit already contained the decision used by its subsequent paper fill.
