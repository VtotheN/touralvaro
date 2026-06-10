#!/usr/bin/env node
// Usage: node screenshot.cjs <scene-id> [output-dir] [single-waypoint-id]
// Auto-reads config from test_projects/<scene-id>/config.json to place cameras
const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');

const SCENE   = process.argv[2] || 'bf81-interior';
const OUT_DIR = process.argv[3] || `/tmp/tour_${SCENE}`;
const SINGLE  = process.argv[4] || null;   // optional: shoot one room only
const TIMEOUT = 30000;

// Resolve project root relative to this file
const ROOT     = path.resolve(__dirname, '..');
const CFG_PATH = path.join(ROOT, 'test_projects', SCENE, 'config.json');

// Auto-compute camera from room bounds (Three.js coords)
function roomCamera(room) {
  const x0 = room.x, y0 = room.y, w = room.w, d = room.d;
  const zOff = room.z_offset || 0;  // mezzanine lift in Three.js Y space
  const camX  = x0 + w * 0.20;
  const camZ  = -(y0 + d * 0.20);
  const camY  = zOff + 1.70;
  const lookX = x0 + w * 0.70;
  const lookZ = -(y0 + d * 0.80);
  const lookY = zOff + 0.20;
  return [camX, camY, camZ, lookX, lookY, lookZ];
}

async function screenshot(page, cam, outPath) {
  if (cam) {
    await page.evaluate(([c]) => {
      if (window.__camera) {
        window.__camera.position.set(c[0], c[1], c[2]);
        window.__camera.lookAt(c[3], c[4], c[5]);
      }
    }, [cam]);
    await page.waitForTimeout(400);
  }
  await page.evaluate(() => { window.__captureNextFrame = true; });
  await page.waitForFunction(() => !!window.__captureResult, { timeout: 8000 });
  const dataUrl = await page.evaluate(() => window.__captureResult);
  await page.evaluate(() => { window.__captureResult = null; });
  const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
  fs.writeFileSync(outPath, Buffer.from(base64, 'base64'));
  console.log(`Screenshot: ${outPath}`);
}

(async () => {
  // Load config if exists, else use empty room list
  let rooms = [];
  if (fs.existsSync(CFG_PATH)) {
    const cfg = JSON.parse(fs.readFileSync(CFG_PATH, 'utf8'));
    rooms = cfg.rooms || [];
  }

  // Filter to single room if requested
  if (SINGLE) rooms = rooms.filter(r => r.id === SINGLE || r.label === SINGLE);

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--headless=new', '--enable-webgl', '--use-gl=swiftshader',
           '--no-sandbox', '--ignore-gpu-blocklist', '--disable-dev-shm-usage']
  });
  const ctx  = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();

  page.on('console', m => {
    if (m.type() === 'error' && !m.text().includes('404'))
      console.error('[err]', m.text().substring(0, 200));
  });

  await page.route(/polyhaven\.(org|com)/, r => r.abort());

  const URL = `http://localhost:5174/?nopp&scene=${encodeURIComponent(SCENE)}`;
  await page.goto(URL, { waitUntil: 'load', timeout: TIMEOUT });
  await page.waitForTimeout(3500);

  if (rooms.length === 0) {
    // No config — single default screenshot
    await screenshot(page, null, path.join(OUT_DIR, `${SCENE}.png`));
  } else {
    for (const room of rooms) {
      const cam     = roomCamera(room);
      const outFile = path.join(OUT_DIR, `${room.id}.png`);
      await screenshot(page, cam, outFile);
    }
  }

  await browser.close();
})();
