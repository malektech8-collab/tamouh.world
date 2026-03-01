Career Classification Engine – AI Resume SaaS
🎯 Objective

Automatically classify a resume into:

Junior

Senior

Executive

While ensuring:

User can override classification in UI

Classification confidence is logged

Optimization logic adapts based on career level

System remains deterministic and auditable

🧠 Step 1 — Define Classification Rules (Deterministic First)

Before using any LLM reasoning, define measurable, objective signals.

This ensures:

Transparency

Predictability

Cost efficiency

Reduced hallucination risk

Primary Signals
1️⃣ Years of Experience

Calculate from:

Earliest job start date

Latest job end date

Rules
0–3 years → Junior
4–10 years → Senior
10+ years → Candidate for Executive evaluation

⚠ Important: Years alone are insufficient for executive classification.

2️⃣ Leadership Indicators

Scan titles and bullet content for:

“Manager”

“Head of”

“Director”

“VP”

“Chief”

“Led team of”

“Managed budget”

“P&L”

“Oversaw”

“Reported to board”

Each detected indicator increases leadership score.

3️⃣ Metrics Depth

Executives and seniors demonstrate measurable impact.

Detect:

Percentage values (%)

Currency ($, €, SAR)

Revenue impact

Cost savings

Team sizes

Performance improvements

Count quantified bullets and calculate density ratio.

Example:

metrics_ratio = quantified_bullets / total_bullets
🧮 Step 2 — Hybrid Scoring Engine

Combine signals into weighted score.

Example implementation:

def classify_career_level(resume: ResumeDoc):

    score = 0

    years = calculate_years(resume.experience)

    if years <= 3:
        score += 1
    elif 4 <= years <= 10:
        score += 2
    else:
        score += 3

    leadership_signals = detect_leadership(resume)
    score += leadership_signals

    metrics_density = count_metrics(resume)
    score += metrics_density

    if score <= 3:
        return "junior", 0.85
    elif score <= 6:
        return "senior", 0.80
    else:
        return "executive", 0.75
Return Values

classification

confidence_score

Confidence reflects rule-based reliability.

🧠 Step 3 — Optional LLM Validation Layer

After rule-based classification, optionally validate with GPT.

Prompt
Given:
- Years of experience: X
- Leadership indicators: Y
- Roles held: [...]
Classify as junior, senior, or executive.
Return only one word.
Handling Disagreement

If LLM disagrees:

Log mismatch

Keep rule engine result

Improve rules later

⚠ Never blindly trust LLM over deterministic logic.

🔥 Step 4 — Extend ResumeMeta Model

Add structured intelligence storage.

class ResumeMeta(BaseModel):
    career_level: Literal["junior", "senior", "executive"]
    auto_detected: bool
    confidence: float
    user_override: Optional[str]
Override Logic

If user overrides:

auto_detected = False

Preserve original classification

Use override for rendering + optimization

Store both values for analytics

🎨 Step 5 — UI Flow

Frontend behavior:

Resume uploaded

System auto-classifies

Display result:

Detected Career Level: Senior (80% confidence)

Change? [Junior] [Senior] [Executive]

Why this matters:

Builds trust

Gives psychological control

Increases conversion rate

🏗 Step 6 — Career-Aware Optimization Logic

Optimization behavior changes based on classification.

Junior Optimization

Expand skills section

Promote projects before experience (if weak experience)

Highlight internships

Keep summary concise (2 lines)

Avoid exaggerated claims

Senior Optimization

Enforce quantified bullets

Add competency block

Strengthen impact language

Improve keyword density

Executive Optimization

Compress early career

Add leadership profile

Emphasize financial impact

Highlight transformation initiatives

Add strategic narrative tone

This is structural content adaptation — not cosmetic styling.

📁 Backend Flow After Implementation
Upload Resume
        ↓
Extract Text
        ↓
Parse to ResumeDoc
        ↓
Career Classification Engine
        ↓
Audit
        ↓
Optimization (career-aware)
        ↓
Template Rendering

Classification happens before optimization.

🚨 Quality Safeguards

Add validation rules per level.

Executive Rules

Must include leadership signals

Must include quantified metrics

Summary ≥ 4 lines

Leadership achievements section required

Senior Rules

Each role must contain measurable impact

Competency block required

Summary must include years of experience

Junior Rules

Skills section required

Projects allowed before experience

Minimum 5 skills listed

Failure Handling

If validation fails:

Auto-adjust content

Re-run optimizer

Re-check rules

Never render invalid structure.

🔥 Strategic Advantage

Most resume SaaS tools:

Only change visual design

Do not change structure

Do not adapt content logic

Do not understand career stage

You are building:

Career-stage aware AI resume engine

This creates:

Higher perceived intelligence

Better recruiter alignment

Real differentiation

Enterprise-grade positioning

Architectural Principle

Structure > Formatting
Deterministic Logic > Blind AI
Career Intelligence > Static Templates

End of Document.