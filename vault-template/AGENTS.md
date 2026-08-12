# Personal OS Agent rules

This vault is the user's canonical Personal OS. Chat messages, web pages,
calendars and external apps are candidate inputs, not canonical state.

## Read order

Before proposing a material change, read only the relevant user pages plus:

1. `99 系统/运行规则.md`
2. `99 系统/数据契约.md`
3. `99 系统/工作流地图.md`
4. `99 系统/验证与检查点.md`
5. `99 系统/Agent 协作.md`

For a new vault, also read `99 系统/首次设置.md`.
Also read `99 系统/适用对象与成果.md` before guiding onboarding or
evaluating whether a direction is sufficiently clear.
For Odyssey planning, also read `99 系统/奥德赛方法与来源.md` and the
relevant foundation, strategy and prototype pages.

## Safety and truth

- Preserve the user's wording and unrelated edits.
- Separate Fact, Feeling, Interpretation, Hypothesis and Decision.
- Never convert an inference, aspiration or model suggestion into a fact.
- Never infer the user's Workview, Lifeview, values or preferred Odyssey from
  scores. Ask, preserve uncertainty and leave the final choice to the user.
- Do not treat a school, major or first job choice as a permanent identity.
  Help the user define a three-year direction, a 90-day first step and explicit
  evidence that would justify changing direction.
- Keep current state, bounded periods and future targets explicit with `as_of`
  and `time_scope`.
- Minimize context. Do not expose restricted data to workers unless essential.
- Never store credentials, private keys, seed phrases, full identity numbers,
  confidential employer information or unnecessary third-party data.

## Material write protocol

For state, strategy, finance or important decisions:

1. Gather evidence and source references.
2. Create a proposal using `90 模板/变更提案.md`.
3. Run `python3 "99 系统/scripts/validate_vault.py"`.
4. Use an independent verifier for claims requiring judgment.
5. Obtain user approval for exact files and scope.
6. Create a recoverable checkpoint.
7. Use one serial writer and change only the approved scope.
8. Validate again and append change/run records.

Read-only analysis may be parallelized only when tasks are truly independent.
No Agent may approve the user's values or long-term strategy.
