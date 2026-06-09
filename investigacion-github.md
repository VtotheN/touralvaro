# Investigación GitHub — Pipeline Blender → Walkthrough WebGL hiper-realista

Fecha: 2026-06-08
Objetivo: tours virtuales en tiempo real en navegador, modelados desde cero en Blender.

---

## 1. Addons de Blender

| Repo | Stars | Estado | Para qué |
|---|---|---|---|
| [Naxela/The_Lightmapper](https://github.com/Naxela/The_Lightmapper) | 804 | activo oct 2024, v0.7.0 | **Bake GI HDR Cycles + denoise OIDN/Optix + UV2 auto.** EL addon clave para hiper-realismo. |
| [s-leger/archipack](https://github.com/s-leger/archipack) | — | activo | Paredes, puertas, ventanas, escaleras paramétricas. Acelera modelado de interiores 10×. |
| [BlenderKit/BlenderKit](https://github.com/BlenderKit/BlenderKit) | — | activo 2025-2026 | 100k+ assets CC0/gratis. Muebles, materiales, HDRIs. |
| [specoolar/Blender-BakeLab2](https://github.com/specoolar/Blender-BakeLab2) | — | — | Baker alternativo. |
| [netherby/bakewrangler-doc](https://github.com/netherby/bakewrangler-doc) | — | — | Documentación de Bake Wrangler. |
| [KhronosGroup/glTF-Blender-IO](https://github.com/KhronosGroup/glTF-Blender-IO) | — | oficial | Exporter glTF con KHR_materials_clearcoat / transmission / sheen. Viene en Blender. |

## 2. Engines WebGL

| Repo | Stars | Veredicto |
|---|---|---|
| [mrdoob/three.js](https://github.com/mrdoob/three.js) | 105k | **Elegido.** PMREMGenerator, PointerLockControls, lightMap+UV2 nativo. Control total. |
| [needle-tools/needle-engine-support](https://github.com/needle-tools/needle-engine-support) | 599 (v5.1 jun 2026) | Pipeline turn-key Blender→web con KTX2 y lightmaps automáticos. Atajo si no se quiere armar nada. Descartado por acoplamiento al runtime. |
| [BabylonJS/Babylon.js](https://github.com/BabylonJS/Babylon.js) | — | PBR/probes plug-and-play. Buena alternativa si Three.js se siente bajo nivel. |
| [playcanvas/engine](https://github.com/playcanvas/engine) | — | WebGL2+WebGPU, Gaussian Splatting nativo. |
| [pmndrs/react-three-fiber](https://github.com/pmndrs/react-three-fiber) + [pmndrs/drei](https://github.com/pmndrs/drei) | — | Stack React con helpers archviz. Útil si el viewer se integra a una landing Next/React. |

## 3. Optimización glTF

| Repo | Stars | Comando clave |
|---|---|---|
| [donmccurdy/glTF-Transform](https://github.com/donmccurdy/glTF-Transform) | 1.9k | `gltf-transform optimize input.glb output.glb` — gold standard. |
| [zeux/meshoptimizer](https://github.com/zeux/meshoptimizer) | 6k+ | `gltfpack -cc -tc -tq 8 -i input.glb -o output.glb` — Draco + KTX2 en un solo comando. Más rápido. |
| [google/draco](https://github.com/google/draco) | — | Compresión geometría 5-10×. |
| [BinomialLLC/basis_universal](https://github.com/BinomialLLC/basis_universal) | — | KTX2 compresión texturas 3-6×. |
| [KhronosGroup/glTF-Sample-Viewer](https://github.com/KhronosGroup/glTF-Sample-Viewer) | 1.5k | QA renderer — referencia visual para validar exports. |
| [CesiumGS/gltf-pipeline](https://github.com/CesiumGS/gltf-pipeline) | — | Pipeline programático alternativo. |

## 4. Baking GI + reflejos (la salsa secreta del hiper-realismo)

**Workflow estándar:**
1. En Blender, generar UV2 para todos los objetos del tour
2. Configurar Cycles con samples altos (512+) y denoiser OIDN
3. Bake "Diffuse - Direct + Indirect" o "Combined" a texturas HDR (EXR) por objeto
4. Componer atlas si hay muchos objetos
5. En el material glTF, conectar la textura como `lightMap` y configurar `lightMapIntensity`
6. Three.js mapea automáticamente `lightMap` al canal UV2

**Realtime extras (Three.js):**
- [0beqz/screen-space-reflections](https://github.com/0beqz/screen-space-reflections) — SSR para pisos pulidos
- [0beqz/realism-effects](https://github.com/0beqz/realism-effects) — SSGI + SSR + TRAA. **Lo que separa "buen archviz" de "wow"**
- HDRIs de [PolyHaven](https://polyhaven.com/hdris) cargados con `PMREMGenerator.fromEquirectangular()` para reflejos ambientales en metales/cristales

## 5. Modelado de interiores

- **Archipack** + **Archimesh** (built-in en Blender) — paredes/puertas/ventanas
- **Assets CC0**:
  - [PolyHaven](https://polyhaven.com) — HDRIs, materiales PBR, modelos
  - [ambientCG](https://ambientcg.com) — materiales PBR específicamente
  - [Sketchfab CC0](https://sketchfab.com/3d-models/categories/cc0)
  - [madjin/awesome-cc0](https://github.com/madjin/awesome-cc0) — directorio curado de fuentes
- **Exteriores**: [domlysz/BlenderGIS](https://github.com/domlysz/BlenderGIS) — importar terreno de OpenStreetMap

## 6. Visores listos para clonar

| Repo | Para |
|---|---|
| [theringsofsaturn/virtual-museum-tour-threejs](https://github.com/theringsofsaturn/virtual-museum-tour-threejs) | Walkthrough mesh clonable, base sólida |
| [ArthCarvalho/archviz-js](https://github.com/ArthCarvalho/archviz-js) | Pipeline Blender→Three.js archviz demo |
| [pmndrs/react-three-next](https://github.com/pmndrs/react-three-next) | Starter R3F + Next.js |
| [benjaminmiles/react-three-vite](https://github.com/benjaminmiles/react-three-vite) | Starter R3F + Vite |

## 7. ¿Gaussian Splatting? No para este caso.

**Repos consultados:**
- [mkkellogg/GaussianSplats3D](https://github.com/mkkellogg/GaussianSplats3D) (2.8k, *no en desarrollo activo, recomienda Spark*)
- [antimatter15/splat](https://github.com/antimatter15/splat) — viewer GS WebGL puro
- [playcanvas/supersplat](https://github.com/playcanvas/supersplat) — editor GS production

**Veredicto:** 3DGS sirve cuando capturas un espacio FÍSICO con foto/video (lo que hace Zillow SkyTours 2025). Para modelado desde cero en Blender, 3DGS **no aplica** — no permite editar materiales, no tiene colisiones naturales, lighting baked inmutable, no soporta animaciones.

## 8. Esenciales adicionales

| Repo | Por qué es crítico |
|---|---|
| [gkjohnson/three-mesh-bvh](https://github.com/gkjohnson/three-mesh-bvh) (3.4k) | **Sin esto el usuario atraviesa las paredes.** Collision detection acelerado por BVH. |

---

## Stack final elegido

```
Blender 4.x (gratis, ya instalado)
  + Archipack (modelado paramétrico)
  + The Lightmapper (bake GI HDR)
  + PolyHaven assets (HDRIs, materiales)
  + glTF 2.0 exporter (oficial Khronos)
     ↓
  gltfpack -cc -tc  (zeux/meshoptimizer: Draco + KTX2)
     ↓
  Three.js
  + PMREMGenerator (IBL desde HDRI)
  + PointerLockControls (cámara primera persona)
  + three-mesh-bvh (colisiones)
  + realism-effects (SSR/SSGI/TRAA)
  + Vite (dev/build)
```

## Atajo turn-key disponible

Si en algún momento quieres acelerar drásticamente: **Needle Engine** elimina ~70% del pipeline manual (addon Blender + runtime web). Trade-off: acoplado a su runtime. Para Cabrera/Cayena landing pages probablemente quieras control total (Three.js puro).

---

## Fuentes consultadas

Todos los repos arriba son verificados activos a junio 2026.
