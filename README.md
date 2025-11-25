# AI Debt Analyzer
**A Technical Debt Analysis System Designed for AI‑Generated Code**

AI accelerates development — but it also accelerates the creation of **structural technical debt**.  
AI‑generated code frequently introduces duplicated logic, unnecessary abstractions, hallucinated APIs, and fragile error‑handling that silently accumulates over time.

**AI Debt Analyzer** is a full‑stack static analysis + temporal intelligence system designed for modern engineering teams using AI‑assisted coding.

It answers questions such as:

- Which modules are turning into **AI‑generated code dumps**?
- How much structural debt did AI introduce over time?
- Which PRs are risky?
- Which files should be prioritized for refactoring?
- How is AI code affecting long‑term maintainability?

---

## ✨ Key Features

### 🔥 1. Module‑Level AI Debt Heatmap
Aggregates code at the first two directory levels and computes a normalized **AI Debt Score**.

Identifies:

- High‑risk modules  
- AI‑generated hotspots  
- Areas requiring immediate refactoring  

Click on any module to reveal its **Top 10 highest‑debt files**.

---

### 🔍 2. File‑Level Drill‑Down (Top 10 Risk Files)

Each file includes:

- Line count  
- AI Influence Score  
- AI Debt Score  
- Full breakdown of **five AI Code Smells**:
  - Duplicate Logic
  - API Hallucinations
  - Over‑Engineering Wrappers
  - Unnecessary Abstractions
  - Silent Failure Patterns

Includes human‑readable explanations and visual risk tags, such as:

- 🔥 *AI Dump Candidate*  
- ⚠️ *Needs Attention*  

---

### ⏳ 3. Historical AI Debt Trend (Two Modes)

The system provides **two switchable time‑series charts**:

#### **A. Cumulative AI Debt Over Time**
Built using the **end‑of‑month snapshot algorithm**:
1. Identify the last commit of each month  
2. Perform a full static analysis  
3. Plot the cumulative debt score  

Shows:
- When AI debt spiked  
- Effects of rewrites / migrations  
- Long‑term stability vs deterioration  

#### **B. Monthly New AI Debt (Non‑Cumulative)**
Shows debt *introduced* in each month.  
Reveals patterns such as:
- AI‑heavy feature bursts  
- Stable vs risky development periods  

---

### 🧩 4. PR Risk Index + Semantic Drift

For each PR / merge commit, the system computes:

- Files touched  
- Lines added  
- AI Debt Delta  
- Semantic Drift Score  
- A normalized **0–1 AI Risk Index**

Useful for identifying:

- High‑risk PRs  
- Contributors introducing AI‑heavy unstable code  
- “Silent refactoring bombs” that degrade structure  

---

## ⚙️ Technical Architecture

### 1. Static Analysis Engine
AST‑based structural feature extraction:

- Cyclomatic & structural complexity  
- Block‑level shingle duplication detection  
- Wrapper/abstraction misuse  
- API hallucination heuristics  
- Silent failure pattern detection  

### 2. Five AI Code Smells
- **Duplicate Blocks**  
- **API Hallucinations**  
- **Over‑Engineering Wrappers**  
- **Unnecessary Abstractions**  
- **Silent Failures**  

### 3. Core Metrics
- **AI Influence Score** — likelihood of AI‑generated origin  
- **AI Debt Score** — normalized debt index (0–1)  

---

## 📊 Outputs

After scanning, the system generates:

```
ai_debt_reports/
│   files.csv               # Per‑file AI metrics
│   timeline.csv            # Cumulative monthly AI debt
│   timeline_monthly.csv    # Monthly new AI debt (non‑cumulative)
│   prs.csv                 # PR‑level risk & drift
│   report.html             # Full interactive dashboard
```

Open **report.html** to explore the visual analytics dashboard.

---

## 🚀 Installation & Usage

### Install
```bash
pip install ai_debt
```

### Run
```bash
python -m ai_debt.cli --repo /path/to/repo --since 2015-01-01
```

Then open:
```
ai_debt_reports/report.html
```

---

## 🛠️ Intended Users

- Backend engineering teams  
- Platform & infrastructure groups  
- AI‑product engineering orgs  
- Data engineering teams  
- CTOs & tech leads managing AI‑assisted development  

---

## 📘 Why This Matters

AI code generation is fast.  
But **uncontrolled AI code generation is one of the fastest ways to accumulate structural technical debt**.

AI Debt Analyzer gives engineering leaders visibility into:

- Where AI code is creeping in  
- How it’s shaping the codebase  
- Where refactoring budgets should be spent  
- How PRs impact long‑term maintainability  

This creates a feedback loop for **responsible, observable, and sustainable use of AI coding tools**.

---
