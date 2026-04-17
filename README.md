# ⬡ FORGE

**AI-Powered Full-Stack Product Scaffold Engine**

> End-to-End GenAI System: Idea → Structured Code → CI/CD → Iterative Repair

![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-2563EB?style=flat-square)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203%2070B-orange?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?style=flat-square)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-2088FF?style=flat-square)

---

## What is FORGE?

FORGE is an experimental GenAI system that converts a natural language idea into a structured project scaffold and iteratively improves it using CI/CD feedback.

It is designed as a **closed-loop multi-agent system** where each stage feeds into the next — combining LLM orchestration, system design, and automated debugging workflows.

Rather than focusing purely on code generation, FORGE explores:

* how far LLMs can go in **end-to-end software creation**
* how CI signals can be used for **automated repair loops**
* where current systems **fail to generalize beyond templates**

---

## Core Capabilities

* Idea → structured project scaffold (~10–12 files)
* Multi-agent orchestration using LangGraph
* Automated GitHub repo creation via API
* CI/CD integration with GitHub Actions
* LLM-driven autofix loop based on lint/test failures
* Stack-aware generation (Python/FastAPI, Node.js, etc.)

---

## Architecture

```
User Input
    │
    ▼
Idea Validator ──▶ PRD Generator ──▶ Code Scaffolder
    │                                      │
    ▼                                      ▼
 Auto-Fixer ◀── CI Monitor ◀── GitHub Push
```

Each stage is handled by a specialized agent coordinated through a shared state graph.

---

## Pipeline Overview

1. **Idea Input**

   * User provides idea, target audience, optional stack

2. **Idea Validation**

   * LLM evaluates feasibility, risk, and suggests stack

3. **PRD Generation**

   * Structured product requirements generated

4. **Code Scaffold**

   * Multi-file project generated (routes, services, tests)

5. **GitHub Push**

   * Repository created and populated via API

6. **CI/CD Execution**

   * GitHub Actions runs linting and tests

7. **Failure Analysis**

   * LLM parses CI logs (ruff, pytest)

8. **Autofix Loop**

   * Patch suggestions generated and applied iteratively

---

## Tech Stack

**Backend & AI**
FastAPI · LangGraph · Groq API · LLaMA 3 70B · LangChain Core · Pydantic · httpx

**CI/CD & DevOps**
GitHub Actions · GitHub REST API · ruff · pytest

**Frontend & Infra**
Vanilla JS · SSE · Docker Compose · uvicorn

---

## Performance (Observed)

| Metric             | Value                    |
| ------------------ | ------------------------ |
| Idea → GitHub push | ~45 seconds              |
| LLM latency (Groq) | 630–970 ms               |
| Autofix success    | ~70% (lint-level issues) |
| CI convergence     | 1–2 iterations           |
| Files generated    | ~10–12                   |

---

## System Design Highlights

### Multi-Agent Orchestration

* Implemented via LangGraph StateGraph
* Shared state passed across agents
* Conditional routing (e.g., skip pipeline on low feasibility)

### Prompt Engineering

* Centralized prompt layer (`core/prompts.py`)
* JSON-constrained outputs for reliability
* Stack-aware code generation

### Autofix Loop

* CI logs parsed via GitHub API
* LLM generates patch operations
* Patches applied via GitHub Contents API
* Iterative loop until CI passes or limit reached

---

## Limitations (Important)

* Generated code is **scaffold-level**, not production-ready
* Autofix primarily handles **lint/syntax issues**, not deep logic bugs
* Patch strategy may remove problematic lines instead of fully repairing logic
* System prioritizes pipeline completion over code depth in current version

---

## Why this project

FORGE is less about building a perfect code generator and more about exploring a key question:

> *Can LLMs participate in full software engineering loops — not just generation, but debugging and iteration?*

Through this system, I observed that while LLMs are effective at structured generation and shallow fixes, they struggle with:

* semantic correctness
* dependency reasoning
* non-local bug resolution

This project reflects my interest in building systems that expose these limitations and push toward more reliable autonomous software workflows.

---

## Future Work

* Structured error classification before patching
* Semantic-aware repair instead of line deletion
* Improved grounding for generated code
* Minimal viable project mode (reduce over-generation)
* Better test generation aligned with code behavior

---

## Quick Start

```bash
git clone https://github.com/your-username/forge
cd forge
pip install -r requirements-prod.txt
cp .env.example .env
python server.py
```

---

## Final Note

FORGE is an **experimental system**, not a production tool.
Its goal is to explore the boundary between LLM-assisted coding and autonomous software engineering.

---

*FORGE v1.0 — LangGraph · Groq · FastAPI · GitHub Actions*
