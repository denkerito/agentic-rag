# AGENTS.md

## Interaction Protocol
- Proceed autonomously only for deterministic tasks, contained changes or obvious refactorings.
- For high-impact changes with several valid solutions, architectural tasks or complex new features:
  - Do not make risky assumptions.
  - Briefly present the main trade-offs and ask a few targeted questions before writing the plan or touching code.

## Language
- Documentation (README, AGENTS.md, `vision.md`, `docs/`), commit messages and pull requests are in English.
- Code (names, comments, docstrings, messages), the agent's prompt and the dataset (`data/`) stay in Italian: changing the prompt would change the agent measured in the `finale` experiment.

## Ground truth
- The 12 questions in `eval/ground_truth/` are the development set.
- The 50 questions in `eval/ground_truth_finale/` are the test set of the `finale` experiment (2026-10-26). They were off-limits to the assistant until the experiment and the judge validation were over. Since 2026-11-11 they are visible and in git, so they no longer measure anything new: they are not used to tune prompts, thresholds, tools or metrics, and any future change to the agent must be measured on a new test set.
- A new test set gets the same protection until its experiment is over. Its folder and the private reports of the labels that use it (`eval/reports/private/esperimenti/`) are not opened, read or printed: the assistant knows only their structure. The harness code reads them at runtime, and the assistant receives only count outputs (e.g. `tools/controlla_ground_truth.py`) and the public reports.
- The agent and the application modules never access the ground truth files.

## Agent Guiding Principles
1. **Numbers are never made up:** calculations, aggregations and period comparisons go **always and only** through read-only SQL queries (relational database). The agent does not do mental arithmetic or estimate figures in the prompt.
2. **Mandatory, verifiable sources:** every conclusion or financial statement must come with the unique IDs of the supporting sources (`FATT-*`, `CTR-*`, `DOC-*`, `MOV-*`, etc.), so the accountant can open and check the data.
3. **Honesty about undocumented causes:** if an anomaly or numerical change has no match in the documents (e.g. the November travel-expense spike), the agent must state explicitly that the cause is not documented in the sources, without guessing or inventing.
4. **Transparent reasoning:** the agent must make the intermediate steps of the investigation visible (queries run, documents retrieved through RAG) so the user can validate the line of reasoning.
