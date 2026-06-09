# Despliegue del tour

El tour es **estático** (HTML + JS + assets .glb) — se puede servir desde cualquier CDN gratuito.

## Opción 1 — Vercel (recomendado para Cayena/Cabrera)

```bash
bash scripts/deploy.sh vercel
```

Primera vez te pedirá login (te abre el navegador). Después es un solo comando por release.

URL pública: `https://touralvaro-XXXX.vercel.app` (puedes mapear dominio propio después).

## Opción 2 — Netlify

```bash
bash scripts/deploy.sh netlify
```

## Opción 3 — Cualquier hosting estático

```bash
bash scripts/deploy.sh build
# → viewer/dist/  (subir esta carpeta entera a Cloudflare Pages, S3, GitHub Pages, etc.)
```

## Opción 4 — Preview local (no público)

```bash
bash scripts/deploy.sh preview
# → http://localhost:4173/
```

## Embebido en una landing existente

Para meter el tour en `cayena-landing` o `cabrera`:

```html
<iframe
  src="https://tu-tour.vercel.app/?scene=cayena-loft"
  width="100%"
  height="600"
  allow="fullscreen; pointer-lock; xr-spatial-tracking"
  style="border:none; border-radius:12px;"
></iframe>
```

El parámetro `?scene=<nombre>` selecciona qué escena cargar (cayena-loft, cabrera-casa, escena-demo, etc.) sin pasar por el selector.

## Optimización para producción

Antes de deployar, vale la pena correr una optimización agresiva:

```bash
bash scripts/optimize.sh                       # WebP + Draco
# o si quieres KTX2 (mejor GPU memory):
npx gltfpack -cc -tc -tq 8 \
  -i viewer/public/models/cayena-loft.glb \
  -o viewer/public/models/cayena-loft.glb     # reemplazo in-place
```

## Capturas / thumbnails para metadata social

```bash
bash scripts/snapshot.sh
# → viewer/public/thumbnails/*.jpg
```

Usar esos .jpg como `og:image` en la landing.
