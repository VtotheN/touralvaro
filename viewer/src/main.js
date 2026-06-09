import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { KTX2Loader } from 'three/examples/jsm/loaders/KTX2Loader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { setupControls } from './controls.js';
import { setupTouchControls, isTouchDevice } from './touch-controls.js';
import { discoverAvailableScenes, pickDefaultScene } from './scenes.js';
import { createPostprocessing } from './postprocessing.js';
import { createWaypointSystem, loadWaypoints } from './waypoints.js';
import { VRButton } from 'three/examples/jsm/webxr/VRButton.js';

const HDRI_URL = 'https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/1k/studio_small_03_1k.hdr';
const QUALITY_KEY = 'touralvaro.quality';
const SCENE_KEY = 'touralvaro.scene';
const EYE_HEIGHT = 1.7;

const app          = document.getElementById('app');
const hud          = document.getElementById('hud');
const stats        = document.getElementById('stats');
const fpsLabel     = document.getElementById('fps');
const sceneSelect  = document.getElementById('scene-select');
const qualitySelect = document.getElementById('quality-select');
const fullscreenBtn = document.getElementById('fullscreen-btn');
const fadeOverlay  = document.getElementById('fade-overlay');
const progressBar  = document.getElementById('progress-bar');

const TOUCH = isTouchDevice();

// ── Renderer ─────────────────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.xr.enabled = true;
app.appendChild(renderer.domElement);

// ── Scene / Camera ────────────────────────────────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x101316);
const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 200);
camera.position.set(0, EYE_HEIGHT, 3);

// ── HDRI ──────────────────────────────────────────────────────────────────────
const pmrem = new THREE.PMREMGenerator(renderer);
pmrem.compileEquirectangularShader();
new RGBELoader().load(HDRI_URL, (hdr) => {
  scene.environment = pmrem.fromEquirectangular(hdr).texture;
  hdr.dispose();
}, undefined, () => {
  if (!NOPP) scene.add(new THREE.HemisphereLight(0xbcd0ff, 0x202018, 0.6));
});

// ── Lights ────────────────────────────────────────────────────────────────────
const sun = new THREE.DirectionalLight(0xffeacc, 2.0);
sun.position.set(4, 6, 3);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.near = 0.5; sun.shadow.camera.far = 30;
sun.shadow.camera.left = -10; sun.shadow.camera.right = 10;
sun.shadow.camera.top = 10;  sun.shadow.camera.bottom = -10;
sun.shadow.bias = -0.0005;
scene.add(sun, new THREE.AmbientLight(0xffffff, 0.15));

// ── Loaders ───────────────────────────────────────────────────────────────────
const dracoLoader = new DRACOLoader().setDecoderPath('https://www.gstatic.com/draco/v1/decoders/');
const ktx2Loader = new KTX2Loader()
  .setTranscoderPath('https://cdn.jsdelivr.net/gh/mrdoob/three.js@r169/examples/jsm/libs/basis/')
  .detectSupport(renderer);
const loader = new GLTFLoader()
  .setDRACOLoader(dracoLoader)
  .setKTX2Loader(ktx2Loader)
  .setMeshoptDecoder(MeshoptDecoder);

// ── Waypoints ─────────────────────────────────────────────────────────────────
const wpSystem = createWaypointSystem();

// ── Controls ──────────────────────────────────────────────────────────────────
const controls = setupControls(camera, renderer.domElement, {
  useTouch: TOUCH,
  onLock: () => {
    hud.classList.add('hidden');
    wpSystem.setLabelsVisible(false);
  },
  onUnlock: () => {
    hud.classList.remove('hidden');
    wpSystem.setLabelsVisible(true);
  },
});

if (TOUCH) {
  hud.classList.add('hidden');
  setupTouchControls(renderer.domElement, {
    setMoveAxes: (x, y) => controls.setMoveAxes(x, y),
    addLook: (dx, dy) => controls.addLook(dx, dy),
  });
}

// ── Postprocessing ────────────────────────────────────────────────────────────
const NOPP = new URLSearchParams(window.location.search).has('nopp');
const post = NOPP ? null : createPostprocessing(renderer, scene, camera);

// ── Camera tween (teleport) ───────────────────────────────────────────────────
let tween = null;

function onTeleport(wp) {
  const eyeY = wp.eyeY ?? EYE_HEIGHT;
  tween = {
    from: camera.position.clone(),
    to: new THREE.Vector3(wp.position[0], eyeY, wp.position[2]),
    t: 0,
    duration: 0.55,
  };
  if (!TOUCH) setTimeout(() => controls.controls.lock(), 680);
}

// ── Progress bar ──────────────────────────────────────────────────────────────
let _progressTimer = null;

function startProgress() {
  clearInterval(_progressTimer);
  progressBar.style.opacity = '1';
  progressBar.style.width = '0%';
  let elapsed = 0;
  _progressTimer = setInterval(() => {
    elapsed += 0.05;
    const p = 0.82 * (1 - Math.exp(-elapsed * 1.2));
    progressBar.style.width = `${p * 100}%`;
  }, 50);
}

function completeProgress() {
  clearInterval(_progressTimer);
  progressBar.style.width = '100%';
  setTimeout(() => {
    progressBar.style.opacity = '0';
    setTimeout(() => {
      progressBar.style.width = '0%';
      progressBar.style.opacity = '1';
    }, 380);
  }, 240);
}

// ── Fade overlay ──────────────────────────────────────────────────────────────
function fade(toOpacity, ms = 280) {
  return new Promise((resolve) => {
    fadeOverlay.style.transition = `opacity ${ms}ms ease`;
    fadeOverlay.style.opacity = String(toOpacity);
    setTimeout(resolve, ms + 30);
  });
}

// ── Scene disposal ────────────────────────────────────────────────────────────
let activeRoot = null;
let activeColliders = [];

function disposeMat(mat) {
  if (!mat) return;
  for (const k of Object.keys(mat)) {
    if (mat[k]?.isTexture) try { mat[k].dispose(); } catch {}
  }
  try { mat.dispose(); } catch {}
}

function disposeRoot(root) {
  if (!root) return;
  root.traverse((o) => {
    if (o.isMesh) {
      try { o.geometry.disposeBoundsTree?.(); } catch {}
      try { o.geometry.dispose(); } catch {}
      if (Array.isArray(o.material)) o.material.forEach(disposeMat);
      else disposeMat(o.material);
    }
  });
  scene.remove(root);
}

// ── Placeholder room (no .glb available) ─────────────────────────────────────
function buildPlaceholderRoom() {
  const root = new THREE.Group();
  const W = 6, D = 5, H = 2.8;
  const wallMat  = new THREE.MeshStandardMaterial({ color: 0xe8e3d8, roughness: 0.92 });
  const floorMat = new THREE.MeshStandardMaterial({ color: 0x4a3a2a, roughness: 0.55 });
  const ceilMat  = new THREE.MeshStandardMaterial({ color: 0xf2efe8, roughness: 0.95 });

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(W, D), floorMat);
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; root.add(floor);
  const ceil = new THREE.Mesh(new THREE.PlaneGeometry(W, D), ceilMat);
  ceil.rotation.x = Math.PI / 2; ceil.position.y = H; root.add(ceil);

  const wall = (w, h, x, y, z, ry = 0) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), wallMat);
    m.position.set(x, y, z); m.rotation.y = ry; m.receiveShadow = true; root.add(m);
  };
  wall(W, H, 0, H/2, -D/2); wall(W, H, 0, H/2,  D/2, Math.PI);
  wall(D, H, -W/2, H/2, 0,  Math.PI/2); wall(D, H, W/2, H/2, 0, -Math.PI/2);

  const tableMat = new THREE.MeshStandardMaterial({ color: 0x6b4423, roughness: 0.4 });
  const table = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.05, 0.8), tableMat);
  table.position.set(0, 0.75, 0); table.castShadow = table.receiveShadow = true; root.add(table);
  for (const [x, z] of [[-0.6,-0.3],[0.6,-0.3],[-0.6,0.3],[0.6,0.3]]) {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.75, 0.05), tableMat);
    leg.position.set(x, 0.375, z); leg.castShadow = leg.receiveShadow = true; root.add(leg);
  }
  const sofa = new THREE.Mesh(new THREE.BoxGeometry(2, 0.8, 0.9),
    new THREE.MeshStandardMaterial({ color: 0x2c3e50, roughness: 0.85 }));
  sofa.position.set(-1.5, 0.4, -1.5); sofa.castShadow = sofa.receiveShadow = true; root.add(sofa);
  return root;
}

function applyMeshSettings(root, baked) {
  const colliders = [];
  root.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = !baked;
      o.receiveShadow = true;
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      for (const m of mats) if (m) m.envMapIntensity = baked ? 0.5 : 1.0;
      colliders.push(o);
    }
  });
  return colliders;
}

// ── Load scene ────────────────────────────────────────────────────────────────
async function loadSceneByDescriptor(desc, isFirst = false) {
  if (!isFirst) await fade(1);
  startProgress();

  try {
    if (!desc) {
      disposeRoot(activeRoot);
      activeRoot = buildPlaceholderRoom();
      scene.add(activeRoot);
      activeColliders = applyMeshSettings(activeRoot, false);
      controls.setColliders(activeColliders);
      wpSystem.setWaypoints(scene, [], onTeleport);
    } else {
      const gltf = await new Promise((resolve, reject) =>
        loader.load(desc.url, resolve, undefined, reject)
      );
      disposeRoot(activeRoot);
      activeRoot = gltf.scene;
      scene.add(activeRoot);
      activeColliders = applyMeshSettings(activeRoot, !!desc.baked);
      controls.setColliders(activeColliders);
      const wps = await loadWaypoints(desc.id);
      wpSystem.setWaypoints(scene, wps, onTeleport);
      // Persist + URL
      localStorage.setItem(SCENE_KEY, desc.id);
      const url = new URL(window.location);
      url.searchParams.set('scene', desc.id);
      window.history.replaceState({}, '', url);
      // Stats (hidden by default; toggle with `)
      stats.textContent = `${desc.label} · ${activeColliders.length} meshes${desc.baked ? ' · baked' : ''}`;
    }
  } catch (err) {
    console.warn('Scene load failed', err);
    disposeRoot(activeRoot);
    activeRoot = buildPlaceholderRoom();
    scene.add(activeRoot);
    activeColliders = applyMeshSettings(activeRoot, false);
    controls.setColliders(activeColliders);
    wpSystem.setWaypoints(scene, [], onTeleport);
    stats.textContent = 'error · placeholder';
  }

  completeProgress();
  await fade(0);
}

// ── Quality presets ───────────────────────────────────────────────────────────
function applyQuality(level) {
  switch (level) {
    case 'low':
      renderer.setPixelRatio(1);
      renderer.shadowMap.enabled = false; sun.castShadow = false;
      break;
    case 'medium':
      renderer.setPixelRatio(1);
      renderer.shadowMap.enabled = true; sun.castShadow = true;
      sun.shadow.mapSize.set(1024, 1024);
      if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
      break;
    case 'high':
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
      renderer.shadowMap.enabled = true; sun.castShadow = true;
      sun.shadow.mapSize.set(2048, 2048);
      if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
      break;
    case 'ultra':
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.shadowMap.enabled = true; sun.castShadow = true;
      sun.shadow.mapSize.set(4096, 4096);
      if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
      break;
  }
  if (post) { post.setQuality(level); post.setSize(window.innerWidth, window.innerHeight); }
  localStorage.setItem(QUALITY_KEY, level);
}

// ── Stats toggle (backtick) ───────────────────────────────────────────────────
let statsVisible = false;
stats.style.display = 'none';
fpsLabel.style.display = 'none';
window.addEventListener('keydown', (e) => {
  if (e.code === 'Backquote') {
    statsVisible = !statsVisible;
    stats.style.display   = statsVisible ? 'block' : 'none';
    fpsLabel.style.display = statsVisible ? 'block' : 'none';
  }
});

// ── Resize ────────────────────────────────────────────────────────────────────
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  if (post) post.setSize(window.innerWidth, window.innerHeight);
  wpSystem.resize(window.innerWidth, window.innerHeight);
});

// ── Fullscreen ────────────────────────────────────────────────────────────────
fullscreenBtn?.addEventListener('click', () => {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {});
  else document.exitFullscreen?.();
});

// ── FPS counter ───────────────────────────────────────────────────────────────
let frames = 0, fpsLastT = performance.now();
function updateFps(now) {
  if (++frames, now - fpsLastT >= 500) {
    fpsLabel.textContent = `${Math.round(frames * 1000 / (now - fpsLastT))} fps`;
    frames = 0; fpsLastT = now;
  }
}

// ── Render loop ───────────────────────────────────────────────────────────────
const clock = new THREE.Clock();
function tick() {
  const dt = Math.min(clock.getDelta(), 0.1);

  if (tween) {
    tween.t += dt / tween.duration;
    const e = 1 - Math.pow(1 - Math.min(tween.t, 1), 3); // easeOutCubic
    camera.position.lerpVectors(tween.from, tween.to, e);
    if (tween.t >= 1) { camera.position.copy(tween.to); tween = null; }
  } else {
    controls.update(dt);
  }

  if (post) post.composer.render(dt);
  else {
    renderer.render(scene, camera);
    if (window.__captureNextFrame) {
      window.__captureResult = renderer.domElement.toDataURL('image/png');
      window.__captureNextFrame = false;
    }
  }
  wpSystem.render(scene, camera, dt);
  updateFps(performance.now());
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
async function bootstrap() {
  const available = await discoverAvailableScenes();

  if (sceneSelect) {
    sceneSelect.innerHTML = '';
    if (!available.length) {
      const opt = document.createElement('option');
      opt.textContent = '(sin escenas)'; opt.value = '';
      sceneSelect.appendChild(opt);
      sceneSelect.disabled = true;
    } else {
      for (const s of available) {
        const opt = document.createElement('option');
        opt.value = s.id; opt.textContent = s.label;
        sceneSelect.appendChild(opt);
      }
    }
  }

  // Priority: URL param > localStorage > default
  const urlScene = new URLSearchParams(window.location.search).get('scene');
  const savedId  = localStorage.getItem(SCENE_KEY);
  const initial  = available.find(s => s.id === urlScene)
    || available.find(s => s.id === savedId)
    || pickDefaultScene(available);

  const savedQ = localStorage.getItem(QUALITY_KEY) || 'high';
  if (qualitySelect) qualitySelect.value = savedQ;
  applyQuality(savedQ);

  if (initial && sceneSelect) sceneSelect.value = initial.id;
  await loadSceneByDescriptor(initial, true);

  // Screenshotter mode: expose camera + auto-clear overlay
  if (NOPP) {
    scene.background = new THREE.Color(0x7aaed0);  // sky blue through glass
    // Kill all lights (sun + hemisphere from HDRI fallback), add single soft ambient
    scene.traverse(obj => { if (obj.isLight) obj.intensity = 0; });
    scene.add(new THREE.AmbientLight(0xfff8f0, 0.8));
    renderer.shadowMap.enabled = false;

    window.__camera = camera;
    window.__scene = scene;
    window.__wpSystem = wpSystem;
    const wpParam = new URLSearchParams(window.location.search).get('wp');
    if (wpParam) {
      const wp = wpSystem.getWaypoints().find(w => w.id === wpParam);
      if (wp) {
        camera.position.set(wp.position[0], wp.position[1] ?? EYE_HEIGHT, wp.position[2]);
      }
    } else {
      const wps = wpSystem.getWaypoints();
      if (wps.length) {
        const wp = wps[0];
        // Sala: west side looking east — shows floor texture + doors + depth
        camera.position.set(wp.position[0] - 1.8, 1.5, wp.position[2] + 0.5);
        camera.lookAt(wp.position[0] + 5.0, 1.1, wp.position[2] - 0.5);
      }
    }
    await fade(0, 0);
    hud.classList.add('hidden');
    document.getElementById('topbar')?.remove();
    wpSystem.setLabelsVisible(false);
    wpSystem.setMarkersVisible(false);
  }

  if (!NOPP) {
    const vrBtn = VRButton.createButton(renderer);
    Object.assign(vrBtn.style, { bottom: '12px', left: '50%', transform: 'translateX(-50%)', zIndex: '12' });
    document.body.appendChild(vrBtn);
  }

  sceneSelect?.addEventListener('change', () => {
    const desc = available.find(s => s.id === sceneSelect.value);
    if (desc) loadSceneByDescriptor(desc);
  });
  qualitySelect?.addEventListener('change', () => applyQuality(qualitySelect.value));

  renderer.setAnimationLoop(tick);
}

bootstrap();
