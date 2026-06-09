#!/usr/bin/env node
// Usage: node screenshot.cjs [scene-id] [output.png] [waypoint-id]
const { chromium } = require('playwright');
const fs = require('fs');

const SCENE   = process.argv[2] || 'bf81-interior';
const OUT     = process.argv[3] || `/tmp/tour_${SCENE}.png`;
const WP      = process.argv[4] || null;
const URL     = `http://localhost:5174/?nopp&scene=${encodeURIComponent(SCENE)}`;
const TIMEOUT = 25000;

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--headless=new', '--enable-webgl', '--use-gl=swiftshader', '--no-sandbox', '--ignore-gpu-blocklist', '--disable-dev-shm-usage']
  });
  const ctx  = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await ctx.newPage();

  page.on('console', m => {
    const t = m.type();
    if (t === 'error' && !m.text().includes('404')) console.error(`[err]`, m.text().substring(0, 200));
  });

  // Only block polyhaven HDRI CDN
  await page.route(/polyhaven\.(org|com)/, r => r.abort());

  await page.goto(URL, { waitUntil: 'load', timeout: TIMEOUT });
  await page.waitForTimeout(3000);

  if (WP) {
    // Per-room diagonal corner shots: [camX, camY, camZ, lookX, lookY, lookZ]
    const CAM = {
      sala:    [0.4,  1.55, -0.5,  5.4,  1.2, -3.8],
      comedor: [7.4,  1.55, -0.8,  7.4,  1.20, -4.0],
      cocina:  [10.7, 1.55, -0.8, 10.7,  1.20, -4.0],
      master:  [4.2,  1.55, -4.5,  0.4,  1.2, -7.8],
      hab2:    [4.8,  1.55, -4.5,  8.1,  1.2, -7.8],
      'baño':  [10.2, 1.30, -5.8,  8.4,  0.80, -4.4],
      pasillo: [0.5,  1.55, -8.7, 10.0,  1.2, -8.7],
    };
    await page.evaluate(([wpId, camTable]) => {
      const c = camTable[wpId];
      if (c && window.__camera) {
        window.__camera.position.set(c[0], c[1], c[2]);
        window.__camera.lookAt(c[3], c[4], c[5]);
      }
    }, [WP, CAM]);
    await page.waitForTimeout(400);
  }

  // Signal tick to capture on next render, then wait for it
  await page.evaluate(() => { window.__captureNextFrame = true; });
  await page.waitForFunction(() => !!window.__captureResult, { timeout: 8000 });
  const dataUrl = await page.evaluate(() => window.__captureResult);

  const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
  fs.writeFileSync(OUT, Buffer.from(base64, 'base64'));
  console.log(`Screenshot: ${OUT}`);

  await browser.close();
})();
