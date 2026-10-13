# AEGIS — Project Directives & Behavioral Guidelines

These rules apply strictly and unconditionally across all files, tools, and actions in this repository.

---

## 1. Strictly Adhere to the Ponytail Protocol

Every line of code and every interaction must climb the **Minimality Ladder**:
1. **YAGNI (You Ain't Gonna Need It)**: Do not build speculative features or premature abstractions.
2. **Reuse Existing Code**: Search first (`grep`, `view_file`) before writing duplicate helpers.
3. **Standard Library First**: Prefer Python standard library (`pathlib`, `itertools`, `hashlib`, `asyncio`, `dataclasses`) over third-party utilities.
4. **Native Language & Platform Features**: Use native constructs (FastAPI dependency injection, Pydantic v2 validators, async context managers).
5. **Existing Dependencies**: Never install a new package if an installed dependency (`fastapi`, `pydantic`, `sqlalchemy`, `networkx`, `scikit-learn`, `qdrant-client`) can solve it.
6. **One-Liner / Concise Construct**: Avoid creating 5-layer helper abstractions for simple operations.
7. **Minimum Viable Implementation**: Write the cleanest, most concise implementation that satisfies the explicit requirements.

### Non-Negotiable Boundaries:
- Validate all untrusted inputs with Pydantic v2.
- Prevent data loss and concurrency hazards (compare-and-swap state transitions).
- Hash-chained non-repudiation for audit trails.
- Keep responses and diffs direct, concise, and fluff-free.

---

## 2. Strict "No Dummy / No Static Mocks" Doctrine

- **Zero Hardcoded Fakes**: No static JSON fixtures substituting for business logic, no mock rule outputs, no fake graph queries.
- **Algorithmic Realism**: Real mathematical graph algorithms (temporal shortest paths, degree distributions, motif discovery via NetworkX), real scikit-learn/XGBoost pipelines, real Qdrant hybrid vector embeddings/search, real FastAPI endpoints.
- **Dynamic Synthetic Generator**: Synthetic data generators must algorithmically generate realistic transactions, genuine graph topologies, and mathematically verifiable typologies.

---

## 3. Mandatory Phase Updater Protocol (`study_docs/`)

Whenever any code file, schema, route, test, or model is created or updated:
1. **Identify the affected phase** (Phase 0 through Phase 5).
2. **Update `study_docs/phase-n.md`**:
   - Register new/modified files in the **Component & File Registry** (with clickable `file:///` links, boundary, purpose, and exported symbols).
   - Append a **Dynamic Change Chronology & Deep Dive** entry (timestamp, files changed, technical rationale, data flow impact, pedagogical explanation).
   - Update the **Implementation Checklist** (`- [ ]` -> `- [x]`).
   - Update the **Status Badge** (`⚪ Planned`, `🟡 In Progress`, `🟢 Completed`, `🔴 Blocked`) and `Last Updated` timestamp.
3. **Sync `study_docs/README.md`**: Keep status badges and phase summaries in the master index synchronized with code reality.
4. **Runnable Proof**: Document exact runnable commands and test outputs.
