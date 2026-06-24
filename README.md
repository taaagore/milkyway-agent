# MilkyWay Agent

An AI agent that helps rural households and dairy farmers check milk for 
adulteration using a photo of a lactometer reading — grounded in real 
FSSAI regulation data, with human-in-the-loop escalation for ambiguous 
or implausible results.

Built for the Kaggle 5-Day AI Agents Intensive Vibe Coding Course 
capstone, "Agents for Good" track.

## The Problem

Rural households and small dairy farmers have no practical way to check 
milk for adulteration — the nearest lab is too far to reach, and they 
have no easy way to know what FSSAI's actual standards even say.

## How It Works

A 3-node pipeline:
1. **vision_screen** — Gemini Vision API reads a lactometer scale value 
   from an uploaded photo
2. **risk_reasoner** — compares the reading against species-specific 
   FSSAI-derived thresholds, with citations to the actual standard
3. **Routing** — escalates to human review if confidence is too low, or 
   flags implausible readings as invalid, instead of guessing

## Tech Stack

- Flask (Python backend)
- Google Gemini Vision API (gemini-2.5-flash)
- Agent Skills (FSSAI regulation grounding)
- Built and iterated using Google Antigravity (IDE/CLI)

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with:
GEMINI_API_KEY=your_key_here

Run:
```bash
python app.py
```

Visit `http://localhost:5000`

## Documentation

- [DECISIONS.md](DECISIONS.md) — design decisions and rationale
- [PROGRESS.md](PROGRESS.md) — development log
- [WRITEUP.md](WRITEUP.md) — full capstone writeup

## Known Limitations

- Lactometer reading is a simplified proxy for FSSAI's actual SNF% 
  standard; full compliance checking would need a fat-content test too
- Vision-model confidence is self-reported, not independently validated
- Not deployed to live infrastructure — demonstrated via local execution