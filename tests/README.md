Tests are written FROM the spec documents, before implementation:

- test_contracts.py      shapes, universal fields, vocabulary membership
- test_provenance.py     four classes, payload requirements, write contract
- test_reporter.py       eight verbs, ambient capture, validation-at-call
- test_sink.py           JSONL crash-safety, append-only behavior
- test_consolidation.py  aggregation, decomposability pass AND fail cases,
                         tier filtering
- test_toy_module.py     the Phase 0 acceptance deliverable end-to-end
