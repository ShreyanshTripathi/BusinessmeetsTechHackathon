# ML models for the three agents

Three small models, one per MVP function. They sit next to the rules in `backend/shiftloop/agents/`
and return results in the backend's `Event` format (`predict.py`). The backend is not changed yet.

| Model | Question it answers | Data | Algorithm | Held-out result |
|---|---|---|---|---|
| Staffing | The day before: which stations will end up without qualified cover? | Synthetic, 26 weeks of the 2026 ramp (`generate_staffing_data.py`) | Logistic regression | ROC AUC 0.85; 63% of the top 3 flagged stations per shift really had a gap (simple rule: 42%) |
| General Assembly | At shift start: will this line team miss today's target? | UCI garment productivity, 1,197 team-days | Random forest | ROC AUC 0.77; catches 65% of misses |
| Fire & Safety | How serious could this reported near miss have been? | IHM Stefanini industrial safety reports (Kaggle), 425 reports | TF-IDF + logistic regression | 54% on 3 levels; 65% of high-potential reports caught; unsure cases go to an expert |

Both public datasets are stand-ins because no Tesla data is available. In production each model is
retrained on the plant's own data; the interface stays the same.

## Rules the models follow

- **Teams and stations, never individuals.** No names, no per-person absence history, no performance data.
- **Only what is known in advance.** Columns recorded after the shift (incentive, idle time) are left out.
- **Unsure means expert review.** The safety model hands low-confidence reports to a person.
- **Every model has a card** in `models/*.card.json`: data, split, metrics, limits, and what it must not be used for.

## Run

```bash
cd ml
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python generate_staffing_data.py   # writes data/staffing_shifts.csv
python train_staffing.py
python train_assembly.py
python train_safety.py
python predict.py                  # demo: all three models on one scenario
```
