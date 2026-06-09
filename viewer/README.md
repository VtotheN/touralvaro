# touralvaro · viewer

Tour virtual interactivo en Three.js + Vite. Soporta multiples escenas
glTF, postprocessing avanzado (SSGI/SSR/TRAA via [realism-effects](https://github.com/0beqz/realism-effects))
y controles touch para movil.

## Arrancar

```bash
cd viewer
npm install
npm run dev
```

Luego abrir `http://localhost:5173/`.

## UI

- Esquina superior derecha:
  - `Escena` — dropdown con todas las escenas detectadas en `/public/models/`.
  - `Calidad` — `Bajo` / `Medio` / `Alto` / `Ultra`. La eleccion se guarda en `localStorage`.
  - `⛶` — pantalla completa.
- Esquina inferior izquierda — stats de la escena cargada.
- Esquina inferior derecha — FPS en tiempo real.
- Banner "Cargando escena…" mientras descarga el .glb.

### Niveles de calidad

| Nivel  | pixelRatio                       | Shadows | Postprocessing |
| ------ | -------------------------------- | ------- | -------------- |
| Bajo   | 1                                | OFF     | sin SSR/SSGI   |
| Medio  | 1                                | 1024    | sin SSR/SSGI   |
| Alto   | `min(dpr, 1.5)`                  | 2048    | SSR + SSGI     |
| Ultra  | `dpr` completo                   | 4096    | SSR + SSGI + TRAA |

## Controles

### Desktop

- Click sobre el canvas para activar pointer-lock.
- `WASD` / flechas — caminar.
- `Shift` — correr.
- Mouse — mirar.
- `ESC` — salir del pointer-lock.

### Movil

Cuando se detecta `ontouchstart`:

- Joystick virtual abajo a la izquierda — mover.
- Drag con un dedo en cualquier otro lado de la pantalla — mirar.
- El overlay "click to start" se oculta automaticamente.

## Como agregar una escena nueva

1. Exporta tu modelo a glTF binario (`.glb`) desde Blender. Recomendado:
   - Compresion Draco o Meshopt.
   - Texturas KTX2/Basis si el archivo es grande.
   - Lightmap bakeado si quieres look "baked" sin necesidad de SSGI.
2. Copia el `.glb` a `viewer/public/models/<nombre>.glb`.
3. Registra la escena en `viewer/src/scenes.js` agregando una entrada a
   `KNOWN_SCENES`:

   ```js
   {
     id: 'mi-escena',
     label: 'Mi escena',
     url: '/models/mi-escena.glb',
     baked: false, // true si tiene lightmap bakeado
   }
   ```

4. Recarga `http://localhost:5173/`. El viewer hace `HEAD` a cada URL
   conocida y solo muestra las que respondan `200`, asi que no hace falta
   hacer build ni reiniciar Vite.

> **Nota baked:** si `baked: true`, el viewer reduce `envMapIntensity` y
> desactiva `castShadow` en los meshes (porque la luz ya esta en la textura).

## Arquitectura

```
src/
  main.js            ← orquestador: escena, loaders, loop, presets
  controls.js        ← PointerLockControls + BVH collision + ejes externos (joystick)
  touch-controls.js  ← joystick virtual + drag-to-look (touch devices)
  scenes.js          ← catalogo de escenas + discovery via HEAD
  postprocessing.js  ← EffectComposer + SSGI/TRAA por nivel de calidad
index.html           ← UI (dropdowns, HUD, FPS, fullscreen)
public/models/       ← .glb (NO se modifica desde el viewer)
```

## Dependencias

- `three@^0.169` — render
- `three-mesh-bvh@^0.8` — colisiones aceleradas
- `postprocessing@^6.39` — composer + effect pipeline
- `realism-effects@^1.1` — SSGI, SSR, TRAA, motion blur, HBAO
- `vite@^5.4` — dev server + bundler

## Troubleshooting

- **El dropdown esta vacio** — significa que ningun `.glb` registrado en
  `KNOWN_SCENES` esta en `/public/models/`. Verifica los nombres.
- **SSGI/Ultra se ve raro** — los presets son genericos. Para tunear
  ajusta los valores en `src/postprocessing.js` (`SSGI_DEFAULTS`).
- **FPS bajo en movil** — usa preset `Bajo` o `Medio` y exporta tu glTF
  con texturas KTX2 + Draco. Vale la pena bakear lightmap.
