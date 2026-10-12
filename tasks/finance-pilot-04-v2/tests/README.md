# Verifier operation

`test.sh` grades the candidate output directory with a self-contained objective
assertion processor. There is no host bridge, no judge round-trip and no network
dependency: the whole reward is produced inside this container.

## Flow

1. `test.sh` clears any stale `reward.json` / `reward.txt`, then runs
   `tests/grade.py --output-dir /workspace/output --log-dir /logs/verifier`.
2. `grade.py` reads the trusted input copies under `tests/input-data/`,
   recomputes every expected value from the attached originals, and evaluates the
   47 assertions declared in `tests/assertions.json` against the candidate
   artifacts (`funding_results.json`, `risk_ledger.csv`, `action_memo.md`).
3. It writes `report.json` (always) and `reward.json` (only on a valid score).

## Reward

```
reward = min(P / S, cap)
```

`P` is the absolute count of passed assertions and `S` the frozen scale (47,
equal to the assertion count). Absolute counts are used rather than a ratio
because a batch mixes tasks of very different difficulty; `S` is frozen per
package and never renormalized against the batch maximum, so a candidate cannot
influence its own scale through other samples in the same batch.

Critical-error caps only ever lower a score. They are triggered by outcome
assertions, not by reviewer judgement:

| cap | assertion | triggers on |
|---|---|---|
| 0.5 | `R1.contract-params` | contract multiplier / unit magnitude wrong |
| 0.7 | `R1.funding-understatement` | a positive funding gap reported as zero |
| 0.6 | `R4.call-put-direction` | call/put mapped to the wrong side |
| 0.7 | `R5.tp03-disposition` | a delivery-month 1-lot fix approved as compliant |

## Status vocabulary

| status | meaning | reward written | in valid denominator |
|---|---|---|---|
| `graded` | complete valid scoring | yes | yes |
| `graded_candidate_defect` | candidate artifacts missing/broken, scored as found | yes | yes |
| `verifier_failure` | trusted input or scoring dependency fault | **no** | no |
| `not_run` | not executed | no | no |

A verifier-side fault leaves a `verifier_failure` report and no reward file, so
it is recorded separately from a candidate legitimately scoring zero. Trusted
input corruption (missing DOCX tables, changed normative multiplier clause) is a
`verifier_failure`, never a zero.

## Calibration

Author-side runs (`python3 tests/grade.py --output-dir ...`):

| artifact | reward | notes |
|---|---|---|
| `solution/reference` | 1.00 | derived oracle, 47/47 |
| `challenges/acceptable-alternative` | 1.00 | reordered arrays, UTC timestamps, different wording — must not be penalized |
| `challenges/numeric-wrong` | 0.70 | R10 funding gap reported as 0 → `CE.funding` |
| `challenges/semantic-wrong` | 0.70 | TP03 approved as compliant → `CE.disposition` |

Per-round conclusions belong in `private/evaluation/calibration-<round>.json`;
see the "校准闭环" section of `references/scorer-construction.md`.

## Still `not_run`

Native Docker build, Harbor/Forge attempts, resource cleanup, and a genuine
independent-solver rollout. `objective.py` and `verifier.py` are the superseded
host-bridge verifier and are retained only as historical artifacts of the prior
contract; `grade.py` is the live entry point.
