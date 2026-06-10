import * as THREE from 'three';

const SPHERE_RADIUS = 500;
const PITCH_LIMIT = (85 * Math.PI) / 180;
const ROTATE_SPEED = 0.003;
const KEY_ROTATE_SPEED = 0.8; // rad/s

// ── yaw/pitch (degrees) → unit vector on sphere surface ──────────────────────
function yawPitchToVec3(yawDeg, pitchDeg) {
  const y = THREE.MathUtils.degToRad(yawDeg);
  const p = THREE.MathUtils.degToRad(pitchDeg);
  return new THREE.Vector3(
    -Math.sin(y) * Math.cos(p),
     Math.sin(p),
    -Math.cos(y) * Math.cos(p)
  );
}

// ── Fade overlay helper ───────────────────────────────────────────────────────
function makeFadeOverlay(container) {
  const el = document.createElement('div');
  Object.assign(el.style, {
    position: 'absolute', inset: '0',
    background: '#000', opacity: '0',
    pointerEvents: 'none', zIndex: '50',
    transition: 'opacity 0.32s ease',
  });
  container.appendChild(el);
  const fadeTo = (o, ms = 320) =>
    new Promise(res => {
      el.style.transition = `opacity ${ms}ms ease`;
      el.style.opacity = String(o);
      setTimeout(res, ms + 20);
    });
  return { el, fadeTo };
}

// ── Room label ────────────────────────────────────────────────────────────────
function makeRoomLabel(container) {
  const el = document.createElement('div');
  Object.assign(el.style, {
    position: 'absolute', top: '16px', left: '50%',
    transform: 'translateX(-50%)',
    background: 'rgba(0,0,0,0.55)', color: '#fff',
    padding: '6px 18px', borderRadius: '20px',
    fontSize: '14px', fontWeight: '600',
    backdropFilter: 'blur(10px)',
    WebkitBackdropFilter: 'blur(10px)',
    border: '1px solid rgba(255,255,255,0.15)',
    fontFamily: '-apple-system, system-ui, sans-serif',
    letterSpacing: '-0.01em',
    pointerEvents: 'none', zIndex: '40',
  });
  container.appendChild(el);
  return el;
}

// ── Back-to-FPS button ────────────────────────────────────────────────────────
function makeBackBtn(container, sceneId) {
  const el = document.createElement('button');
  el.textContent = '← Explorar libre';
  Object.assign(el.style, {
    position: 'absolute', top: '16px', left: '16px',
    background: 'rgba(0,0,0,0.55)', color: '#fff',
    border: '1px solid rgba(255,255,255,0.18)',
    padding: '6px 14px', borderRadius: '20px',
    fontSize: '13px', cursor: 'pointer',
    backdropFilter: 'blur(10px)',
    WebkitBackdropFilter: 'blur(10px)',
    fontFamily: '-apple-system, system-ui, sans-serif',
    zIndex: '40',
  });
  el.addEventListener('click', () => {
    const url = new URL(window.location.href);
    url.searchParams.delete('mode');
    url.searchParams.set('scene', sceneId);
    window.location.href = url.toString();
  });
  container.appendChild(el);
  return el;
}

// ── Minimap canvas ────────────────────────────────────────────────────────────
function makeMinimap(container) {
  const wrap = document.createElement('div');
  Object.assign(wrap.style, {
    position: 'absolute', bottom: '16px', left: '16px',
    width: '200px', height: '200px',
    borderRadius: '12px', overflow: 'hidden',
    border: '1px solid rgba(255,255,255,0.15)',
    background: 'rgba(10,10,15,0.70)',
    backdropFilter: 'blur(8px)',
    WebkitBackdropFilter: 'blur(8px)',
    zIndex: '40', pointerEvents: 'none',
  });
  const canvas = document.createElement('canvas');
  canvas.width = 200; canvas.height = 200;
  wrap.appendChild(canvas);
  container.appendChild(wrap);
  return canvas;
}

function drawMinimap(canvas, tour, currentRoomId) {
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  if (!tour.floorplan || !tour.floorplan.rooms) return;
  const fpRooms = tour.floorplan.rooms;

  // Compute bounding box
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const r of fpRooms) {
    minX = Math.min(minX, r.x); minY = Math.min(minY, r.y);
    maxX = Math.max(maxX, r.x + r.w); maxY = Math.max(maxY, r.y + r.h);
  }
  const pad = 14;
  const scaleX = (W - pad * 2) / (maxX - minX || 1);
  const scaleY = (H - pad * 2) / (maxY - minY || 1);
  const scale = Math.min(scaleX, scaleY);
  const ox = pad + ((W - pad * 2) - (maxX - minX) * scale) / 2;
  const oy = pad + ((H - pad * 2) - (maxY - minY) * scale) / 2;

  const tx = x => ox + (x - minX) * scale;
  const ty = y => oy + (y - minY) * scale;

  // Draw rooms
  for (const r of fpRooms) {
    const isCurrent = r.id === currentRoomId;
    ctx.fillStyle = isCurrent ? 'rgba(100,160,255,0.35)' : 'rgba(255,255,255,0.10)';
    ctx.strokeStyle = isCurrent ? 'rgba(100,160,255,0.9)' : 'rgba(255,255,255,0.25)';
    ctx.lineWidth = isCurrent ? 1.5 : 1;
    ctx.beginPath();
    ctx.roundRect(tx(r.x), ty(r.y), r.w * scale, r.h * scale, 3);
    ctx.fill(); ctx.stroke();

    // Label
    ctx.fillStyle = isCurrent ? '#fff' : 'rgba(255,255,255,0.5)';
    ctx.font = `${isCurrent ? 700 : 400} 9px -apple-system,sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(r.label || r.id, tx(r.x + r.w / 2), ty(r.y + r.h / 2));
  }

  // Current position dot
  const currentFp = fpRooms.find(r => r.id === currentRoomId);
  if (currentFp) {
    const cx = tx(currentFp.x + currentFp.w / 2);
    const cy = ty(currentFp.y + currentFp.h / 2);
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#4a9eff';
    ctx.shadowColor = '#4a9eff';
    ctx.shadowBlur = 8;
    ctx.fill();
    ctx.shadowBlur = 0;
  }
}

// ── Hotspot container ─────────────────────────────────────────────────────────
function makeHotspotContainer(container) {
  const el = document.createElement('div');
  Object.assign(el.style, {
    position: 'absolute', inset: '0',
    pointerEvents: 'none', zIndex: '30',
    overflow: 'hidden',
  });
  container.appendChild(el);
  return el;
}

// ── Main export ───────────────────────────────────────────────────────────────
export async function startPanoViewer(container, sceneId) {
  // Ensure container is positioned
  if (getComputedStyle(container).position === 'static') {
    container.style.position = 'relative';
  }
  container.style.overflow = 'hidden';

  // 1. Load tour.json
  let tour;
  try {
    tour = await fetch(`/panoramas/${sceneId}/tour.json`).then(r => {
      if (!r.ok) throw new Error(`tour.json not found (${r.status})`);
      return r.json();
    });
  } catch (err) {
    console.warn('[panoViewer] Failed to load tour.json — using demo tour.', err);
    // Demo fallback so the viewer still works without actual panoramas
    tour = {
      startRoom: 'demo',
      rooms: [{
        id: 'demo',
        label: 'Demo Room',
        panorama: null,
        hotspots: [],
      }],
      floorplan: {
        rooms: [{ id: 'demo', label: 'Demo', x: 0, y: 0, w: 10, h: 8 }],
      },
    };
  }

  // 2. Three.js setup
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setSize(container.clientWidth || window.innerWidth, container.clientHeight || window.innerHeight);
  Object.assign(renderer.domElement.style, { position: 'absolute', inset: '0', display: 'block' });
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const W = container.clientWidth || window.innerWidth;
  const H = container.clientHeight || window.innerHeight;
  const camera = new THREE.PerspectiveCamera(90, W / H, 1, 1100);
  camera.position.set(0, 0, 0);

  // 3. Panorama sphere (inside-out)
  const geo = new THREE.SphereGeometry(SPHERE_RADIUS, 64, 32);
  geo.scale(-1, 1, 1);
  const mat = new THREE.MeshBasicMaterial({ color: 0x111318 });
  const sphere = new THREE.Mesh(geo, mat);
  scene.add(sphere);

  // 4. UI elements
  const { fadeTo } = makeFadeOverlay(container);
  const roomLabel = makeRoomLabel(container);
  const minimapCanvas = makeMinimap(container);
  const hotspotContainer = makeHotspotContainer(container);
  makeBackBtn(container, sceneId);

  // 5. Camera drag state
  let yaw = 0, pitch = 0; // radians
  let dragging = false, lastX = 0, lastY = 0;
  const keys = { ArrowLeft: false, ArrowRight: false, ArrowUp: false, ArrowDown: false };

  function applyLook() {
    pitch = Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, pitch));
    camera.rotation.order = 'YXZ';
    camera.rotation.y = yaw;
    camera.rotation.x = pitch;
  }

  renderer.domElement.addEventListener('mousedown', e => {
    dragging = true; lastX = e.clientX; lastY = e.clientY;
    renderer.domElement.style.cursor = 'grabbing';
  });
  window.addEventListener('mouseup', () => {
    dragging = false;
    renderer.domElement.style.cursor = 'grab';
  });
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    yaw   -= (e.clientX - lastX) * ROTATE_SPEED;
    pitch -= (e.clientY - lastY) * ROTATE_SPEED;
    lastX = e.clientX; lastY = e.clientY;
    applyLook();
  });
  renderer.domElement.style.cursor = 'grab';

  // Touch
  let lastTouchX = 0, lastTouchY = 0;
  renderer.domElement.addEventListener('touchstart', e => {
    lastTouchX = e.touches[0].clientX;
    lastTouchY = e.touches[0].clientY;
  }, { passive: true });
  renderer.domElement.addEventListener('touchmove', e => {
    yaw   -= (e.touches[0].clientX - lastTouchX) * ROTATE_SPEED;
    pitch -= (e.touches[0].clientY - lastTouchY) * ROTATE_SPEED;
    lastTouchX = e.touches[0].clientX;
    lastTouchY = e.touches[0].clientY;
    applyLook();
  }, { passive: true });

  // Keyboard
  window.addEventListener('keydown', e => { if (e.key in keys) keys[e.key] = true; });
  window.addEventListener('keyup',   e => { if (e.key in keys) keys[e.key] = false; });

  // 6. Hotspot management
  let hotspotEls = [];

  function clearHotspots() {
    for (const el of hotspotEls) el.remove();
    hotspotEls = [];
  }

  function buildHotspots(hotspots) {
    clearHotspots();
    if (!hotspots) return;
    for (const hs of hotspots) {
      const btn = document.createElement('button');
      btn.textContent = (hs.label || hs.target) + ' →';
      Object.assign(btn.style, {
        position: 'absolute',
        background: 'rgba(0,0,0,0.65)',
        color: '#fff',
        border: '1px solid rgba(255,255,255,0.25)',
        padding: '6px 14px',
        borderRadius: '20px',
        fontSize: '13px',
        fontWeight: '600',
        cursor: 'pointer',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        fontFamily: '-apple-system, system-ui, sans-serif',
        transform: 'translate(-50%, -50%)',
        transition: 'background 0.15s, transform 0.15s',
        whiteSpace: 'nowrap',
        pointerEvents: 'auto',
        zIndex: '30',
        display: 'none',
      });
      btn.addEventListener('mouseenter', () => {
        btn.style.background = 'rgba(74,158,255,0.75)';
        btn.style.transform = 'translate(-50%, -50%) scale(1.06)';
      });
      btn.addEventListener('mouseleave', () => {
        btn.style.background = 'rgba(0,0,0,0.65)';
        btn.style.transform = 'translate(-50%, -50%)';
      });
      btn.addEventListener('click', () => navigateTo(hs.target));
      btn._hs = hs;
      hotspotContainer.style.pointerEvents = 'auto';
      hotspotContainer.appendChild(btn);
      hotspotEls.push(btn);
    }
  }

  // Project hotspot dir onto screen each frame
  function updateHotspotPositions() {
    const cW = container.clientWidth || window.innerWidth;
    const cH = container.clientHeight || window.innerHeight;
    const camDir = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);

    for (const btn of hotspotEls) {
      const hs = btn._hs;
      const dir = yawPitchToVec3(hs.yaw || 0, hs.pitch || 0);
      const dot = dir.dot(camDir);
      if (dot < 0.15) { btn.style.display = 'none'; continue; }

      const ndc = dir.clone().project(camera);
      const x = ((ndc.x + 1) / 2) * cW;
      const y = ((-ndc.y + 1) / 2) * cH;

      // Keep within bounds with margin
      const margin = 60;
      if (x < margin || x > cW - margin || y < margin || y > cH - margin) {
        btn.style.display = 'none'; continue;
      }

      btn.style.display = 'block';
      btn.style.left = `${x}px`;
      btn.style.top  = `${y}px`;
    }
  }

  // 7. Panorama loading
  const texLoader = new THREE.TextureLoader();
  let currentRoomId = null;
  let navigating = false;

  async function loadRoom(roomId) {
    const room = tour.rooms.find(r => r.id === roomId);
    if (!room) { console.warn('[panoViewer] room not found:', roomId); return; }

    if (room.panorama) {
      const tex = await texLoader.loadAsync(room.panorama);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.minFilter = THREE.LinearMipmapLinearFilter;
      tex.generateMipmaps = true;
      sphere.material.map = tex;
      sphere.material.color.set(0xffffff);
      sphere.material.needsUpdate = true;
    } else {
      // No texture — use tinted sphere
      if (sphere.material.map) { sphere.material.map.dispose(); sphere.material.map = null; }
      sphere.material.color.set(0x1a1f2e);
      sphere.material.needsUpdate = true;
    }

    currentRoomId = roomId;
    roomLabel.textContent = room.label || roomId;
    buildHotspots(room.hotspots);
    drawMinimap(minimapCanvas, tour, currentRoomId);
  }

  async function navigateTo(roomId) {
    if (navigating) return;
    navigating = true;
    await fadeTo(1, 300);
    await loadRoom(roomId);
    await fadeTo(0, 300);
    navigating = false;
  }

  // 8. Resize
  window.addEventListener('resize', () => {
    const w = container.clientWidth || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });

  // 9. Animate
  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.1);

    // Keyboard look
    if (keys.ArrowLeft)  { yaw   += KEY_ROTATE_SPEED * dt; applyLook(); }
    if (keys.ArrowRight) { yaw   -= KEY_ROTATE_SPEED * dt; applyLook(); }
    if (keys.ArrowUp)    { pitch += KEY_ROTATE_SPEED * dt; applyLook(); }
    if (keys.ArrowDown)  { pitch -= KEY_ROTATE_SPEED * dt; applyLook(); }

    updateHotspotPositions();
    renderer.render(scene, camera);
  });

  // 10. Initial room load
  const startId = tour.startRoom || tour.rooms[0]?.id;
  if (startId) await loadRoom(startId);
  await fadeTo(0, 400);
}
