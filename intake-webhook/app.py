import datetime
import json
import os
import pathlib
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

INTAKE_DIR = pathlib.Path(os.environ.get("INTAKE_DIR", "/data/intake"))
INTAKE_DIR.mkdir(parents=True, exist_ok=True)


class Sub(BaseModel):
    name: str
    email: str
    company: Optional[str] = ""
    answers: dict = {}
    friction: str = ""
    stalling: str = ""
    gaps: Optional[dict] = {}
    routing: Optional[str] = ""
    source: Optional[str] = "bizbuilders.ai/intake"
    submitted_at: Optional[str] = ""


class DiagnosticAnswer(BaseModel):
    question_id: str
    answer_value: int
    answer_label: str = ""
    dimension: str = ""


class DiagnosticSub(BaseModel):
    name: str
    email: str
    company: Optional[str] = ""
    role: Optional[str] = ""
    industry: Optional[str] = ""
    diagnostic_type: str = "tbtx"
    source: Optional[str] = "transformby10x.ai/diagnostic"
    utm_source: Optional[str] = ""
    utm_campaign: Optional[str] = ""
    answers: List[DiagnosticAnswer]


DIAGNOSTICS: Dict[str, dict] = {
    "tbtx": {
        "brand": "TransformBy10X",
        "title": "Digital Fog Diagnostic",
        "audience": "For people carrying too much in their head",
        "path": "/diagnostic?type=tbtx",
        "source": "transformby10x.ai/diagnostic",
        "submit_label": "Show Me What's Keeping Me Stuck",
        "cta": "Get the Fog-Lift Kit",
        "route_to": "https://transformby10x.ai/foglift-kit.html",
        "form_label": "/// DIGITAL FOG CHECK ///",
        "result_label": "Your Digital Fog readout",
        "intro": "See what is draining your attention, stalling good ideas, and making simple work feel heavier than it should.",
        "questions": [
            {
                "id": "tbtx_q1",
                "dimension": "clarity",
                "label": "How clear is the outcome you are trying to build over the next 30 days?",
                "low": "Very clear",
                "high": "Mostly foggy",
            },
            {
                "id": "tbtx_q2",
                "dimension": "attention",
                "label": "How often do you switch tools, tabs, notes, or ideas before finishing the thing you started?",
                "low": "Rarely",
                "high": "Constantly",
            },
            {
                "id": "tbtx_q3",
                "dimension": "folders",
                "label": "How easy is it to find the files, links, prompts, assets, and decisions for one active project?",
                "low": "Easy",
                "high": "Hard",
            },
            {
                "id": "tbtx_q4",
                "dimension": "markdowns",
                "label": "How much of your thinking exists in reusable briefs, checklists, docs, or templates?",
                "low": "Most of it",
                "high": "Almost none",
            },
            {
                "id": "tbtx_q5",
                "dimension": "scripts",
                "label": "How many repeated tasks still require you to manually remember each step?",
                "low": "Very few",
                "high": "Most of them",
            },
            {
                "id": "tbtx_q6",
                "dimension": "protocols",
                "label": "When work gets messy, do you have a rule for what to do next?",
                "low": "Yes",
                "high": "No",
            },
            {
                "id": "tbtx_q7",
                "dimension": "ai_readiness",
                "label": "How ready is your current setup for AI or agents to produce useful work without heavy babysitting?",
                "low": "Ready",
                "high": "Not ready",
            },
            {
                "id": "tbtx_q8",
                "dimension": "handoff",
                "label": "Could someone else understand your current workflow from the artifacts you already have?",
                "low": "Yes",
                "high": "No",
            },
            {
                "id": "tbtx_q9",
                "dimension": "offer",
                "label": "How clearly can you explain the transformation you help people achieve?",
                "low": "Clearly",
                "high": "Not clearly",
            },
            {
                "id": "tbtx_q10",
                "dimension": "capture",
                "label": "When someone is interested in your work, how reliable is the path from interest to next action?",
                "low": "Reliable",
                "high": "Leaky",
            },
            {
                "id": "tbtx_q11",
                "dimension": "momentum",
                "label": "How often do good ideas stall because the structure to execute them is not already there?",
                "low": "Rarely",
                "high": "Often",
            },
            {
                "id": "tbtx_q12",
                "dimension": "measurement",
                "label": "How clearly can you tell what is working, what is stalled, and what should be changed?",
                "low": "Clearly",
                "high": "Unclear",
            },
        ],
    },
    "bizbuilders": {
        "brand": "BizBuilders AI",
        "title": "Business Friction Diagnostic",
        "audience": "For teams doing work their tools were supposed to remove",
        "path": "/diagnostic?type=bizbuilders",
        "source": "bizbuilders.ai/roadmap",
        "submit_label": "Show Me Where the Work Comes Back",
        "cta": "Get My BizBuilders Roadmap",
        "route_to": "https://bizbuilders.ai/roadmap",
        "form_label": "/// BUSINESS FRICTION CHECK ///",
        "result_label": "Your business friction readout",
        "intro": "Find where AI, automation, and disconnected tools keep handing work back to your team.",
        "questions": [
            {
                "id": "bbai_q1",
                "dimension": "offer",
                "label": "How clearly is your core offer packaged, named, scoped, and tied to a measurable business outcome?",
                "low": "Very clearly",
                "high": "Unclear",
            },
            {
                "id": "bbai_q2",
                "dimension": "audience",
                "label": "How specific is your target buyer, use case, urgency, and trigger event?",
                "low": "Specific",
                "high": "Too broad",
            },
            {
                "id": "bbai_q3",
                "dimension": "capture",
                "label": "How reliable is your lead capture path from traffic source to stored contact record?",
                "low": "Reliable",
                "high": "Leaky",
            },
            {
                "id": "bbai_q4",
                "dimension": "qualification",
                "label": "How consistently do you qualify leads before sales or fulfillment time is spent?",
                "low": "Consistently",
                "high": "Inconsistently",
            },
            {
                "id": "bbai_q5",
                "dimension": "crm",
                "label": "How cleanly do new leads enter a CRM, pipeline, owner assignment, and follow-up sequence?",
                "low": "Cleanly",
                "high": "Messy",
            },
            {
                "id": "bbai_q6",
                "dimension": "folders",
                "label": "How organized are campaign assets, SOPs, client files, sales docs, and delivery materials?",
                "low": "Organized",
                "high": "Scattered",
            },
            {
                "id": "bbai_q7",
                "dimension": "markdowns",
                "label": "How much of your sales, delivery, and operations knowledge is documented in reusable templates?",
                "low": "Most of it",
                "high": "Almost none",
            },
            {
                "id": "bbai_q8",
                "dimension": "scripts",
                "label": "How many repeated operational tasks still depend on manual copy/paste, memory, or one person's habits?",
                "low": "Few",
                "high": "Many",
            },
            {
                "id": "bbai_q9",
                "dimension": "protocols",
                "label": "How explicit are your rules for lead routing, escalation, approval, delivery QA, and ownership?",
                "low": "Explicit",
                "high": "Implicit",
            },
            {
                "id": "bbai_q10",
                "dimension": "delivery",
                "label": "How repeatable is your client/customer delivery process from kickoff to outcome?",
                "low": "Repeatable",
                "high": "Reinvented each time",
            },
            {
                "id": "bbai_q11",
                "dimension": "analytics",
                "label": "How clearly can you connect source, campaign, diagnostic, purchase, and follow-up behavior?",
                "low": "Clearly",
                "high": "Cannot connect",
            },
            {
                "id": "bbai_q12",
                "dimension": "automation",
                "label": "How well do your automations support the workflow instead of creating more exceptions?",
                "low": "They support it",
                "high": "They create exceptions",
            },
            {
                "id": "bbai_q13",
                "dimension": "ai_readiness",
                "label": "How safely could an AI agent draft, route, or execute work using your existing context?",
                "low": "Safely",
                "high": "Not safely",
            },
            {
                "id": "bbai_q14",
                "dimension": "governance",
                "label": "How clear are the approval rules for money, customer promises, production changes, or brand-sensitive work?",
                "low": "Clear",
                "high": "Unclear",
            },
            {
                "id": "bbai_q15",
                "dimension": "handoff",
                "label": "How easily can work move from marketing to sales to delivery without losing context?",
                "low": "Easily",
                "high": "Context gets lost",
            },
            {
                "id": "bbai_q16",
                "dimension": "scale",
                "label": "If demand doubled this month, how much would break in your current operating system?",
                "low": "Very little",
                "high": "A lot",
            },
        ],
    },
}

B2C_DIMENSION_LABELS = {
    "ai_readiness": "AI that needs constant babysitting",
    "attention": "constant switching",
    "capture": "interest that dies without a next step",
    "clarity": "too many possible next moves",
    "folders": "wasting time looking for what you need",
    "handoff": "context that only exists in your head",
    "markdowns": "re-solving the same thinking",
    "measurement": "not knowing what is actually working",
    "momentum": "good ideas that never get finished",
    "offer": "difficulty explaining what you do",
    "protocols": "not knowing what to do when work stalls",
    "scripts": "rebuilding repeated work",
}

B2B_DIMENSION_LABELS = {
    "ai_readiness": "AI that still needs babysitting",
    "analytics": "results that cannot be traced",
    "audience": "a buyer definition that is too broad",
    "automation": "automation creating exceptions",
    "capture": "interest that never becomes a stored lead",
    "crm": "follow-up depending on memory",
    "delivery": "delivery being rebuilt every time",
    "folders": "scattered assets and decisions",
    "governance": "unclear approval rules",
    "handoff": "context disappearing between teams",
    "markdowns": "knowledge trapped in people's heads",
    "offer": "an offer people do not immediately understand",
    "protocols": "unclear next steps and ownership",
    "qualification": "bad-fit leads reaching expensive people",
    "scale": "capacity that breaks under demand",
    "scripts": "repeated work being rebuilt by hand",
}

B2C_CONTEXT = {
    "creator": "You do not have an idea problem. Too many ideas and loose ends are competing for the same attention.",
    "consulting": "The work is not stuck because you have nothing to offer. The next clear move keeps getting buried under decisions.",
    "agency": "Client work, your own work, and constant switching are fighting for the same attention. Your priorities are paying the price.",
    "ecommerce": "Products, content, orders, and promotion are all asking to be first. The result is motion without a clean finish line.",
    "health": "Care work already demands attention. Scattered admin and unfinished decisions are taking what little focus remains.",
    "local": "Calls, messages, customers, and daily problems keep interrupting the work that would make tomorrow easier.",
    "saas": "Building, selling, supporting, and deciding are collapsing into the same day. Important work keeps losing the fight.",
}

B2B_CONTEXT = {
    "creator": "Content is not the first problem. The break is between attention, a clear offer, captured interest, and accountable follow-up.",
    "consulting": "Work is leaking between interest, scope, delivery, and follow-up. Your team is filling those gaps by hand.",
    "agency": "Promises, client context, production work, and reporting are getting reconnected by people instead of carried by the workflow.",
    "ecommerce": "Campaign, purchase, support, and repeat-sale data are split apart. People are compensating for what the tools do not connect.",
    "health": "Trust depends on clean intake, careful follow-up, and controlled claims. Manual rescue work makes every gap riskier.",
    "local": "Searches, referrals, calls, and messages are entering through different doors. Follow-up depends too heavily on someone remembering.",
    "saas": "Acquisition, onboarding, product use, support, and expansion signals are not moving together. Teams are translating the gaps by hand.",
}


def get_config(diagnostic_type: str) -> dict:
    return DIAGNOSTICS.get(diagnostic_type, DIAGNOSTICS["tbtx"])


def category_for(score: int, max_score: int) -> str:
    ratio = score / max_score if max_score else 0
    if ratio <= 0.35:
        return "Clear"
    if ratio <= 0.55:
        return "Fragmented"
    if ratio <= 0.75:
        return "Stalled"
    return "Critical Fog"


def score_dimensions(answers: List[DiagnosticAnswer], diagnostic_type: str = "tbtx") -> Dict[str, dict]:
    grouped: Dict[str, List[int]] = {}
    for answer in answers:
        if not answer.dimension:
            continue
        grouped.setdefault(answer.dimension, []).append(answer.answer_value)

    labels = B2B_DIMENSION_LABELS if diagnostic_type == "bizbuilders" else B2C_DIMENSION_LABELS
    scores = {}
    for dimension, values in grouped.items():
        total = sum(values)
        max_total = len(values) * 5
        scores[dimension] = {
            "label": labels.get(dimension, dimension.replace("_", " ")),
            "score": total,
            "max_score": max_total,
            "severity": round(total / max_total, 2) if max_total else 0,
        }
    return scores


def audience_context(industry: str, diagnostic_type: str) -> str:
    key = (industry or "").strip().lower()
    contexts = B2B_CONTEXT if diagnostic_type == "bizbuilders" else B2C_CONTEXT
    for token, context in contexts.items():
        if token in key:
            return context
    if diagnostic_type == "bizbuilders":
        return "The business is relying on people to remember, chase, translate, and reconnect work that the workflow should carry."
    return "Too much is competing for your attention, so starting and finishing both cost more energy than they should."


def build_report(sub: DiagnosticSub, category: str, dimension_scores: Dict[str, dict]) -> dict:
    ordered = sorted(dimension_scores.items(), key=lambda item: item[1]["severity"], reverse=True)
    top_gaps = ordered[:4]
    gap_labels = [details["label"] for _, details in top_gaps]
    primary_gap = gap_labels[0] if gap_labels else "the first point of friction"

    if sub.diagnostic_type == "bizbuilders":
        summary = (
            f"Your answers show a {category.lower()} business-friction pattern. "
            f"The biggest break is {primary_gap.lower()}. That is where work is coming back to people, slowing delivery, and eating margin."
        )
        roadmap = [
            f"Fix {primary_gap.lower()} before touching the rest.",
            "Trace one live lead or client job and mark every place it stalls, repeats, or loses context.",
            "Remove one repeat loop and give one person clear ownership of the repaired path.",
            "Run the repaired path three times before deciding what should be automated.",
        ]
        first_moves = [
            "Name the exact point where work returns to a person.",
            "Find the duplicate step, tool, or approval creating the loop.",
            "Measure the time and margin lost before adding another tool.",
        ]
        next_move = (
            f"Build the BizBuilders Roadmap around {primary_gap.lower()}—the first place the work is coming back to your team."
        )
        headings = {
            "readout": "Your business friction readout",
            "context": "What this is costing",
            "gaps": "Where work comes back",
            "moves": "Fix this first",
            "plan": "Repair order",
            "next": "Stop paying people to bridge the gap",
        }
        cta_note = "Map the first repair. Do not add more automation to the mess."
        headline = f"The work keeps coming back through {primary_gap.lower()}"
    else:
        summary = (
            f"Your answers show a {category.lower()} Digital Fog pattern. "
            f"The heaviest drag is {primary_gap.lower()}. That is why good intentions keep turning into tabs, notes, restarts, and unfinished work."
        )
        roadmap = [
            "Choose one thing worth finishing this week. Park the rest.",
            "Put everything needed for it in one place.",
            "Write the next three physical actions—not a new master plan.",
            "Silence one source of interruption until the work is done.",
        ]
        first_moves = [
            f"Clear the pressure around {primary_gap.lower()} first.",
            "Pick one unfinished thing that would create real relief.",
            "Make the next action small enough to do today.",
        ]
        next_move = "Use the Fog-Lift Kit to get one priority out of your head and moving again."
        headings = {
            "readout": "Your Digital Fog readout",
            "context": "What your answers say",
            "gaps": "Where the fog is thickest",
            "moves": "Clear this first",
            "plan": "Your next seven days",
            "next": "Do not add another tool",
        }
        cta_note = "Clear one priority. Make the next move obvious."
        headline = f"The fog gets thickest around {primary_gap.lower()}"

    return {
        "headline": headline,
        "summary": summary,
        "audience_context": audience_context(sub.industry or "", sub.diagnostic_type),
        "top_gaps": [
            {
                "dimension": dimension,
                "label": details["label"],
                "severity": details["severity"],
                "score": details["score"],
                "max_score": details["max_score"],
            }
            for dimension, details in top_gaps
        ],
        "first_moves": first_moves,
        "action_plan": roadmap,
        "next_step": next_move,
        "headings": headings,
        "cta_note": cta_note,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "flow-intake-webhook"}


@app.get("/", response_class=HTMLResponse)
def root():
    return index_page()


@app.get("/diagnostic", response_class=HTMLResponse)
def diagnostic_page(type: str = "tbtx"):
    config = get_config(type)
    question_markup = "\n".join(
        f"""
        <fieldset class="question" data-question-id="{q['id']}" data-dimension="{q['dimension']}">
          <legend>{q['label']}</legend>
          <div class="scale-labels"><span>{q['low']}</span><span>{q['high']}</span></div>
          <input aria-label="{q['label']}" type="range" min="1" max="5" value="3" />
        </fieldset>
        """
        for q in config["questions"]
    )
    return render_page(config, question_markup)


@app.get("/tbtx", response_class=HTMLResponse)
def tbtx_page():
    return diagnostic_page("tbtx")


@app.get("/bizbuilders", response_class=HTMLResponse)
def bizbuilders_page():
    return diagnostic_page("bizbuilders")


def index_page() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FLOW Diagnostics</title>
  <style>
    body { margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f6f1; color: #172033; }
    main { width: min(880px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0; }
    h1 { font-size: clamp(2.2rem, 7vw, 5rem); line-height: 1; margin: 0 0 16px; letter-spacing: 0; }
    p { color: #596271; max-width: 680px; }
    .routes { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 28px; }
    a { display: grid; gap: 8px; padding: 20px; border: 3px solid #050505; color: inherit; text-decoration: none; background: white; }
    strong { font-size: 1.15rem; }
    span { color: #596271; }
    @media (max-width: 720px) { .routes { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <h1>FLOW Diagnostics</h1>
    <p>Choose the right diagnostic surface. TransformBy10X is the B2C Digital Fog entry layer. BizBuilders AI is the B2B infrastructure and roadmap layer.</p>
    <div class="routes">
      <a href="/diagnostic?type=tbtx"><strong>TransformBy10X</strong><span>B2C Digital Fog Diagnostic</span></a>
      <a href="/diagnostic?type=bizbuilders"><strong>BizBuilders AI</strong><span>B2B Infrastructure Readiness Diagnostic</span></a>
    </div>
  </main>
</body>
</html>
"""


def render_page(config: dict, question_markup: str) -> str:
    diagnostic_type = "bizbuilders" if config["brand"] == "BizBuilders AI" else "tbtx"
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{config['title']}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg-color: #F4F4F0;
      --text-primary: #050505;
      --accent-red: #E61919;
      --surface-color: #EAE8E3;
      --grid-line: #050505;
      --muted: #4a4a44;
    }}
    * {{ box-sizing: border-box; border-radius: 0 !important; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg-color);
      color: var(--text-primary);
      line-height: 1.5;
      background-image: linear-gradient(to right, rgba(0,0,0,0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(0,0,0,0.08) 1px, transparent 1px);
      background-size: 50px 50px;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 48px;
    }}
    nav {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 12px 0 28px;
      color: var(--muted);
      font-size: 0.92rem;
      font-family: "JetBrains Mono", monospace;
      text-transform: uppercase;
      font-weight: 800;
    }}
    nav a {{ color: var(--text-primary); text-decoration: none; font-weight: 900; }}
    nav a:hover {{ color: var(--accent-red); text-decoration: underline; text-underline-offset: 4px; }}
    header {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 24px;
      align-items: end;
      margin-bottom: 22px;
      border: 4px solid var(--text-primary);
      background: var(--bg-color);
      padding: 24px;
    }}
    h1 {{
      margin: 0;
      font-family: "Archivo Black", Impact, sans-serif;
      text-transform: uppercase;
      font-size: clamp(2.25rem, 6vw, 5.4rem);
      line-height: 0.86;
      letter-spacing: -0.05em;
    }}
    .eyebrow {{
      color: var(--accent-red);
      font-weight: 900;
      text-transform: uppercase;
      font-size: 0.82rem;
      margin-bottom: 10px;
      font-family: "JetBrains Mono", monospace;
      letter-spacing: 0.08em;
    }}
    p {{ margin: 0; color: var(--muted); }}
    .brief {{
      display: grid;
      gap: 12px;
      padding-bottom: 8px;
    }}
    form, .result {{
      background: var(--bg-color);
      border: 4px solid var(--text-primary);
      padding: 0;
      box-shadow: 12px 12px 0 var(--text-primary);
      overflow: hidden;
    }}
    form::before, .result::before {{
      display: block;
      background: var(--text-primary);
      color: var(--bg-color);
      padding: 10px 14px;
      font-family: "JetBrains Mono", monospace;
      font-weight: 900;
      letter-spacing: 0.08em;
      font-size: 0.78rem;
    }}
    form::before {{ content: "{config['form_label']}"; }}
    .result::before {{ content: "{config['result_label']}"; }}
    form > * {{
      margin-left: 18px;
      margin-right: 18px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
      margin-bottom: 18px;
    }}
    label {{
      display: grid;
      gap: 6px;
      font-weight: 800;
      font-size: 0.9rem;
      font-family: "JetBrains Mono", monospace;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .span-2 {{ grid-column: span 2; }}
    input[type="text"], input[type="email"], select {{
      width: 100%;
      border: 2px solid var(--text-primary);
      padding: 11px 12px;
      font: inherit;
      background: #fff;
      color: var(--text-primary);
    }}
    .question {{
      border: 2px solid var(--text-primary);
      padding: 14px;
      margin: 0 0 10px;
      background: var(--surface-color);
    }}
    legend {{
      font-family: "Archivo Black", Impact, sans-serif;
      text-transform: uppercase;
      font-weight: 900;
      padding: 0 6px;
      letter-spacing: -0.02em;
    }}
    .scale-labels {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      color: var(--muted);
      font-size: 0.84rem;
      margin: 10px 0 4px;
      font-family: "JetBrains Mono", monospace;
      font-weight: 800;
      text-transform: uppercase;
    }}
    input[type="range"] {{ width: 100%; accent-color: var(--accent-red); }}
    button {{
      border: 0;
      background: var(--text-primary);
      color: white;
      font-family: "Archivo Black", Impact, sans-serif;
      text-transform: uppercase;
      letter-spacing: -0.02em;
      font-size: clamp(1.5rem, 4vw, 3rem);
      font-weight: 900;
      padding: 18px 16px;
      cursor: pointer;
      width: calc(100% - 36px);
      margin-bottom: 18px;
      transition: background-color 180ms ease, transform 180ms ease;
    }}
    button:hover {{ background: var(--accent-red); }}
    button:active {{ transform: translateY(2px); }}
    button:focus-visible, .result-cta:focus-visible, nav a:focus-visible {{
      outline: 4px solid var(--accent-red);
      outline-offset: 3px;
    }}
    .result {{
      margin-top: 16px;
      display: none;
    }}
    .result-hero {{
      display: grid;
      gap: 10px;
      padding: 22px 18px 6px;
      max-width: 1000px;
    }}
    .scoreline, .action-label {{
      font-family: "JetBrains Mono", monospace;
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .action-label {{ color: var(--accent-red); }}
    .scoreline {{ color: var(--muted); }}
    .result h2 {{
      margin: 0;
      font-family: "Archivo Black", Impact, sans-serif;
      text-transform: uppercase;
      font-size: clamp(2rem, 5vw, 4.1rem);
      line-height: 0.92;
      letter-spacing: -0.04em;
      text-wrap: balance;
    }}
    .result-lead {{
      max-width: 72ch;
      font-size: clamp(1rem, 1.8vw, 1.24rem);
      line-height: 1.55;
      text-wrap: pretty;
    }}
    .result-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin: 14px 18px 18px;
    }}
    .result-panel {{
      border: 2px solid var(--text-primary);
      padding: 18px;
      background: var(--surface-color);
    }}
    .result-panel h3 {{
      margin: 0 0 8px;
      font-family: "JetBrains Mono", monospace;
      text-transform: uppercase;
      font-size: 0.9rem;
      color: var(--accent-red);
    }}
    .result-action {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px 24px;
      align-items: end;
      margin: 0 18px 18px;
      padding: 22px;
      background: var(--text-primary);
      color: var(--bg-color);
    }}
    .result-action h3 {{
      margin: 0;
      max-width: 25ch;
      font-family: "Archivo Black", Impact, sans-serif;
      font-size: clamp(1.6rem, 3vw, 2.8rem);
      line-height: 0.98;
      letter-spacing: -0.035em;
      text-transform: uppercase;
      text-wrap: balance;
    }}
    .result-action .action-label {{ grid-column: 1 / -1; }}
    .result-action .action-note {{
      grid-column: 1 / -1;
      color: #b9b9b1;
      max-width: 62ch;
    }}
    .result-cta {{
      display: inline-flex;
      min-height: 52px;
      align-items: center;
      justify-content: center;
      padding: 13px 18px;
      background: var(--accent-red);
      color: white;
      font-family: "JetBrains Mono", monospace;
      font-size: 0.88rem;
      font-weight: 900;
      letter-spacing: 0.03em;
      text-decoration: none;
      text-transform: uppercase;
      transition: background-color 180ms ease, transform 180ms ease;
    }}
    .result-cta:hover {{ background: #ff3030; transform: translateY(-2px); }}
    .result-cta:active {{ transform: translateY(1px); }}
    ul {{ margin: 0; padding-left: 18px; color: var(--muted); }}
    li + li {{ margin-top: 5px; }}
    strong {{ color: var(--accent-red); }}
    .error {{
      color: var(--accent-red);
      font-weight: 800;
      min-height: 24px;
      margin-top: 10px;
      font-family: "JetBrains Mono", monospace;
      text-transform: uppercase;
    }}
    @media (max-width: 860px) {{
      header {{ grid-template-columns: 1fr; }}
      .grid {{ grid-template-columns: 1fr; }}
      .span-2 {{ grid-column: auto; }}
      .result-grid {{ grid-template-columns: 1fr; }}
      .result-action {{ grid-template-columns: 1fr; align-items: start; }}
      .result-cta {{ justify-self: start; }}
    }}
    @media (max-width: 520px) {{
      main {{ width: min(100% - 22px, 1060px); padding-top: 18px; }}
      form, .result {{ box-shadow: 7px 7px 0 var(--text-primary); }}
      nav {{ align-items: flex-start; flex-direction: column; }}
      .result-hero {{ padding-top: 18px; }}
      .result-panel, .result-action {{ padding: 15px; }}
    }}
  </style>
</head>
<body>
  <main>
    <nav>
      <span>{config['brand']} diagnostic</span>
      <span><a href="/diagnostic?type=tbtx">TBTX</a> / <a href="/diagnostic?type=bizbuilders">BizBuilders AI</a></span>
    </nav>
    <header>
      <div>
        <div class="eyebrow">{config['audience']}</div>
        <h1>{config['title']}</h1>
      </div>
      <div class="brief">
        <p>{config['intro']}</p>
      </div>
    </header>
    <form id="diagnostic-form">
      <div class="grid">
        <label>Name <input required name="name" type="text" autocomplete="name" /></label>
        <label>Email <input required name="email" type="email" autocomplete="email" /></label>
        <label>Company <input name="company" type="text" autocomplete="organization" /></label>
        <label>Role <input name="role" type="text" autocomplete="organization-title" /></label>
        <label class="span-2">Industry
          <select name="industry">
            <option value="">Choose one</option>
            <option>Creator / Personal Brand</option>
            <option>Consulting / Professional Services</option>
            <option>Agency / Marketing Services</option>
            <option>Ecommerce</option>
            <option>Health / Wellness / Aesthetics</option>
            <option>Local Business</option>
            <option>SaaS / Software</option>
            <option>Other</option>
          </select>
        </label>
      </div>
      {question_markup}
      <button type="submit">{config['submit_label']}</button>
      <div class="error" id="error"></div>
    </form>
    <section class="result" id="result" aria-live="polite"></section>
  </main>
  <script>
    const diagnosticType = "{diagnostic_type}";
    const source = "{config['source']}";
    const form = document.querySelector("#diagnostic-form");
    const result = document.querySelector("#result");
    const error = document.querySelector("#error");

    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, (character) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      }})[character]);
    }}

    function list(items) {{
      return `<ul>${{items.map((item) => `<li>${{escapeHtml(item)}}</li>`).join("")}}</ul>`;
    }}

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      error.textContent = "";
      const data = new FormData(form);
      const params = new URLSearchParams(window.location.search);
      const answers = [...document.querySelectorAll(".question")].map((node) => {{
        const input = node.querySelector("input");
        return {{
          question_id: node.dataset.questionId,
          dimension: node.dataset.dimension,
          answer_value: Number(input.value),
          answer_label: node.querySelector("legend").textContent
        }};
      }});
      const payload = {{
        name: data.get("name"),
        email: data.get("email"),
        company: data.get("company") || "",
        role: data.get("role") || "",
        industry: data.get("industry") || "",
        diagnostic_type: diagnosticType,
        source,
        utm_source: params.get("utm_source") || "",
        utm_campaign: params.get("utm_campaign") || "",
        answers
      }};
      try {{
        const response = await fetch("/diagnostic/submit", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload)
        }});
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || "Submission failed");
        const topGaps = body.report.top_gaps.map((gap) =>
          `${{gap.label}} (${{Math.round(gap.severity * 100)}}% friction)`
        );
        result.style.display = "block";
        result.innerHTML = `
          <div class="result-hero">
            <h2>${{escapeHtml(body.report.headline)}}</h2>
            <p class="scoreline">${{escapeHtml(body.category)}} · ${{body.score}} / ${{body.max_score}}</p>
            <p class="result-lead">${{escapeHtml(body.report.summary)}}</p>
          </div>
          <div class="result-grid">
            <article class="result-panel">
              <h3>${{escapeHtml(body.report.headings.context)}}</h3>
              <p>${{escapeHtml(body.report.audience_context)}}</p>
            </article>
            <article class="result-panel">
              <h3>${{escapeHtml(body.report.headings.gaps)}}</h3>
              ${{list(topGaps)}}
            </article>
            <article class="result-panel">
              <h3>${{escapeHtml(body.report.headings.moves)}}</h3>
              ${{list(body.report.first_moves)}}
            </article>
            <article class="result-panel">
              <h3>${{escapeHtml(body.report.headings.plan)}}</h3>
              ${{list(body.report.action_plan)}}
            </article>
          </div>
          <section class="result-action">
            <p class="action-label">${{escapeHtml(body.report.headings.next)}}</p>
            <h3>${{escapeHtml(body.report.next_step)}}</h3>
            <a class="result-cta" href="${{escapeHtml(body.route_to)}}">${{escapeHtml(body.next_cta)}}</a>
            <p class="action-note">${{escapeHtml(body.report.cta_note)}}</p>
          </section>
        `;
        result.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }} catch (err) {{
        error.textContent = err.message;
      }}
    }});
  </script>
</body>
</html>
"""


@app.post("/intake")
def intake(sub: Sub):
    task_id = "INTAKE-" + uuid.uuid4().hex[:12]
    gap_count = sum(1 for v in (sub.gaps or {}).values() if v > 0)
    labels = ["Stable system", "Targeted resource", "Infrastructure conversation", "Full engagement"]
    routing = sub.routing or labels[min(gap_count, 3)]
    envelope = {
        "task_id": task_id,
        "name": sub.name,
        "email": sub.email,
        "company": sub.company,
        "gaps": sub.gaps,
        "total_gaps": gap_count,
        "routing": routing,
        "friction": sub.friction,
        "stalling": sub.stalling,
        "answers": sub.answers,
        "source": sub.source,
        "created": datetime.datetime.utcnow().isoformat(),
    }
    (INTAKE_DIR / f"{task_id}.json").write_text(json.dumps(envelope, indent=2))
    print("Intake received:", task_id, routing, flush=True)
    return {
        "status": "received",
        "task_id": task_id,
        "routing": routing,
        "message": "Baseline recorded. Observations within one business day.",
    }


@app.post("/diagnostic/submit")
def diagnostic_submit(sub: DiagnosticSub):
    config = get_config(sub.diagnostic_type)
    session_id = "DIAG-" + uuid.uuid4().hex[:12]
    score = sum(answer.answer_value for answer in sub.answers)
    max_score = len(sub.answers) * 5
    category = category_for(score, max_score)
    dimension_scores = score_dimensions(sub.answers, sub.diagnostic_type)
    report = build_report(sub, category, dimension_scores)
    record = {
        "session_id": session_id,
        "lead": {
            "name": sub.name,
            "email": sub.email,
            "company": sub.company,
            "role": sub.role,
            "industry": sub.industry,
            "source": sub.source,
        },
        "diagnostic_type": sub.diagnostic_type,
        "score": score,
        "max_score": max_score,
        "category": category,
        "dimension_scores": dimension_scores,
        "report": report,
        "next_cta": config["cta"],
        "route_to": config["route_to"],
        "utm_source": sub.utm_source,
        "utm_campaign": sub.utm_campaign,
        "answers": [answer.model_dump() for answer in sub.answers],
        "created": datetime.datetime.utcnow().isoformat(),
    }
    (INTAKE_DIR / f"{session_id}.json").write_text(json.dumps(record, indent=2))
    print("Diagnostic received:", session_id, sub.diagnostic_type, category, score, flush=True)
    return {
        "status": "received",
        "session_id": session_id,
        "score": score,
        "max_score": max_score,
        "category": category,
        "dimension_scores": dimension_scores,
        "report": report,
        "next_cta": config["cta"],
        "route_to": config["route_to"],
    }


@app.get("/intake/submissions")
def submissions(api_key: str = ""):
    if api_key != os.environ.get("WEBHOOK_API_KEY", ""):
        return {"error": "unauthorized"}
    files = sorted(INTAKE_DIR.glob("*.json"), reverse=True)
    return [json.loads(f.read_text()) for f in files[:20]]
