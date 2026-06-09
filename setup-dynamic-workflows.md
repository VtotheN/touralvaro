# Setup mínimo — Dynamic Workflows + Subagents (alternativa a ruflo)

## 1. Crear un subagent

Archivo: `.claude/agents/code-reviewer.yaml`

```yaml
name: code-reviewer
description: Reviews code for bugs, style, and security issues
model: claude-sonnet-4-6
tools:
  - Read
  - Grep
  - Bash
system_prompt: |
  You are a senior code reviewer. Focus on:
  - Logic bugs and edge cases
  - Security vulnerabilities (OWASP top 10)
  - Performance issues
  Be terse. Report only actionable findings.
```

## 2. Crear otro subagent en paralelo

Archivo: `.claude/agents/test-writer.yaml`

```yaml
name: test-writer
description: Writes unit tests for changed code
model: claude-haiku-4-5-20251001
tools:
  - Read
  - Write
  - Bash
system_prompt: |
  You write focused unit tests covering the changed code.
  Use the project's existing test framework.
  No integration tests unless asked.
```

## 3. Dynamic Workflow que los orquesta en paralelo

Archivo: `workflows/review-and-test.js`

```javascript
// Este JS NO consume tokens del modelo — solo coordina
export default async function workflow({ runAgent, args }) {
  const { branch } = args;

  // Lanzar dos agentes en paralelo
  const [review, tests] = await Promise.all([
    runAgent('code-reviewer', { prompt: `Review changes in branch ${branch}` }),
    runAgent('test-writer', { prompt: `Write tests for changes in branch ${branch}` })
  ]);

  return { review, tests };
}
```

## 4. Ejecutar

```bash
claude workflows run review-and-test --branch feature/login
```

## Por qué esto es más barato que ruflo

- **Coordinación = 0 tokens**: el JS no llama al modelo
- **Cada subagent tiene modelo bloqueado**: usas Haiku para tareas simples, Sonnet/Opus para razonamiento
- **Sin overhead de framework**: no carga 60+ agentes que no usas
- **Sin memoria persistente cara**: si no la necesitas, no la pagas

## Cuándo NO usar esto y volver a ruflo

- Si necesitas que los agentes recuerden cosas entre sesiones (RAG persistente)
- Si necesitas federación entre máquinas
- Si quieres que el swarm aprenda con el tiempo (self-learning)
- Si tienes 50+ agentes con coordinación compleja (jerárquica + consenso)
