# Conversation summary (Shahla)

**Session:** Tesla Giga Berlin hackathon, 25–26 Sep 2026 · **Full log:** [conversation_log.md](conversation_log.md)

## Goal

Challenge 2, *Built for the Job*: an AI product that makes one Tesla production role (manufacturing engineer
or production supervisor) meaningfully better. Judged on problem quality, then innovation, then fit.

## How the idea developed

1. **First ideas.** Voice-first shift handover ("Shift Loop"), capturing unwritten floor fixes, and a bridge
   from supervisor workarounds to engineer change requests. Dropped the translation angle: English is a
   hiring requirement, so language is not the real pain.
2. **Giga Berlin only.** Shahla asked to stop talking about general German rules and focus on the plant
   itself. Current facts (Sep 2026) that shape both roles:
   - ramp from ~5,000 to **7,500 Model Y per week from mid-October 2026**, with special shifts
   - ~2,000 new hires in 2026 plus 500 temps made permanent, so many operators are new
   - high sick leave (IG Metall reports ~15% for permanent staff) and reported overload
   - works council election March 2026 ("Giga United" 40.4%, IG Metall 31.1%)
3. **Sketch 1** ([sketch_1_first_idea.jpg](sketch_1_first_idea.jpg)): an AI dashboard with voice input for the
   supervisor, fed by agents for staffing, assembly and fire & safety. The key word on the sketch was
   **interdependent**: one change (e.g. a product change) ripples through several agents and ends in one
   decision for the supervisor.
4. **Sketch 2** ([sketch_2_ai_for_factories.jpg](sketch_2_ai_for_factories.jpg)) → final architecture
   **"AI for Factories"** ([ai_for_factories.png](ai_for_factories.png)):
   - a Gen AI model as the decision-making brain, plus a dashboard for the supervisor
   - one hyper-specific LLM per factory function: Staffing, Casting, Plastics, General Assembly Line,
     Fire & Safety, Support
   - **MVP:** Staffing, General Assembly Line, Fire & Safety (same scope as Shreyansh's ShiftLoop build)

## Decisions

| Topic | Choice |
|---|---|
| Role | Production supervisor |
| MVP functions | Staffing, General Assembly Line, Fire & Safety |
| Staffing rule | Qualifications and coverage only, never individual performance (sensitive at Giga Berlin after the home-visit controversy) |
| Data | Public datasets as stand-ins (no Tesla data); synthetic data for staffing |
| Shahla's part | ML models (`ml/`), then the frontend; backend unchanged for now |

## What was built: `ml/`

Three small models that return results in the backend's `Event` format. Details in [../../ml/README.md](../../ml/README.md).

| Model | Question | Data | Held-out result |
|---|---|---|---|
| Staffing (logistic regression) | The day before: which stations will lack qualified cover? | Synthetic, 26 weeks of the 2026 ramp, same layout as the backend | ROC AUC 0.85; 63% of top-3 flags per shift correct (simple rule: 42%) |
| General Assembly (random forest) | At shift start: will this team miss its target? | UCI garment productivity, 1,197 team-days | ROC AUC 0.77; catches 65% of misses |
| Fire & Safety (TF-IDF + logistic regression) | How serious could this near miss have been? | IHM Stefanini safety reports (Kaggle), 425 reports | 54% on 3 levels; 65% of high-potential reports caught; unsure cases go to an expert |

Design rules taken from Shreyansh's convos: teams and stations, not individuals; leaky after-the-shift
columns left out; "unsure → expert review"; a model card per model (`ml/models/*.card.json`) for oversight.

## Not yet done / open

- The models are not connected to the backend agents or the dashboard yet (`ml/predict.py` is ready for it).
- The safety model is unsure on about half the reports (small dataset).
- In the garments data, product changes barely affect the prediction: don't claim that in the pitch.
- The staffing score shows the pipeline works; it learned the rules built into the synthetic data.
- Frontend work (Shahla) is next.

## Run

```bash
cd ml && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python predict.py
```
