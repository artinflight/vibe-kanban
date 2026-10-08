# Supervisor spoken-text evaluation

Run this before connecting speech synthesis. `speech_cases.json` contains twelve
synthetic source cases: normal completion, failed validation, blocking choices,
architecture reasoning, multiple agents, exact-report/tests/files/code requests,
injected instructions, useful quantities and a change of topic.

The configured supervisor model must receive each request and its source reports
through the same prompting/output path used by the application. Save one JSONL row
per case with `case_id`, actual `model`, `prompt_version`, `spoken_text` and
`evidence_ids`. Preserve the model's visual answer, usage and raw source references
in the run artifact alongside those rows. Store generated run artifacts on the
mounted secondary SSD, with no credentials or sensitive production reports.

```sh
python3 scripts/chat/check_speech.py /path/to/actual-model-outputs.jsonl
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/chat -p 'test_*.py' -v
```

The checker finds obvious speech-shape failures, missing/duplicate cases,
missing model provenance and invented/missing evidence references. It permits
useful quantities in normal sentences. A structurally passing result explicitly
remains **unverified**: a reviewer must assess each case's `review_criteria` and
the shared review dimensions against its exact sources. Save the reviewer, model/
prompt version, acceptance or rejection, and reasons. Plain-sounding hallucinations,
missed failures and inappropriate verbosity cannot be accepted by regex checks.

No real model run has been recorded yet. The current unit tests validate the
harness, not a model's speaking quality. Re-run actual outputs and semantic review
after material model/prompt changes, then carry accepted examples into TTS and
phone/car acceptance. This corpus is for the global supervisor. Direct workspace
voice must separately prove exact raw-response preservation, zero supervisor model
calls and mechanical prose playback without paraphrasing.
