# Repository collaboration rules

This repository contains a reusable Personal OS framework, not one person's
canonical life data.

## Scope

- Framework code and documentation live at the repository root.
- `vault-template/` must remain generic and safe to publish.
- A user's real Personal OS should be generated into a separate directory with
  `scripts/init_vault.py`.

## Safety

- Never add real financial balances, medical records, identity numbers,
  credentials, wallet material, confidential employer information, or third
  party personal data to this repository.
- Examples must be fictional and obviously labeled.
- Do not claim that an AI can determine a user's values or make high-risk
  decisions on their behalf.

## Change protocol

Before completing a framework change:

1. Keep the architecture, templates, validator, and documentation consistent.
2. Run `python3 -m unittest discover -s tests -v`.
3. Run `python3 scripts/validate_vault.py --vault vault-template --template-mode`.
4. Explain any warning; errors block release.

Use the generated vault's own `AGENTS.md` when working with a user's life data.

