// Controles touch para movil. Joystick virtual a la izquierda (mover) +
// drag con un dedo en el resto de la pantalla (mirar alrededor).
// La camara/colisiones se delegan al controller principal en controls.js
// a traves de los hooks que expone (input externo).

const JOY_RADIUS = 60;
const LOOK_SENSITIVITY = 0.0035; // rad / px

export function isTouchDevice() {
  return 'ontouchstart' in window || (navigator.maxTouchPoints || 0) > 0;
}

export function setupTouchControls(domElement, hooks) {
  // hooks: { setMoveAxes(x, y), addLook(dx, dy), tap() }
  const joystickEl = document.createElement('div');
  joystickEl.id = 'touch-joystick';
  joystickEl.innerHTML = '<div class="thumb"></div>';
  Object.assign(joystickEl.style, {
    position: 'fixed',
    left: '24px',
    bottom: '24px',
    width: `${JOY_RADIUS * 2}px`,
    height: `${JOY_RADIUS * 2}px`,
    borderRadius: '50%',
    background: 'rgba(255,255,255,0.08)',
    border: '1px solid rgba(255,255,255,0.2)',
    touchAction: 'none',
    zIndex: '20',
    pointerEvents: 'auto',
    backdropFilter: 'blur(6px)',
  });
  const thumb = joystickEl.querySelector('.thumb');
  Object.assign(thumb.style, {
    position: 'absolute',
    left: '50%',
    top: '50%',
    width: '48px',
    height: '48px',
    marginLeft: '-24px',
    marginTop: '-24px',
    borderRadius: '50%',
    background: 'rgba(255,255,255,0.65)',
    boxShadow: '0 2px 10px rgba(0,0,0,0.4)',
    transition: 'transform 0.05s linear',
  });
  document.body.appendChild(joystickEl);

  let joyTouchId = null;
  let lookTouchId = null;
  let lookLastX = 0;
  let lookLastY = 0;

  function setThumb(dx, dy) {
    thumb.style.transform = `translate(${dx}px, ${dy}px)`;
  }

  function onJoyMove(touch) {
    const rect = joystickEl.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    let dx = touch.clientX - cx;
    let dy = touch.clientY - cy;
    const len = Math.hypot(dx, dy);
    if (len > JOY_RADIUS) {
      dx = (dx / len) * JOY_RADIUS;
      dy = (dy / len) * JOY_RADIUS;
    }
    setThumb(dx, dy);
    // Convencion del controller: x derecha positiva, y adelante positivo.
    hooks.setMoveAxes(dx / JOY_RADIUS, -dy / JOY_RADIUS);
  }

  joystickEl.addEventListener('touchstart', (e) => {
    e.preventDefault();
    if (joyTouchId !== null) return;
    const t = e.changedTouches[0];
    joyTouchId = t.identifier;
    onJoyMove(t);
  }, { passive: false });

  window.addEventListener('touchmove', (e) => {
    for (const t of e.changedTouches) {
      if (t.identifier === joyTouchId) {
        onJoyMove(t);
        e.preventDefault();
      } else if (t.identifier === lookTouchId) {
        const dx = t.clientX - lookLastX;
        const dy = t.clientY - lookLastY;
        lookLastX = t.clientX;
        lookLastY = t.clientY;
        hooks.addLook(-dx * LOOK_SENSITIVITY, -dy * LOOK_SENSITIVITY);
        e.preventDefault();
      }
    }
  }, { passive: false });

  window.addEventListener('touchend', (e) => {
    for (const t of e.changedTouches) {
      if (t.identifier === joyTouchId) {
        joyTouchId = null;
        setThumb(0, 0);
        hooks.setMoveAxes(0, 0);
      } else if (t.identifier === lookTouchId) {
        lookTouchId = null;
      }
    }
  });

  window.addEventListener('touchcancel', (e) => {
    for (const t of e.changedTouches) {
      if (t.identifier === joyTouchId) {
        joyTouchId = null;
        setThumb(0, 0);
        hooks.setMoveAxes(0, 0);
      } else if (t.identifier === lookTouchId) {
        lookTouchId = null;
      }
    }
  });

  // Cualquier touch fuera del joystick = look.
  domElement.addEventListener('touchstart', (e) => {
    // Si el touch empieza sobre el joystick lo ignoramos aqui.
    for (const t of e.changedTouches) {
      const el = document.elementFromPoint(t.clientX, t.clientY);
      if (el && joystickEl.contains(el)) continue;
      if (lookTouchId !== null) continue;
      lookTouchId = t.identifier;
      lookLastX = t.clientX;
      lookLastY = t.clientY;
      e.preventDefault();
      break;
    }
  }, { passive: false });

  return {
    destroy() {
      joystickEl.remove();
    },
  };
}
