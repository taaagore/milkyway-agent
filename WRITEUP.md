# MilkyWay Agent

## Problem
Rural households and small dairy farmers have no practical way to check 
milk for adulteration — the nearest lab is too far to reach, and they 
have no easy way to know what FSSAI's actual standards even say.

## Solution
The agent doesn't just label a sample adulterated or safe — it shows 
which FSSAI standard it checked against and why, so the verdict is 
something a person can actually trust and verify.

## Value
Dairy farmers get an easy way to check their own milk before selling 
it, and households can verify whether the milk they're buying is 
trustworthy enough — or switch to a provider they can trust if it isn't.

## Architecture

MilkyWay Agent uses a 3-node pipeline modeled on the agentic workflow 
patterns from the course (Day 4's expense-agent architecture):

1. **vision_screen** — calls the Gemini Vision API (gemini-2.5-flash) on 
   an uploaded lactometer photo, returning a numeric reading and a 
   self-reported confidence score.
2. **risk_reasoner** — compares that reading against species-specific 
   FSSAI-derived thresholds (cow: 28.0, buffalo: 30.0), producing a 
   verdict and a plain-language explanation.
3. **Routing decision** — a human-in-the-loop safeguard: if either the 
   vision confidence or the reasoning confidence falls below 0.80, the 
   case is escalated for manual review instead of returning a possibly-
   wrong confident answer.

## Course Concepts Demonstrated

- **Agent Skills** — FSSAI regulation grounding packaged as a Skill 
  (SKILL.md + reference.md), so the reasoner cites an actual standard 
  rather than hallucinating one.
- **Human-in-the-loop / guardrails** — confidence-based escalation, 
  modeled on the expense-agent pattern from Day 4.
- **Secure agentic coding** — identified and closed a real vulnerability: 
  the reference-data API initially allowed unauthenticated writes; found 
  and fixed (write access removed, GET-only retained).
- **Vibe coding with Antigravity** — scaffolded and iterated using 
  Antigravity IDE/CLI, with all agent-generated changes reviewed before 
  acceptance (including catching and rejecting unrequested scope creep).

## Real-World Testing and Findings

- Two end-to-end tests with live (non-mocked) photos confirmed both 
  pipeline branches: a low-confidence ambiguous photo correctly 
  triggered escalation; a higher-confidence photo correctly produced a 
  direct verdict.
- A genuine consistency issue was found and fixed: the same test photo 
  initially produced different verdicts across repeated runs. Setting 
  temperature=0 alone didn't resolve it — the real cause was prompt 
  ambiguity (the model reading unrelated numbers in cluttered images). 
  Tightening the prompt to explicitly exclude non-scale numbers fixed it.

## Known Limitations

- The lactometer-reading threshold is a simplified proxy for FSSAI's 
  actual legal standard (minimum SNF%: 8.3% cow, 9.0% buffalo, per the 
  FSS Food Products Standards 2011). Full compliance checking would 
  require combining the reading with a fat-percentage test via 
  Richmond's formula — out of scope for this prototype.
- Vision-model confidence is self-reported, not independently 
  validated — a known LLM calibration limitation.
- Not deployed to live infrastructure (Cloud Run wasn't viable without 
  a billed Google Cloud account); demonstrated via local execution and 
  recorded video instead.