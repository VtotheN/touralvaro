import * as THREE from 'three';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

export async function loadWaypoints(sceneId) {
  const base = sceneId.replace(/-optimized$/, '').replace(/-baked$/, '');
  try {
    const res = await fetch(`/waypoints/${base}.json`);
    if (!res.ok) return [];
    return await res.json();
  } catch { return []; }
}

export function createWaypointSystem() {
  const labelRenderer = new CSS2DRenderer();
  labelRenderer.setSize(window.innerWidth, window.innerHeight);
  Object.assign(labelRenderer.domElement.style, {
    position: 'fixed',
    inset: '0',
    pointerEvents: 'none',
    zIndex: '5',
  });
  document.body.appendChild(labelRenderer.domElement);

  const group = new THREE.Group();
  let currentScene = null;
  const entries = [];
  let clock = 0;
  let labelsVisible = true;

  function clear() {
    for (const { inner, outer, label2d } of entries) {
      label2d.element.remove();
      group.remove(inner, outer, label2d);
      inner.geometry.dispose(); inner.material.dispose();
      outer.geometry.dispose(); outer.material.dispose();
    }
    entries.length = 0;
  }

  function setWaypoints(scene, waypoints, onTeleport) {
    if (currentScene) currentScene.remove(group);
    clear();
    currentScene = scene;
    if (!waypoints.length) return;
    scene.add(group);

    for (const wp of waypoints) {
      const p = new THREE.Vector3(...wp.position);

      const inner = new THREE.Mesh(
        new THREE.CircleGeometry(0.09, 24),
        new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true })
      );
      inner.position.copy(p);
      inner.renderOrder = 999;

      const outer = new THREE.Mesh(
        new THREE.RingGeometry(0.11, 0.17, 24),
        new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true })
      );
      outer.position.copy(p);
      outer.renderOrder = 998;

      const div = document.createElement('div');
      div.textContent = wp.label;
      Object.assign(div.style, {
        background: 'rgba(8,8,8,0.80)',
        color: '#fff',
        padding: '5px 13px',
        borderRadius: '20px',
        fontSize: '13px',
        fontFamily: '-apple-system, system-ui, sans-serif',
        letterSpacing: '0.01em',
        whiteSpace: 'nowrap',
        cursor: 'pointer',
        pointerEvents: 'auto',
        userSelect: 'none',
        border: '1px solid rgba(255,255,255,0.22)',
        transform: 'translateY(-30px)',
        transition: 'background 0.12s, transform 0.12s, border-color 0.12s',
        boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
      });
      div.addEventListener('mouseenter', () => {
        div.style.background = 'rgba(50,110,255,0.90)';
        div.style.borderColor = 'rgba(255,255,255,0.45)';
        div.style.transform = 'translateY(-33px) scale(1.05)';
      });
      div.addEventListener('mouseleave', () => {
        div.style.background = 'rgba(8,8,8,0.80)';
        div.style.borderColor = 'rgba(255,255,255,0.22)';
        div.style.transform = 'translateY(-30px) scale(1)';
      });
      div.addEventListener('click', (e) => {
        e.stopPropagation();
        onTeleport(wp);
      });

      const label2d = new CSS2DObject(div);
      label2d.position.copy(p);
      group.add(inner, outer, label2d);
      entries.push({ inner, outer, label2d, wp });
    }
  }

  function render(scene, camera, dt) {
    clock += dt;
    for (const { inner, outer } of entries) {
      inner.lookAt(camera.position);
      outer.lookAt(camera.position);
      const pulse = 0.5 + 0.5 * Math.sin(clock * Math.PI * 1.5);
      outer.material.opacity = 0.25 + 0.3 * pulse;
      outer.scale.setScalar(0.85 + 0.2 * pulse);
    }
    if (labelsVisible) labelRenderer.render(scene, camera);
  }

  function resize(w, h) { labelRenderer.setSize(w, h); }

  function setLabelsVisible(v) {
    labelsVisible = v;
    labelRenderer.domElement.style.visibility = v ? 'visible' : 'hidden';
  }

  return { setWaypoints, render, resize, setLabelsVisible };
}
