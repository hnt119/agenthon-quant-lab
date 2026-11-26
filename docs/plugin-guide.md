# Optional Codex skill

For the CLI alone, use the [v0.3.1 PyPI instructions](user-guide.md). The skill is a separate source-checkout integration. Its helper calls the same deterministic engine through the checkout’s own Python environment.

With Git and Python 3.12 installed, run the following from the parent directory for your new checkout.

```sh
git clone --branch v0.3.1 --single-branch https://github.com/hnt119/agenthon-quant-lab.git
cd agenthon-quant-lab
python3.12 scripts/setup.py --install-skill
.venv/bin/quant-lab doctor
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
The skill resolves its real path, uses the checkout's `.venv`, and delegates
financial calculations to the toolkit’s Python modules. Keep the checkout at its linked location,
or deliberately update the link yourself when moving it.

## Reproduce the BTC study

If your skill already points to this release checkout, you can ask Codex directly:

> Use $quant-research to reproduce the frozen BTC momentum study, open the report, and explain how it compared with passive BTC/cash after costs.

From the same checkout you can run `.venv/bin/quant-lab btc-study` directly. From any folder on macOS or Linux the installed helper accepts the same command:

```sh
python3 "${CODEX_HOME:-$HOME/.codex}/skills/quant-research/scripts/quant.py" --version
python3 "${CODEX_HOME:-$HOME/.codex}/skills/quant-research/scripts/quant.py" btc-study
```

Expect version 0.3.1 and a new folder under your current directory’s `runs/`. Open the printed `report.md` or `dashboard.html`. The dashboard opens in a browser directly from disk. The final `reproduction.json` lists each original result that was checked. The admitted data come with the checkout. An incomplete checkout should be restored at the same reviewed Git revision. No market-data account or JSON specification is needed.

This reproduces one fixed Bitstamp study. Use `--out <fresh-folder>` for an explicit destination. The separate options, SMA and local daily-data workflows retain their own specifications. [Read the saved example](../examples/btc-study/README.md) · [Frozen data, license and protocol](../experiments/btc-financial-v1/README.md)

Useful requests include:

1. “Price these options and show how value changes with volatility.”
2. “Compare this strategy with buy-and-hold after costs.”
3. “Explain why this analysis failed validation.”
4. “Reproduce this saved experiment with a different assumption.”
5. “Find the papers relevant to this pricing approach and show what is implemented.”
6. “Which historical experiments failed or remain incomplete, and what did we learn?”
7. “Inspect this daily CSV and compare a five-close SMA, cash and buy-and-hold through my train, validation and test dates. Show the equity and drawdown.”

The first four use run/example/explain/reproduce. Requests five and six query curated local archives. Request seven uses `inspect-data` with a historical specification, evaluates the fixed portfolios and links the report, CSV and SVG. [Historical example](historical-workflow.md)

The skill should ask for material missing inputs, distinguish failed
from unavailable checks, and link actual artifacts. The [user guide](user-guide.md)
explains setup, inputs, source-version reproduction and private ZIP bundles.

No live trading, paid model usage, endpoint diagnostics, generated-code execution,
competition evaluation or automatic public sharing is part of this skill.
