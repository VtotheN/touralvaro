import * as THREE from 'three';
import { PointerLockControls } from 'three/examples/jsm/controls/PointerLockControls.js';
import { MeshBVH, acceleratedRaycast, computeBoundsTree, disposeBoundsTree } from 'three-mesh-bvh';

THREE.Mesh.prototype.raycast = acceleratedRaycast;
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;

const WALK_SPEED = 2.4;
const RUN_SPEED = 4.5;
const EYE_HEIGHT = 1.7;
const PLAYER_RADIUS = 0.35;

export function setupControls(camera, domElement, { onLock, onUnlock, useTouch = false } = {}) {
  const controls = new PointerLockControls(camera, domElement);

  if (!useTouch) {
    domElement.addEventListener('click', () => controls.lock());
    controls.addEventListener('lock', () => onLock?.());
    controls.addEventListener('unlock', () => onUnlock?.());
  } else {
    // En touch siempre estamos "activos".
    onLock?.();
  }

  const keys = { f: false, b: false, l: false, r: false, run: false };
  window.addEventListener('keydown', (e) => {
    switch (e.code) {
      case 'KeyW': case 'ArrowUp':    keys.f = true; break;
      case 'KeyS': case 'ArrowDown':  keys.b = true; break;
      case 'KeyA': case 'ArrowLeft':  keys.l = true; break;
      case 'KeyD': case 'ArrowRight': keys.r = true; break;
      case 'ShiftLeft': case 'ShiftRight': keys.run = true; break;
    }
  });
  window.addEventListener('keyup', (e) => {
    switch (e.code) {
      case 'KeyW': case 'ArrowUp':    keys.f = false; break;
      case 'KeyS': case 'ArrowDown':  keys.b = false; break;
      case 'KeyA': case 'ArrowLeft':  keys.l = false; break;
      case 'KeyD': case 'ArrowRight': keys.r = false; break;
      case 'ShiftLeft': case 'ShiftRight': keys.run = false; break;
    }
  });

  // Ejes externos (joystick touch). x = strafe derecha, y = adelante.
  let extX = 0;
  let extY = 0;

  function setMoveAxes(x, y) {
    extX = Math.max(-1, Math.min(1, x || 0));
    extY = Math.max(-1, Math.min(1, y || 0));
  }

  // Look manual desde touch (yaw, pitch en radianes).
  const euler = new THREE.Euler(0, 0, 0, 'YXZ');
  const PI_2 = Math.PI / 2;
  function addLook(dyaw, dpitch) {
    euler.setFromQuaternion(camera.quaternion);
    euler.y += dyaw;
    euler.x += dpitch;
    euler.x = Math.max(-PI_2, Math.min(PI_2, euler.x));
    camera.quaternion.setFromEuler(euler);
  }

  let collisionMeshes = [];

  function setColliders(meshes) {
    // Dispose de boundsTrees viejos no en uso.
    collisionMeshes = meshes;
    for (const m of meshes) {
      if (m.geometry && !m.geometry.boundsTree) {
        try { m.geometry.computeBoundsTree(); } catch (e) { /* ignore */ }
      }
    }
  }

  const forward = new THREE.Vector3();
  const right = new THREE.Vector3();
  const move = new THREE.Vector3();
  const sphere = new THREE.Sphere(new THREE.Vector3(), PLAYER_RADIUS);

  function update(dt) {
    if (!useTouch && !controls.isLocked) return;
    const speed = (keys.run ? RUN_SPEED : WALK_SPEED) * dt;

    camera.getWorldDirection(forward);
    forward.y = 0;
    if (forward.lengthSq() < 1e-6) return;
    forward.normalize();
    right.crossVectors(forward, camera.up).normalize();

    move.set(0, 0, 0);
    if (keys.f) move.add(forward);
    if (keys.b) move.sub(forward);
    if (keys.r) move.add(right);
    if (keys.l) move.sub(right);
    if (extY) move.addScaledVector(forward, extY);
    if (extX) move.addScaledVector(right, extX);

    if (move.lengthSq() === 0) return;
    move.normalize().multiplyScalar(speed);

    const next = camera.position.clone().add(move);
    next.y = EYE_HEIGHT;

    sphere.center.copy(next);
    let blocked = false;
    for (const mesh of collisionMeshes) {
      if (!mesh.geometry || !mesh.geometry.boundsTree) continue;
      const localSphere = sphere.clone();
      localSphere.applyMatrix4(mesh.matrixWorld.clone().invert());
      if (mesh.geometry.boundsTree.intersectsSphere(localSphere)) {
        blocked = true;
        break;
      }
    }
    if (!blocked) camera.position.copy(next);
  }

  return { update, setColliders, controls, setMoveAxes, addLook };
}
