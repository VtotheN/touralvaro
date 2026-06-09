// Captura thumbnails de cada escena disponible.
import { chromium } from 'playwright';
import { mkdir, readdir, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const MODELS_DIR = path.join(ROOT, 'viewer', 'public', 'models');
const OUT_DIR = path.join(ROOT, 'viewer', 'public', 'thumbnails');
const URL_BASE = 'http://localhost:5173';

await mkdir(OUT_DIR, { recursive: true });

const files = existsSync(MODELS_DIR) ? await readdir(MODELS_DIR) : [];
const scenes = files
  .filter((f) => f.endsWith('.glb') && !f.includes('optimized'))
  .map((f) => f.replace(/\.glb$/, ''));

if (scenes.length === 0) {
  console.error('[snapshot] No hay .glb en', MODELS_DIR);
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });

for (const slug of scenes) {
  const page = await ctx.newPage();
  const url = `${URL_BASE}/?scene=${encodeURIComponent(slug)}&snapshot=1`;
  console.log('[snapshot]', slug, '→', url);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60_000 });
  // Espera adicional para que cargue el glTF y baked textures
  await page.waitForTimeout(3500);
  const out = path.join(OUT_DIR, `${slug}.jpg`);
  await page.screenshot({ path: out, type: 'jpeg', quality: 78, fullPage: false });
  await page.close();
}

await browser.close();
console.log('[snapshot] Hecho.');
