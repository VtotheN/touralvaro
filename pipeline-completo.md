# Pipeline completo — Blender → Walkthrough WebGL hiper-realista

Este documento describe el flujo completo, paso por paso, desde un Blender vacío hasta un tour navegable en un navegador.

---

## Fase 1 — Modelado en Blender

### 1.1 Setup inicial
- Blender 4.x (ya instalado en `/Applications/Blender.app`).
- Activar addons en `Preferences → Add-ons`:
  - **glTF 2.0 format** (viene incluido, sólo activar)
  - **Node: Wrangler** (viene incluido)
  - **Archipack** o **Archimesh** (modelado arquitectónico paramétrico)
  - **The Lightmapper** ([Naxela/The_Lightmapper](https://github.com/Naxela/The_Lightmapper)) — instalar manual desde .zip
  - **BlenderKit** ([BlenderKit/BlenderKit](https://github.com/BlenderKit/BlenderKit)) — 100k+ assets

### 1.2 Modelar el espacio
- Para interiores arquitectónicos usar **Archipack** (paredes, puertas, ventanas paramétricas) — 10× más rápido que mesh manual.
- Para volúmenes específicos: primitivas + booleans.
- Mantener **escala métrica real** (`Scene → Units → Metric`, scale 1.0). Cycles y Three.js asumen 1 unidad = 1 metro.

### 1.3 Materiales PBR
- Todos los materiales como `Principled BSDF`.
- Texturas desde [PolyHaven](https://polyhaven.com) o [ambientCG](https://ambientcg.com) — son PBR-completos (base color + roughness + normal + AO).
- Conexión típica via Node Wrangler: `Ctrl+T` con un Image Texture seleccionado para auto-conectar mapping + texcoord.

### 1.4 Iluminación
- **Sol direccional** + plano emisivo en ventanas (o un Area Light grande).
- HDRI mundial para iluminación indirecta y reflejos: `World → Environment Texture → HDR de PolyHaven`.
- Cycles, no Eevee (Cycles bakea mejor el GI).

---

## Fase 2 — Baking de iluminación (paso clave para hiper-realismo)

> Nota: el demo automático **no hace bake** porque The Lightmapper requiere GUI. Una vez instalado, el flujo es:

### 2.1 Con The Lightmapper (recomendado)
1. Seleccionar todos los objetos estáticos del tour
2. Panel `The Lightmapper`:
   - Resolution: 1024–4096 según escena
   - Samples: 256–1024
   - Denoise: OIDN (o Optix si tienes Nvidia)
   - UV Mode: Smart UV Project (genera UV2 automáticamente)
3. Click **Build Lightmaps**
4. Guarda las texturas como EXR (HDR) o PNG (LDR) en `blender/lightmaps/`
5. Conecta la textura como `lightMap` en el material (canal UV2)

### 2.2 Manual (sin addon)
Resumen rápido si quieres entender qué hace el addon:
1. Desempaquetar todos los meshes a un segundo UV channel (UV2) sin solapamientos
2. Crear texture image por mesh (o atlas compartido)
3. `Render → Bake → Type: Diffuse → Direct + Indirect (no Color)`
4. Bake → exportar texturas
5. Reasignar a un material output secundario o como lightMap

---

## Fase 3 — Exportación a glTF

### 3.1 Settings recomendados del exporter
- Format: **glTF Binary (.glb)** — un solo archivo
- Include:
  - ✅ Selected Objects (si exportas parte) o todo
  - ✅ Custom Properties (opcional)
  - ❌ Cameras (Three.js maneja la propia)
  - ❌ Punctual Lights (las luces baked ya están en el lightmap)
- Transform: ✅ +Y Up
- Geometry:
  - ✅ Apply Modifiers
  - ✅ UVs (incluye UV2 si existe)
  - ✅ Normals
  - ✅ Tangents
- Materials: Export
- Images: Automatic (mantiene PNG/JPEG según corresponda)
- Compression:
  - **Draco** ON para producción (no en demo, para no requerir decoder al cargar)
  - O dejar OFF y comprimir después con `gltfpack`

### 3.2 CLI (lo que usamos en el demo)
```bash
bash scripts/run-blender.sh
# → genera viewer/public/models/escena-demo.glb
```

---

## Fase 4 — Optimización del glTF

Sin este paso un tour de 50MB tarda 8 segundos en cargar. Con este paso baja a ~5MB.

### 4.1 Con gltf-transform (lo que usamos)
```bash
bash scripts/optimize.sh
# → escena-demo.optimized.glb
```
Compresión: Draco (geometría) + WebP (texturas). Reducción típica: **80–90%** del tamaño.

### 4.2 Con gltfpack (alternativa, vía meshoptimizer)
```bash
npx --yes gltfpack -cc -tc -tq 8 -i input.glb -o output.glb
# -cc: compress geometry (meshopt)
# -tc: compress textures (KTX2)
# -tq 8: texture quality (1-10)
```
KTX2 es superior a WebP en GPU memory, pero requiere transcoder en el cliente. Three.js lo soporta vía `KTX2Loader`.

---

## Fase 5 — Visor Three.js

### 5.1 Componentes clave (ya implementados en `viewer/`)
- **`main.js`** — escena, renderer, loader glTF, HDRI environment vía `PMREMGenerator`, sun light + shadows
- **`controls.js`** — `PointerLockControls` (cámara FPS) + `three-mesh-bvh` (collision sin atravesar paredes)
- **`index.html`** — HUD con instrucciones

### 5.2 Configuración de calidad
- `renderer.toneMapping = ACESFilmicToneMapping` — color cinematográfico
- `renderer.outputColorSpace = SRGBColorSpace` — correcto para web
- `PMREMGenerator` desde HDRI → reflejos ambientales
- `lightMapIntensity = 1.0` cuando haya lightmaps baked
- Sombras: `PCFSoftShadowMap`, bias `-0.0005`

### 5.3 Realismo extra (siguiente iteración)
Cuando la geometría esté lista, activar [0beqz/realism-effects](https://github.com/0beqz/realism-effects):
- **SSR** (Screen Space Reflections) — para pisos pulidos / mesas / cristales
- **SSGI** (Screen Space Global Illumination) — light bleeding en tiempo real
- **TRAA** — antialiasing temporal

Costo: ~20-30% de FPS, pero es la diferencia entre "se ve bien" y "wow".

---

## Fase 6 — Despliegue

### 6.1 Local (dev)
```bash
cd viewer
npm install
npm run dev
# http://localhost:5173
```

### 6.2 Producción
```bash
npm run build
# → viewer/dist/ — subir a Vercel/Netlify/Cloudflare Pages
```

El tour es estático (HTML + JS + .glb), se sirve desde cualquier CDN.

### 6.3 Embebido
Para incrustarlo en una landing existente (ej. Cabrera/Cayena):
```html
<iframe src="https://tu-tour.vercel.app" width="100%" height="600" allow="fullscreen"></iframe>
```
O importar el módulo directamente si la landing también es JS.

---

## Resumen del orden

```
1. Modelar en Blender (Archipack + assets PolyHaven)
2. (opcional iteración 2) Bake con The Lightmapper
3. bash scripts/run-blender.sh        → genera .glb
4. bash scripts/optimize.sh           → comprime el .glb
5. cd viewer && npm run dev           → prueba local
6. npm run build → subir dist/ a CDN  → tour público
```
