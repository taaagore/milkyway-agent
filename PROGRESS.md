## Jun 24 — Live API integration working end-to-end

- Fixed Gemini quota issue: gemini-2.0-flash was deprecated/hitting a 
  known free-tier provisioning bug; switched to gemini-2.5-flash, resolved.
- First real (non-mocked) pipeline run: vision_screen() correctly read 
  a lactometer scale value (15.0) from a real photo, flagged low 
  confidence (0.0) due to photo ambiguity (product listing image, not 
  a clean test photo).
- risk_reasoner correctly computed RISKY verdict against real FSSAI-
  derived threshold (28.0 for cow).
- route_decision correctly escalated to human review due to low vision 
  confidence — core human-in-the-loop safety behavior confirmed working 
  with live data, not just mocks.
- Second real-data test (test2.jpg, cleaner reference photo): 
  vision_screen() returned reading 22.0 with confidence 0.85 (high). 
  risk_reasoner correctly flagged RISKY (below cow threshold 28.0) with 
  confidence 0.97. route_decision correctly auto-approved (no escalation) 
  since both confidences exceeded 0.80 threshold. Confirms both the 
  escalation path (test1) and confident-verdict path (test2) work 
  correctly with live, non-mocked data.

## Run-to-run consistency issue found (Jun 24)
Same test2.jpg photo produced different verdicts (RISKY/SAFE) across 
4 manual test runs, despite OCR confidence self-reporting consistently 
high (~95%). Root cause: no temperature setting on Gemini API call, 
allowing sampling randomness on a task that should be deterministic.
Fix: set temperature=0 in generation config.
Key lesson: self-reported confidence does not detect this kind of 
instability — confidence and consistency are not the same thing.
## Temperature fix + prompt tightening (Jun 24)
- temperature=0 alone didn't fix run-to-run variance on test2.jpg
- Root cause: ambiguous stock photo with multiple competing numbers
- Fix: tightened vision_screen() prompt to explicitly ignore product 
  codes, labels, packaging numbers — read only graduated scale markings
- Result: reading now consistent across all runs on same image
- Escalation on test2.jpg is correct behavior (genuinely ambiguous image,
  low confidence → human review triggered appropriately)
## Jun 24/25 — Demo prep + GitHub setup
- Found test2.jpg's escalation behavior was actually correct (no clear 
  liquid line in stock photos), not a bug
- Found test4.jpg as a genuine clean case: reading 12.0, confidence 0.9, 
  RISKY verdict, not escalated -- confirmed via direct pipeline test
- GitHub repo created and pushed: github.com/taaagore/milkyway-agent
- Caught and fixed an accidental API key commit in README.md before 
  it reached GitHub (push protection blocked it, amended commit, 
  re-pushed clean)
- Recording plan finalized: test4.jpg (confident RISKY) + test1.jpg 
  (escalation) as the two demo cases