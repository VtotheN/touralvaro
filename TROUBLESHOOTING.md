# Troubleshooting

## El tour no carga, pantalla negra

1. Abre la consola del navegador (`Cmd+Opt+J` en Chrome / `Cmd+Opt+I` en Safari).
2. Errores típicos:
   - `Failed to fetch /models/escena-demo.glb` → ejecutar `bash scripts/run-blender.sh` para generarlo.
   - `THREE.WebGLRenderer: context lost` → recargar la pestaña; suele ser tema de GPU del navegador.
   - `KTX2Loader … transcoder` → si usas un .glb con KTX2 pero el transcoder no carga, prueba con la versión sin KTX2 (`escena-demo.glb` en lugar de `.optimized.glb`).

## Blender no se encuentra

El runner asume `/Applications/Blender.app/Contents/MacOS/Blender`. Si lo tienes en otro lado:

```bash
export BLENDER_BIN=/ruta/a/Blender
bash scripts/run-blender.sh
```

(o edita `scripts/run-blender.sh` directamente)

## El HDRI no carga (sin reflejos)

El HDRI viene de polyhaven.com. Si fallan los reflejos:

1. Verifica conexión a internet.
2. Para producción, descarga el HDRI a `viewer/public/hdri/studio.hdr` y cambia el `HDRI_URL` en `viewer/src/main.js` a `/hdri/studio.hdr`.

## Caminar a través de paredes

- Verifica que `controls.setColliders(meshes)` se llame **después** de que el glTF cargó.
- Cada mesh debe tener `geometry.boundsTree` (se crea automático en `setColliders`).
- Si una pared es muy delgada (< 0.1m), el jugador puede atravesarla a alta velocidad. Aumenta el grosor.

## Sombras muy duras / cortadas

Edita `viewer/src/main.js`:

```js
sun.shadow.mapSize.set(4096, 4096);  // sube de 2048
sun.shadow.camera.left = -20;        // amplía el frustum
sun.shadow.camera.right = 20;
sun.shadow.bias = -0.0002;           // menos auto-sombra (acne)
```

## Performance baja en móvil

- Cambia preset de calidad a "Bajo" o "Medio" (selector arriba a la derecha).
- Para móviles, recomendado desactivar postprocessing pesado (SSGI).
- Reducir resolución del HDRI a 512px.

## El bake del lightmap falla

Si The Lightmapper falla headless:

1. Abre Blender GUI manualmente.
2. Abre `blender/escena-demo.blend`.
3. Activa el addon en `Edit → Preferences → Add-ons`.
4. Panel `The Lightmapper` → "Build Lightmaps".
5. Re-exporta con `Blender -b blender/escena-demo.blend -P blender/scripts/export-gltf.py`.

## El selector de escenas está vacío

- El selector hace `HEAD` requests a cada `.glb` esperado.
- Si está vacío, ningún .glb existe todavía. Ejecuta:
  ```bash
  bash scripts/run-blender.sh           # escena-demo
  bash scripts/build-escenas.sh         # cayena + cabrera (si Agente B terminó)
  ```

## Reset duro (volver al estado inicial)

```bash
cd ~/Desktop/touralvaro
rm -rf viewer/node_modules viewer/dist viewer/public/models/*.glb blender/escena-demo.blend
bash scripts/dev.sh
```
