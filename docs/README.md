# docs/ — index

| File | Purpose | Update when |
|---|---|---|
| `STATE.md` | What is shipped, how it was verified, open items | every release |
| `DECISIONS.md` | Dated product (`D-`) and engineering (`E-`) decisions with reason and location | any non-trivial choice |
| `ARCHITECTURE.md` | System context, pipeline stages, developer gate, data, security posture | structure changes |
| `DEPLOYMENT.md` | Pre-flight checklist, Docker, env vars that matter, first-boot steps, rollback | ops changes |
| `API.md` | REST contract, examples, determinism header, receipt, guard | endpoint changes |
| `INTEGRATIONS.md` | MCP design and shipped status, ecosystem survey | MCP changes |
| `GUARD.md` | Guard verdict semantics and fixed summaries | guard changes |
| `ENGLISH_GATE.md` | Translations layer, retrieval metrics, picker results | english gate changes |
| `MODELS.md` | Measured model benchmark behind `/settings` | re-benchmark |
| `RISKS.md` | Product risk register; every mitigation names its test | new risk / mitigation |
| `GLOSSARY.md` | AR/EN project vocabulary | new term |
| `adr/` | Architecture decision records (stack, matching, states, storage, providers) | architecture-level decision |
| `manual-test/` | Live-verified manual test images and expected outcomes | UI behaviour changes |
| `examples/` | Client snippets (`guard_client.py`) | API changes |
