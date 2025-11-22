# AI Debt Analyzer  
**A Technical Debt Analysis System Designed for AI-Generated Code**

AI accelerates development — but also accelerates the creation of **structural technical debt**.  
AI-generated code often contains duplicated logic, unnecessary abstractions, hallucinated APIs, and fragile error handling that compound over time.

**AI Debt Analyzer** is built specifically for engineering teams operating in the AI era.  
It answers critical questions such as:

- Which modules are becoming **“AI code dumps”** over time?  
- How much technical debt did AI-generated code introduce?  
- Which PRs are structurally risky?  
- Which files should be refactoring priorities?

Designed for backend teams, AI engineering organizations, data engineering teams, and any company scaling AI-assisted coding.

---

## ✨ Features

### 🔥 1. AI Tech Debt Heatmap (Module-Level)

Automatically aggregates the first two directory levels and computes the **AI Debt Score** for each module.

Helps identify:

- High-risk modules  
- Hotspots caused by AI code generation  
- Areas requiring immediate refactoring  

Clicking on any module reveals the **Top 10 most risky files**.

---

### 🔍 2. File-Level Drill-Down (Top 10 Risk Files)

For each module, the system displays:

- The 10 files with the highest AI Debt Score  
- Full breakdown of **five AI Code Smells**  
- Human-readable explanations  
  - “AI-generated wrapper explosion”  
  - “silent exception swallowing”  
  - “hallucinated API patterns”, etc.  
- Visual risk tags  
  - 🔥 *AI Dump Candidate*  
  - ⚠️ *Needs Attention*

---

### ⏳ 3. Historical AI Debt Trend (Monthly Snapshots)

We use an innovative **end-of-month snapshot algorithm**:

1. Identify the last commit of each month  
2. Perform a full static analysis on that snapshot  
3. Plot AI Debt evolution over time  

This reveals:

- When AI debt started accumulating  
- Effects of migrations, rewrites, major features  
- Whether the codebase is stabilizing or degrading  

---

### 🧩 4. PR Risk Index

For each merge commit / PR, we compute:

- Files touched  
- Lines added  
- Existing debt in each modified file  
- A normalized **0–1 risk index**

Helps engineering leads pinpoint:

- Risky contributors  
- PRs likely to introduce structural decay  
- High-impact debt events  

---

## ⚙️ Technical Architecture (Summary)

### 1. Whole-Repository Static Analysis  
AST-based feature extraction:

- Structural complexity  
- Repeated logic (shingle-based duplication detection)  
- Wrapper overuse  
- Invalid/misused APIs (hallucinations)  
- Silent failure patterns  

### 2. Five AI Code Smells

- **Duplicate Blocks**  
- **API Hallucinations**  
- **Over-engineering Wrappers**  
- **Unnecessary Abstractions**  
- **Silent Failures**

### 3. Two Core Scores

- **AI Influence Score** — likelihood of AI origin  
- **AI Debt Score** — normalized structural risk (0–1)  

---

## 🚀 Install & Run

```bash
pip install ai_debt
python -m ai_debt.cli --repo /path/to/repo --since 2015-01-01

Outputs to:
ai_debt_reports/
    files.csv
    timeline.csv
    prs.csv
    report.html

Open **report.html** to view the dashboard.