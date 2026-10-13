---
name: phase-updater
description: >-
  Updates each phase in `study_docs/phase-n.md` and `study_docs/README.md` when changes are made.
  Tracks what the changes did, what files changed, their use and location, and comprehensive
  architectural and pedagogical explanations, making study docs dynamic and continuously synced.
---

# Phase Updater Skill (`study_docs/`)

This skill governs the continuous, dynamic synchronization of AEGIS's study documentation in `study_docs/`. Every file creation, modification, refactoring, or test execution MUST be recorded in the corresponding phase document.

---

## 📌 Non-Negotiable Core Protocol: Live Phase Sync

Whenever any change is made to the codebase (contracts, domain, detection, graph, RAG, agents, audit, api, worker, tests, or config):

### 1. Identify Target Phase(s)
Map the changed files to the appropriate phase document:
- **Phase 0 (`study_docs/phase-0.md`)**: Core contracts, DB schema, async event outbox, FastAPI skeleton, audit hash chain, synthetic data engine.
- **Phase 1 (`study_docs/phase-1.md`)**: Deterministic rules engine, case state machine, customer/account views, NetworkX graph projection.
- **Phase 2 (`study_docs/phase-2.md`)**: Point-in-time leak-free feature extraction, scikit-learn/XGBoost calibrated scoring, SHAP reason codes, temporal graph motif detector, entity resolution.
- **Phase 3 (`study_docs/phase-3.md`)**: Qdrant hybrid vector index, policy corpus ingestion, LangGraph investigation workflow, claim verifier, risk challenger, human review gate.
- **Phase 4 (`study_docs/phase-4.md`)**: Multi-tenant isolation tests, prompt injection resilience, temporal leakage regression suite, agent eval harness, drift monitoring.
- **Phase 5 (`study_docs/phase-5.md`)**: Flagship "Project Sandglass" demo scenario, visual audit timeline, presentation runbooks, ADRs.

---

### 2. Update the Target Phase File Registry
In `study_docs/phase-n.md` under `## 📂 Component & File Registry`, ensure every new or modified file is registered:

| File Path | Boundary / Package | Purpose & Responsibility | Key Exported Symbols |
|---|---|---|---|
| `[packages/contracts/transaction.py](file:///c:/Users/saswa/Desktop/Aegis/packages/contracts/transaction.py)` | `packages/contracts` | Strict Pydantic v2 validation for incoming transaction payloads | `TransactionIn`, `DirectionEnum` |

Rules for File Registry:
- **Always use clickable markdown links** formatted with forward slashes: `[path/to/file.py](file:///c:/Users/saswa/Desktop/Aegis/path/to/file.py)`.
- Specify the exact architectural boundary.
- Clearly state the purpose and why this file exists in the system.
- List exported classes, functions, or schemas.

---

### 3. Log the Dynamic Chronological Deep-Dive Entry
Under `## 📝 Dynamic Change Chronology & Deep Dive` in `study_docs/phase-n.md`, prepend/append a new entry with the following strict structure:

```markdown
### 🔄 Update [YYYY-MM-DD] — <Concise Title of Change>
- **Status Transition**: `⚪ Planned` -> `🟡 In Progress` (or `🟡 In Progress` -> `🟢 Completed`)
- **Files Modified / Added**:
  - `[path/to/file.py](file:///c:/Users/saswa/Desktop/Aegis/path/to/file.py)`: <Location & primary function>
- **What Changed**: <Precise summary of code changes, function additions, schema updates>
- **Technical Deep-Dive & Pedagogical Rationale**:
  - <Why this change was designed this way>
  - <How the data flow or algorithmic execution works>
  - <Ponytail rationale: stdlib/native choices, minimal diff justification>
- **Impact on Upstream/Downstream Subsystems**: <How this change affects other phases/modules>
```

---

### 4. Update Checklist & Phase Status
1. Check off completed items in `## 🎯 Implementation Checklist` (`- [ ]` -> `- [x]`).
2. Update the Phase Status badge at the top of the file:
   - `⚪ Planned`: Not yet implemented.
   - `🟡 In Progress`: Currently being developed/tested.
   - `🟢 Completed`: Fully implemented, verified with runnable tests.
   - `🔴 Blocked`: Blocked on prerequisite components.
3. Update `Last Updated:` timestamp to current local time.

---

### 5. Sync the Master Index (`study_docs/README.md`)
Whenever a phase status transitions (e.g. from `⚪ Planned` to `🟡 In Progress` or `🟢 Completed`), update the status badge and summary row in [`study_docs/README.md`](file:///c:/Users/saswa/Desktop/Aegis/study_docs/README.md).

---

### 6. Verification & Runnable Proof
In `## 🧪 Verification & Runnable Proof` of `phase-n.md`, document the exact runnable command and output demonstrating the component works:
```bash
pytest tests/unit/test_transaction_contracts.py -v
```
**Strict "No Dummy / No Static Mocks" Doctrine**: Never record mocked fake returns as verification proof. All proof must come from executing live, algorithmic Python code.
