# Decisions Log

This document tracks the critical product and technical decisions made for the Milkyway Agent project.

## Pitch

**Problem**: Rural households and small dairy farmers have no practical way 
to check milk for adulteration — the nearest lab is too far to reach, and 
they have no easy way to know what FSSAI's actual standards even say.

**Solution**: The agent doesn't just label a sample adulterated or safe — 
it shows which FSSAI standard it checked against and why, so the verdict 
is something a person can actually trust and verify.

**Value**: Dairy farmers get an easy way to check their own milk before 
selling it, and households can verify whether the milk they're buying is 
trustworthy enough — or switch to a provider they can trust if it isn't.

## Test Method

**Chosen: Lactometer reading** (decided Jun 23)

Why: Detects water dilution, the most common adulteration in rural milk 
supply. Reading a gauge value off a photo is a reliable vision task — 
unlike judging plain milk's appearance directly, which was rejected as 
scientifically indefensible (adulterants like water, starch, and 
detergent don't visibly change milk's appearance to a camera).

Rejected alternatives:
- Iodine/starch test — narrower detection scope (starch only)
- pH strip — hardest vision task, ambiguous color gradients

## Architecture

3-node pipeline, modeled on the Day 4 expense-agent pattern:

1. `vision_screen` — reads the lactometer scale value from the photo, 
   outputs `lactometer_reading` (float) and `read_confidence` (0-1)
2. `risk_reasoner` — compares reading against FSSAI-derived threshold, 
   outputs `verdict`, `explanation`, `risk_confidence`
3. Routing — escalates to human review if confidence falls below threshold

### FSSAI Actual Legal Standard (for reference)
Source: FSS (Food Products Standards and Food Additives) Regulations, 2011, 
General Standard for Milk and Milk Products, Compendium v.XXVI (20.12.2022)

| Milk Type | Min Fat % | Min SNF % |
|---|---|---|
| Buffalo Milk | 5.0 | 9.0 |
| Cow Milk | 3.2 | 8.3 |

Our prototype uses lactometer reading alone (28.0 cow / 30.0 buffalo) as a 
simplified proxy for these SNF minimums, since full SNF determination 
requires combining lactometer reading with fat% via Richmond's formula — 
out of scope for this capstone, noted as a clear next step.

## Open Decisions

- [x] Confidence threshold for human-escalation: 0.8 (chosen Jun 23) — 
  prioritizes trustworthy verdicts over convenience, since false 
  confidence undermines the core value proposition more than an 
  occasional "needs human check" response does.
- [x] App asks user to select milk type (cow/buffalo) before/with photo 
  upload, so the correct threshold gets applied — avoids misclassifying 
  buffalo milk against cow thresholds or vice versa.