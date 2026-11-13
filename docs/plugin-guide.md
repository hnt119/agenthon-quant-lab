# Codex skill setup

The reusable integration is the maintained `quant-research` Codex skill. It is a
thin command-and-reference interface to this source checkout, not a separate
finance engine or a hosted plugin service.

```sh
python3 scripts/setup.py --install-skill
.venv/bin/python -m agenthon_quant doctor
```

The optional installation links `skills/quant-research` into
`${CODEX_HOME:-$HOME/.codex}/skills/quant-research`. A link already pointing to this
checkout is an idempotent success. Any existing file, directory, broken link or
link to a different checkout is preserved and reported; nothing is replaced.
For an isolated test or another skills directory, pass
`--install-skill --skills-dir /absolute/skills-directory`.

Start a new Codex chat when needed for skill discovery and invoke `$quant-research`
explicitly if it has not been selected automatically. Discovery depends on the
host app; successful file installation alone is not proof of automatic selection.
The skill resolves its real path, uses the checkout's `.venv`, and keeps all
calculations in `src/agenthon_quant`. Keep the checkout at its linked location,
or deliberately update the link yourself when moving it.

Useful requests include:

1. “Price these options and show how value changes with volatility.”
2. “Compare this strategy with buy-and-hold after costs.”
3. “Explain why this analysis failed validation.”
4. “Reproduce this saved experiment with a different assumption.”
5. “Find the papers relevant to this pricing approach and show what is implemented.”
6. “Which historical experiments failed or remain incomplete, and what did we learn?”

The first four use run/example/explain/reproduce; the last two query curated local
archives. The skill should ask for material missing inputs, distinguish failed
from unavailable checks, and link actual artifacts. The [user guide](user-guide.md)
explains setup, inputs, source-version reproduction and private ZIP bundles.

No live trading, paid model usage, endpoint diagnostics, generated-code execution,
competition evaluation or automatic public sharing is part of this skill.
