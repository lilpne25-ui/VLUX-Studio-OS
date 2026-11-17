# V0.5 Pilot — EP011 vs EP021

**Status:** complete for analysis. Training remains intentionally blocked.

This pilot runs the real Attention Lab pipeline on two authorized copies of VLUX
episodes. It is a **benchmark between two different episodes**, not a controlled
A/B test: the topics, hooks and visual treatments differ, so no causal claim is
possible.

## 1. Scope and authorization

| Item | EP011 | EP021 |
| --- | --- | --- |
| Role in pilot | Earlier reference | Recent VLUX episode |
| Source | Authorized local copy | Authorized local copy |
| Format | 540×960, ~22.7 s, H.264/AAC | 540×960, ~22.9 s, H.264/AAC |
| Permission recorded | `authorized_analysis_only` | `authorized_analysis_only` |
| Training eligibility | Excluded by design | Excluded by design |
| Platform results | User-provided screenshot, measurement date unknown | None recorded |
| Commercial results | None (no leads/revenue verified) | None |

The copies live under the local, git-ignored `data/` directory. The videos,
contact sheets and first frames are **not** published. No OCR or ASR was
available; on-screen text was read through an AI-assisted visual review of
private contact sheets and is labeled `AI_ASSISTED_VISUAL_REVIEW`.

## 2. What was measured (observed facts)

These numbers come from FFprobe/OpenCV on the authorized copies. They describe
the files, not their business performance.

| Fact | EP011 | EP021 | Difference |
| --- | ---: | ---: | --- |
| Duration | 22.67 s | 22.87 s | +0.20 s |
| Cuts detected | 11 | 4 | −7 |
| Cuts before 3 s | 1 | 0 | −1 |
| Average shot | 1.89 s | 4.57 s | +2.68 s |
| Motion, full video | 12.12 | 5.95 | −6.18 |
| Motion, first 3 s | 11.79 | 8.15 | −3.64 |
| Mean brightness (0–255) | 81.76 | 50.06 | −31.70 |
| Mean contrast (0–255) | 66.01 | 40.75 | −25.26 |
| Edge density | 0.0266 | 0.0238 | −0.0028 |
| Near-static samples | 5.2 % | 15.5 % | +10.3 pp |
| Silence ratio | 0.0 | 0.0 | 0 |

Reading: EP011 is faster, brighter and more visually active. EP021 holds shots
longer and contains a larger near-static share. Neither fact proves that one
episode is better; a calm shot can be the right choice.

## 3. What was estimated (heuristic, not validated)

Scores are 0–100 with explicit evidence and coverage. They are an editorial
policy, not a trained model and not a virality prediction.

| Dimension | EP011 | EP021 | Confidence |
| --- | ---: | ---: | --- |
| Hook | 90 | 69 | medium |
| Narrative | 90 | 90 | low |
| Production | 84 | 78 | medium |
| Commercial value (message completeness) | 90 | 90 | low |
| Overall | 88 | 81 | low |

Important: “commercial value” here means the metadata contains audience,
problem, solution and CTA fields. It does **not** mean sales, leads or demand.
The commercial results layer is separate and remains `NOT_AVAILABLE`.

The A/B contract reports one estimate gap above its reporting threshold: the
hook favors EP011 by 21 points. Narrative and commercial estimates are equal;
production differs by 6 points. None of these differences is a verdict.

AI-assisted visual reading (non-human, not a preference):

- **EP011:** hook “¿NO PUEDES EDITARLO?”, consequence “REDIBUJAR = HORAS”,
  solution/evidence around Autodesk Fusion/Autotimeline and editable history,
  CTA “Comenta: CAD”. The video itself discloses “Recreación 3D conceptual” and
  “no es la interfaz de Autodesk”.
- **EP021:** hook “PROMESA DE ENTREGA ¿TIENES CAPACIDAD?”, capacity deficit
  (11 needed vs 7 available), planning solution, closing question CTA and VLUX
  logo. The video itself discloses “CASO SIMULADO · DATOS FICTICIOS”.

## 4. Human-judgment differences

**There are none recorded.** No identified person has rated either episode on
the 1–5 dimensions (hook, narrative, production, commercial value, CTA,
clarity). AI-assisted notes are excluded from the human layer by design, and
anonymous ratings are excluded from the training gate.

Consequently, the A/B contract returns:

```text
decision_status: HUMAN_REVIEW_AND_RESULTS_REQUIRED
human_preferences: NOT_AVAILABLE
commercial_results: NOT_COMPARABLE
automatic_winner: null
```

To obtain this layer, a named evaluator must record a 1–5 evaluation for each
episode. Until then, “which is better for the audience?” remains unanswered.

## 5. Needed improvements

### EP021 (recent episode)

1. **Hook cadence:** zero detected cuts before 3 s. The opening may read as
   static in a vertical feed.
2. **First-frame luminance:** 21.06/255. The first sample is dark; mobile
   legibility may suffer.
3. **Near-static share:** 15.5 % of samples. Either shorten the static segment
   or make its narrative purpose explicit.
4. **Measurement:** no platform or commercial records are attached, so nothing
   can be validated against outcomes.

### EP011 (reference)

1. The heuristic flags no creative gap in hook, CTA, rhythm or silence.
2. The real gap is **measurement**: platform metrics are a user-provided
   screenshot with an unknown measurement date, and there are no verified
   leads, meetings or revenue. These numbers cannot validate the creative
   estimate.
3. The video is a conceptual recreation, not real Autodesk UI. Any claim about
   product behavior must respect that disclosure.

## 6. First change to test

**Change one thing in EP021:** introduce a deliberate visual change before 2 s
(cut, reveal or transition) while keeping the topic, script, offer and CTA
constant.

- **Hypothesis:** a visible change in the opening reduces early drop-off.
- **Primary metric:** 3-second retention, when a real measurement exists.
- **Secondary:** average watch time and saves.
- **Design:** EP021 current version vs EP021 with the new opening. Do not
  compare EP011 vs EP021 as if it were a controlled test.
- **Stop condition:** if retention does not improve, revert to the current
  opening and test the next single variable (first-frame luminance).

This is a proposal, not a result. No platform experiment has been run.

## 7. What this pilot proves — and what it does not

**Proves**

- The pipeline imports authorized local copies, computes objective facts,
  persists Attention Lab contracts, compares A/B layers and blocks training.
- Missing human and commercial evidence stays missing instead of being
  imputed.
- The dashboard and CLI read the same SQLite contracts.

**Does not prove**

- That EP011 is “better” than EP021, or that either will perform well.
- That any visual feature causes retention, leads or sales.
- That a model has been trained. Training state remains
  `NO_TRAINING_INSUFFICIENT_DATA`.

## 8. Reproduce

```powershell
# Local paths; the media stays git-ignored.
python -m vlux_ci.cli --db data/vlux.sqlite import data/review/pilot/EP011-pilot.mp4 `
  --episode EP011 --version v0.5-pilot --source-kind review `
  --permission authorized_analysis_only --provenance LOCAL_AUTHORIZED_COPY

python -m vlux_ci.cli --db data/vlux.sqlite attention 1
python -m vlux_ci.cli --db data/vlux.sqlite attention 2
python -m vlux_ci.cli --db data/vlux.sqlite ab --a 1 --b 2
python -m vlux_ci.cli --db data/vlux.sqlite learning-status
```

The full JSON contracts and the numeric platform excerpt remain in the local,
git-ignored `reports/v05/` directory.
