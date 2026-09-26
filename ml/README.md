# ML models for the three agents

One **random forest** per MVP function makes the predictions. **Claude explains them**: each prediction
comes with its drivers (which inputs pushed it up or down), and `explain.py` turns those into two or three
plain sentences for the supervisor. Claude never makes or changes a prediction. Results come back in the
backend's `Event` format (`predict.py`). The backend loads them through `backend/shiftloop/ml_bridge.py`.

| Model | Question it answers | Data | Model | Held-out result | Model it replaced |
|---|---|---|---|---|---|
| Staffing | The day before: which stations will end up without qualified cover? | Synthetic, 26 weeks of the 2026 ramp (`generate_staffing_data.py`) | Random forest, 300 trees | ROC AUC 0.862; 62% of the top 3 flagged stations per shift really had a gap | Logistic regression 0.850 / 63% (a tie on top 3); simple rule 0.812 / 42% |
| General Assembly | At shift start: will this line team miss today's target? | UCI garment productivity, 1,197 team-days | Random forest, 300 trees | ROC AUC 0.770; catches 65% of misses at a 50% cut-off | Logistic regression 0.758 / 77% (lower AUC, more misses caught at 50%) |
| Fire & Safety | How serious could this reported near miss have been? | IHM Stefanini industrial safety reports (Kaggle), 425 reports | TF-IDF → 50 SVD components → random forest | 54% on 3 levels; 74% of high-potential reports caught; 18% of them rated low | TF-IDF + logistic regression: 54% / 65% / 17% |

Notes on the comparison:
- **Staffing:** forest settings were chosen on an August validation month, then tested once on September.
- **Safety:** forests handle thousands of sparse word columns badly (plain TF-IDF + forest: 51%, 23% of
  high-potential reports rated low). Compressing the text to 50 SVD components fixes most of that. These
  settings were picked on the same cross-validation that is reported, so the numbers are slightly optimistic.
  More reports go to the expert as unsure (61% vs 50%).

Both public datasets are stand-ins because no Tesla data is available. In production each model is
retrained on the plant's own data; the interface stays the same.

## Rules the models follow

- **Teams and stations, never individuals.** No names, no per-person absence history, no performance data.
- **Only what is known in advance.** Columns recorded after the shift (incentive, idle time) are left out.
- **Unsure means expert review.** The safety model hands low-confidence reports to a person.
- **Every model has a card** in `models/*.card.json`: data, split, metrics against the replaced model,
  reference values for explanations, limits, and what it must not be used for.
- **Claude only explains.** It gets the prediction, evidence and drivers, is told to use only those facts,
  and never judges individuals. Without credentials it falls back to a template (`SHIFTLOOP_OFFLINE=1` forces this).

## How a prediction is explained

1. The forest predicts (e.g. 89% risk that S18 has no qualified cover tomorrow night).
2. `drivers.py` resets each input to a typical value and measures how much the risk changes
   (operator level 1 instead of the usual 2: +42 points). For text, it removes each word instead.
3. `explain.py` sends the prediction and drivers to Claude (`claude-haiku-4-5`, override with
   `SHIFTLOOP_SUMMARY_MODEL`), which writes the explanation in English, German or Polish.

## Run

```bash
cd ml
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # or: uv venv --python 3.11 && uv pip install -r requirements.txt
python generate_staffing_data.py   # writes data/staffing_shifts.csv
python train_staffing.py
python train_assembly.py
python train_safety.py
python predict.py                  # demo: all three models on one scenario, with explanations
python -m pytest                   # 24 tests: forests, baselines, drivers, events, Claude layer
```
