# Agenthon Quant Lab

Maintain the deterministic calculation engine in `src/agenthon_quant` as the
single implementation used by CLI, skill and future dashboard. Keep independent
verification separate from calculation. Run `python -m unittest discover -s tests -v`.

The original competition repository is historical evidence, not a dependency.
Do not change its release pointers or receipts. Do not copy official graders,
reference answers, raw captures, credentials or generated competition answers.
Keep negative results and distinguish synthetic checks from market evidence.

The default paid-service budget is zero. No live broker, paid data, model endpoint,
generated-code execution or external publication is implemented or authorized by
routine local maintenance. Future generated code needs verified isolation with
read-only inputs, fresh attempts, resource limits and validated publication; a
plain subprocess is not an adequate replacement.

Every analysis needs an explicit specification, content-hashed inputs, code
identity, checks and a report. Preserve existing run directories; reproduce into
a new directory. Never tune strategy parameters using the final held-out period.

Skill source is `skills/quant-research`; keep its commands synchronized with the
CLI. Avoid duplicating calculations in skill scripts or a future dashboard.
