# touralvaro — Pipeline de tours virtuales WebGL

Modela en Blender, navega en el navegador. Walkthrough de primera persona, calidad hiper-realista.

## Quickstart

```bash
# 1) Generar la escena demo en Blender headless
bash scripts/run-blender.sh

# 2) Instalar dependencias del viewer
cd viewer
npm install

# 3) Optimizar el glTF generado
npm run optimize

# 4) Arrancar dev server
npm run dev
# abrir http://localhost:5173
# click sobre la escena para bloquear cursor, WASD para caminar
```

## Estructura

- `blender/` — escenas .blend y scripts Python que se corren con `Blender -b -P`
- `viewer/` — proyecto web Three.js + Vite
- `scripts/` — helpers (optimización glTF, runner de Blender)
- `pipeline-completo.md` — guía paso a paso del workflow completo
- `investigacion-github.md` — repos y addons relevantes con enlaces

## Documentación

- **Pipeline detallado**: `pipeline-completo.md`
- **Investigación GitHub**: `investigacion-github.md`
- **Stack**: Blender 4.x + The Lightmapper + glTF + Three.js + three-mesh-bvh + realism-effects

## Próximas iteraciones

1. Instalar addon [The Lightmapper](https://github.com/Naxela/The_Lightmapper) en Blender para bake real de GI
2. Conectar el MCP de Blender para iteración interactiva con Claude
3. Reemplazar la habitación demo con la geometría real del proyecto (Cayena / Cabrera)
4. Activar `realism-effects` (SSR/SSGI) cuando la geometría esté lista
