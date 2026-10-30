# Offline security regressions

Requires Python 3 (standard library only), Bash, jq, Node.js and ordinary shell utilities. No dependency installation or credentials are needed. From the repository root, use an existing writable scratch directory:

```bash
python3 tests/test_security.py --scratch /path/to/scratch -v
```

Temporary fixtures are created only under `--scratch` and removed afterward. The harness constructs a private HOME/PATH and a minimal environment with a synthetic API key. It runs real scripts/encoders/parsers; curl and DNS tools record argv/stdin locally and never connect. No SQL/database behavior is involved. Do not replace these recording transports with real network clients.

For baseline proof, export the known commit to a new empty directory in scratch, then run the candidate's tests against that export:

```bash
mkdir /path/to/scratch/sendgrid-baseline
git archive 6d6b44b27d634544a5049f823f906a8992a1802c | tar -x -C /path/to/scratch/sendgrid-baseline
python3 tests/test_security.py --scratch /path/to/scratch \
  --root /path/to/scratch/sendgrid-baseline -v \
  HelperTests.test_test_email_values_remain_data \
  HelperTests.test_json_structure_cannot_add_recipients \
  HelperTests.test_webhook_arguments_are_rejected_before_any_network
```

Those baseline tests are expected to fail; the corrected tree must pass. URL cases exercise rejection of the removed probing capability, including private/reserved/alternate address forms and mixed/rebinding DNS fixtures. They do not test IP classification, connection pinning or a real DNS resolver: no webhook target is resolved or connected to. Synthetic proxy/redirect configuration cannot trigger a transport when probing is absent.

The suite also executes the actual curl documentation blocks against the recorder, including standalone outbound references without sibling scripts, and checks exact argv/data. Parser tests characterize a local data/code boundary, not production multipart fidelity. It intentionally remains a lossy diagnostic parser. Human-facing approval/privacy prose is reviewed as guidance, not claimed as a runtime permission gate or agent-behavior guarantee.
