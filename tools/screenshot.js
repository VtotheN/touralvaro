#!/usr/bin/env node
/**
 * tools/screenshot.js — Headless Playwright scene screenshotter
 * Usage: node tools/screenshot.js [scene-id] [output.png]
 * Default: bf81-interior → /tmp/tour_screenshot.png
 */
const { chromium } = require('playwright');

const SCENE = process.argv[2] || 'bf81-interior';
const OUT   = process.argv[3] || `/tmp/tour_${SCENE}.png`;
const URL   = 'http://localhost:5174';
const TIMEOUT = 15000;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx     = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page    = await ctx.newPage();

  // Capture console for debugging
  page.on('console', m => { if (m.type() === 'error') console.error('[browser]', m.text()); });

  await page.goto(URL, { waitUntil: 'networkidle', timeout: TIMEOUT });

  // Select scene
  await page.evaluate((sceneId) => {
    const sel = document.getElementById('scene-select');
    if (sel) {
      sel.value = sceneId;
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }, SCENE);

  // Wait for 3D load (watch for canvas to have non-black pixels or progress bar gone)
  await page.waitForFunction(() => {
    const bar = document.getElementById('progress-bar');
    return !bar || parseFloat(bar.style.width || '0') >= 100 || bar.style.opacity === '0';
  }, { timeout: TIMEOUT }).catch(() => {});

  await page.waitForTimeout(3000); // let Three.js render settle

  // Click canvas to enter first-person mode
  await page.click('canvas', { position: { x: 640, y: 360 } }).catch(() => {});
  await page.waitForTimeout(1500);

  await page.screenshot({ path: OUT, fullPage: false });
  await browser.close();
  console.log(`Screenshot saved: ${OUT}`);
})();
