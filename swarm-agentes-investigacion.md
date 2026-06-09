# Investigación: Swarms de Agentes — ¿hay algo mejor que ruflo?

Fecha: 2026-06-08

## Sobre "ruflo" (lo que usas actualmente)

`ruflo` = el nuevo nombre de **claude-flow** de ruvnet (github.com/ruvnet/ruflo).
Versión actual: **v3.6 (abril 2026)**.

**Lo que ofrece:**
- 60+ agentes especializados (coding, review, testing, security, etc.)
- Federación entre máquinas
- Memoria persistente entre sesiones (vector search HNSW, knowledge graphs)
- Swarm self-learning
- Agent Booster WASM para tareas simples
- Promete ~75% reducción de costos de API

**La letra chica:**
Una auditoría de abril 2026 encontró que ruflo **añade 15.000–25.000 tokens de overhead por sesión** solo en arranque/coordinación. El ahorro del 75% asume cargas donde el WASM puede hacer tareas simples sin LLM — si tu trabajo es mayormente razonamiento, no ahorra tanto.

---

## Comparativa de alternativas

| Framework | Fortaleza | Cuándo gana a ruflo |
|---|---|---|
| **Claude Agent SDK + Dynamic Workflows** (nativo Anthropic, 2026) | El runtime ejecuta JavaScript que coordina subagentes con **0 tokens de modelo** para la orquestación | ⭐ El más eficiente en tokens si trabajas con Claude — sin overhead de framework |
| **Subagents nativos de Claude Code** | YAML en `.claude/agents/`, corren dentro de la sesión padre | Lo más token-efficient para workflows repetibles |
| **LangGraph** | Grafos con checkpointing y time-travel | Si tu flujo es DAG complejo con ramas/loops |
| **CrewAI** | Roles declarativos, 30–60% más rápido que AutoGen | Prototipo rápido multi-agente |
| **AG2** (sucesor de AutoGen) | Event-driven, async messaging | Conversaciones multi-turno con ejecución de código |
| **OpenAI Agents SDK** (sucesor de Swarm experimental) | Sandbox + harness producción | Si usas modelos OpenAI |
| **Ray** | Paralelismo masivo, actores distribuidos | 100+ agentes en múltiples máquinas (Uber lo usa) |

---

## Recomendación

Si tu objetivo es **paralelismo + ahorro de recursos**, la opción que más probablemente le gane a ruflo es la **nativa de Anthropic**:

1. **Dynamic Workflows + Subagents del Claude Agent SDK**
   - El coordinador es JavaScript, no LLM
   - Ruflo te cobra tokens en su capa de orquestación; los Dynamic Workflows no
   - Para muchos agentes en paralelo esto importa mucho

2. **Conserva ruflo solo si necesitas sus features únicas:**
   - Federación entre máquinas
   - Memoria/RAG persistente entre sesiones
   - Swarm self-learning
   - Si no las usas, estás pagando overhead de tokens sin recibir el beneficio

---

## Innovación clave de Dynamic Workflows (2026)

> "The JavaScript that coordinated agents spent zero model tokens. That distinction matters: the model did the judgment, the code did the coordination."

Las 3 capacidades de agentes de Anthropic en 2026:

1. **Agent View** — Dashboard de control. Ejecutas `claude agents` y ves cada sesión en background: qué está trabajando, qué necesita input, qué terminó.
2. **Subagents** — Workflows repetibles. YAML con modelo bloqueado y system prompt.
3. **Dynamic Workflows** — JS script que orquesta subagentes a escala. Claude escribe el script para la tarea, el runtime lo ejecuta en background.

---

## Fuentes

- [GitHub - ruvnet/ruflo](https://github.com/ruvnet/ruflo)
- [Claude Flow V3 — 15-Agent Concurrent Swarm (issue #927)](https://github.com/ruvnet/ruflo/issues/927)
- [RuFlow: 75% API cost reduction claims (DEV)](https://dev.to/arshkharbanda2010/ruflow-ruflo-the-multi-agent-claude-ai-orchestrator-that-slashes-api-costs-by-75-2nmc)
- [Ruflo v3.6 tutorial — AI Agents First](https://aiagentsfirst.com/ruflo-v3-claude-code-multi-agent-swarm)
- [Claude Code Agents in 2026 — CloudZero](https://www.cloudzero.com/blog/claude-code-agents/)
- [Orchestrate subagents — Claude Code Docs](https://code.claude.com/docs/en/workflows)
- [Claude Code Dynamic Workflows — InfoQ](https://www.infoq.com/news/2026/06/dynamic-workflows-claude-code/)
- [2026 Agent Framework Showdown — QubitTool](https://qubittool.com/blog/ai-agent-framework-comparison-2026)
- [Best Multi-Agent Frameworks 2026 — Gurusup](https://gurusup.com/blog/best-multi-agent-frameworks-2026)
- [Top 5 Open-Source Agentic AI Frameworks 2026 — AIMultiple](https://aimultiple.com/agentic-frameworks)
