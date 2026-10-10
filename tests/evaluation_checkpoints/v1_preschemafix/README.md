# Script-arm checkpoints collected BEFORE the schema fix

These two arms were run against the previous `system_prompt.txt`, which nested
`EPF Taxable Interest` inside a container called `Other Interest` and documented
no input structure at all. Models writing Python therefore inferred the input's
shape from the output schema and read
`data["Other Interest"]["EPF Taxable Interest"]`, raising TypeError on an int.
Both retry transcripts in the project do exactly that, and gemma scored 63.3% on
that field here against 100.0% for the same model in zero-shot.

They are kept for provenance and are NOT comparable with the re-run arms: the
prompt changed, so the question changed.

| arm | cases | accuracy (rescored ground truth) |
|---|---|---|
| ollama/gemma4-12b-ctx16k script | 50 | 45.73% |
| nvidia/nemotron-3-ultra script | 36 | 61.19% |

The zero-shot checkpoints were NOT archived. Their answers remain scorable
because `LEGACY_FIELD_PATHS` in `evaluate_llm.py` reads `epf_taxable_interest`
at its old nested location when the current path is absent, and the collision
caused no measurable harm there: 0 conflations and 0 shape errors across all
nine zero-shot arms, 508/508 correct for nemotron.
