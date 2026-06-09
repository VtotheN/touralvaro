# Comparativa rápida — Swarms de Agentes

## TL;DR

| Si quieres... | Usa |
|---|---|
| Máxima eficiencia de tokens con Claude | **Dynamic Workflows + Subagents nativos (Claude Agent SDK)** |
| Lo que ya tienes con federación + memoria | **ruflo v3.6** |
| Grafos complejos multi-paso | **LangGraph** |
| Prototipo rápido por roles | **CrewAI** |
| Paralelismo masivo (100+ agentes) | **Ray** |
| Conversaciones multi-turno + código | **AG2** |
| Stack OpenAI | **OpenAI Agents SDK** |

## Decisión rápida

```
¿Trabajas con Claude?
├── SÍ → ¿Necesitas federación / memoria persistente / RAG?
│         ├── SÍ → ruflo
│         └── NO → Dynamic Workflows + Subagents (más barato)
└── NO → ¿Stack OpenAI?
          ├── SÍ → OpenAI Agents SDK
          └── NO → LangGraph (más flexible)
```

## Costo real de ruflo

- Overhead: 15k–25k tokens por sesión solo en arranque
- Ahorro del 75% solo aplica si la mayor parte del trabajo lo hace el WASM Agent Booster (tareas simples)
- Para tareas de razonamiento puro, el overhead puede costar más que el ahorro
