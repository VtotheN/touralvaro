# The Lightmapper — instalación y bake automatizado

Documentación del flujo de bake con [The Lightmapper](https://github.com/Naxela/The_Lightmapper)
(Naxela) integrado al pipeline de `touralvaro`.

## Versión instalada

- **Repo**: https://github.com/Naxela/The_Lightmapper
- **Rama**: `master` (rama por defecto; commit más reciente al instalar
  estaba fechado 2026-04-21)
- **`bl_info.version`** en `__init__.py`: `(0, 6, 3, 0)`
- **`bl_info.blender`**: declara soporte mínimo `(3, 1, 0)`. Lo usamos en
  Blender **5.1.1** y registra los operadores sin errores aparentes (la
  declaración mínima no es bloqueante).

## Carpeta exacta donde quedó instalado

```
/Users/isabella/Library/Application Support/Blender/5.1/scripts/addons/thelightmapper/
```

> Importante: el nombre del directorio **tiene que ser `thelightmapper`**
> (todo minúsculas, sin guión bajo) porque el propio addon hace
> `import thelightmapper` internamente cuando lanza el subprocess de bake
> en background. Si la carpeta se llama `The_Lightmapper-master` (como
> sale del zip) o `The_Lightmapper`, Blender lo registra igual pero los
> caminos internos de TLM rompen al intentar el bake en background.
>
> El script `scripts/bake.sh` renombra automáticamente al extraer el zip.

En Blender 5.x macOS la carpeta moderna para "extensions" es
`~/Library/Application Support/Blender/5.1/extensions/`, pero TLM no está
empaquetado como extensión nueva — sigue siendo addon legacy de Python,
así que va en `scripts/addons/`. Esa carpeta no existe por defecto; se
crea sola al instalar el primer addon legacy (o el runner la crea).

## Comando para re-bakear

Desde la raíz del workspace:

```bash
bash scripts/bake.sh
```

El runner hace, en orden:

1. Verifica que Blender 5.1 esté en `/Applications/Blender.app`.
2. Verifica que `blender/escena-demo.blend` exista; si no, llama a
   `scripts/run-blender.sh` para regenerarlo.
3. Si la carpeta `thelightmapper/` no está en `scripts/addons`, descarga
   el zip de master, descomprime y renombra.
4. Habilita el addon (`addon_enable` + `save_userpref`).
5. Ejecuta `blender/scripts/bake-con-lightmapper.py` con la `.blend`
   cargada, que llama a `thelightmapper.addon.utility.build.prepare_build(0, True)`
   (modo background; mismo entry-point que TLM usa internamente cuando se
   bakea desde la GUI con "Background bake" activo).
6. Después del bake, exporta a `viewer/public/models/escena-demo-baked.glb`.
7. Si algo en TLM falla (detectado vía `blender/.tlm-failed` o exit code
   != 0, o GLB no producido), corre `blender/scripts/bake-fallback.py`
   que usa `bpy.ops.object.bake` directo de Cycles (mismo flujo que
   `bake-lightmap.py`, sin tocarlo).
8. Compara tamaños: el GLB baked debe ser sustancialmente mayor que el
   original (porque ahora trae texturas baked embebidas).

### Resultado actual (verificado)

```
demo  (sin bake): 17.5 KB
baked (con TLM):  1.3 MB
```

El bake completo de la escena demo (14 meshes a 512×512) tarda ~5
segundos en CPU.

## Operadores relevantes de TLM

- `bpy.ops.tlm.build_lightmaps` — entry-point para GUI. **No corre en
  modo headless**: el operador detecta `bpy.app.background == True` y
  sólo imprime un mensaje pidiendo usar la función Python directamente.
- `bpy.ops.tlm.enable_set` — marca objetos como lightmapped (en nuestro
  script lo hacemos a mano iterando, para no depender del contexto de
  selección que es frágil en background).
- `bpy.ops.tlm.clean_lightmaps` — limpia y restaura materiales.
- `thelightmapper.addon.utility.build.prepare_build(0, True)` —
  **éste es el que usamos en headless**. El segundo parámetro fuerza
  `background_mode=True`.

## Cómo desinstalar

```bash
# 1) Desactivar y borrar la carpeta
rm -rf "$HOME/Library/Application Support/Blender/5.1/scripts/addons/thelightmapper"

# 2) Limpiar el flag en userpref (opcional; Blender ignora addons no
#    encontrados sin romper)
/Applications/Blender.app/Contents/MacOS/Blender -b --python-expr "
import bpy
try:
    bpy.ops.preferences.addon_disable(module='thelightmapper')
    bpy.ops.wm.save_userpref()
except Exception:
    pass
"

# 3) Borrar lightmaps generados (opcional)
rm -rf blender/Lightmaps  blender/lightmaps  viewer/public/models/escena-demo-baked.glb
```

## Caveats y limitaciones encontrados

1. **`bpy.ops.tlm.build_lightmaps` NO funciona desde CLI**. El operador
   detecta `bpy.app.background` y se rinde. Solución: llamar
   directamente a `thelightmapper.addon.utility.build.prepare_build(0, True)`.
   Esto sí funciona.

2. **El nombre del módulo importa**. Hay que llamar a la carpeta
   `thelightmapper` (no `The_Lightmapper` ni `The_Lightmapper-master`)
   porque el código del addon hace `import thelightmapper` literal en
   varios lugares. `bake.sh` lo maneja al extraer.

3. **Resolución es un enum de strings**. `tlm_mesh_lightmap_resolution`
   acepta solamente `'32'`,`'64'`,`'128'`,`'256'`,`'512'`,`'1024'`,
   `'2048'`,`'4096'`,`'8192'`. Pasarle `"3"` (índice) revienta. Hay que
   pasar el string del valor en píxeles.

4. **OpenCV opcional pero recomendado**. Si `tlm_filtering_use=True`
   pero `cv2` no está instalado en el Python de Blender, TLM aborta el
   bake con un `report({'INFO'}, ...)` silencioso. Lo dejamos en `False`
   por defecto en `bake-con-lightmapper.py`. Para activarlo:
   ```bash
   /Applications/Blender.app/Contents/Resources/5.1/python/bin/python3.13 \
       -m pip install opencv-python
   ```
   (la versión de Python varía por Blender, ajustar).

5. **OIDN denoise externo opcional**. `tlm_denoise_use=True` requiere
   apuntar a un binario OIDN externo. Lo dejamos en `False`; Cycles ya
   denoise internamente.

6. **Warnings de "vertex color won't be exported"** son normales. TLM
   crea una `vertex_colors` layer llamada `TLM` por objeto que el
   exporter de glTF detecta como activa pero sin uso en el node tree.
   No afecta el resultado.

7. **`use_nodes` deprecation warning en Blender 5/6**. Tanto TLM como el
   fallback usan `mat.use_nodes` que está marcado como deprecated.
   Funciona en 5.1.1 pero podría romperse en Blender 6.0+.

8. **El .blend se modifica**. TLM duplica materiales (los renombra
   `_baked`, agrega nodo `TLM_Lightmap`, etc.) y al re-guardar el .blend
   esos cambios persisten. Si querés volver al estado original, regenera
   la escena con `bash scripts/run-blender.sh`.

## Archivos relevantes

- `blender/scripts/bake-con-lightmapper.py` — script principal de bake
  via TLM.
- `blender/scripts/bake-fallback.py` — fallback puro Cycles que toma
  cualquier objeto MESH, hace smart unwrap a UV2, bake DIFFUSE
  direct+indirect, reconecta como Base Color y exporta GLB.
- `blender/scripts/bake-lightmap.py` — script original "skeleton" del
  usuario, intacto (no se borra ni se modifica). Sirve como referencia
  manual.
- `scripts/bake.sh` — orquestador end-to-end.
- `blender/lightmaps/` — PNGs generados por el fallback (no por TLM).
- `blender/Lightmaps/` — carpeta de cache donde TLM guarda sus EXR/PNGs
  internos durante el bake.
- `blender/.tlm-failed` — marcador temporal si TLM falló (lo crea
  `bake-con-lightmapper.py` y lo limpia `bake.sh`).
