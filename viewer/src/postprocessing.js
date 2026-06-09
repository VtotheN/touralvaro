// Wrapper sobre postprocessing + realism-effects.
// Devuelve { composer, setQuality(level) } y se actualiza dinamicamente
// segun el preset Bajo/Medio/Alto/Ultra.

import * as POSTPROCESSING from 'postprocessing';
import { HalfFloatType } from 'three';
import { SSGIEffect, TRAAEffect, VelocityDepthNormalPass } from 'realism-effects';

// SSGI default options (de readme), tuneadas a algo razonable para interiores.
const SSGI_DEFAULTS = {
  distance: 6,
  thickness: 1.2,
  autoThickness: true,
  maxRoughness: 0.7,
  blend: 0.9,
  denoiseIterations: 1,
  denoiseKernel: 2,
  denoiseDiffuse: 10,
  denoiseSpecular: 10,
  depthPhi: 2,
  normalPhi: 50,
  roughnessPhi: 1,
  envBlur: 0.5,
  importanceSampling: true,
  directLightMultiplier: 1,
  steps: 20,
  refineSteps: 5,
  spp: 1,
  resolutionScale: 0.75,
  missedRays: false,
};

export function createPostprocessing(renderer, scene, camera) {
  const composer = new POSTPROCESSING.EffectComposer(renderer, {
    frameBufferType: HalfFloatType,
  });

  // RenderPass tradicional (lo usamos cuando NO esta activo SSGI).
  const renderPass = new POSTPROCESSING.RenderPass(scene, camera);

  // Pass de velocity/depth/normal compartido por SSGI y TRAA.
  let velocityDepthNormalPass = null;
  let ssgiEffect = null;
  let traaEffect = null;
  let ssgiPass = null;
  let traaPass = null;

  let currentLevel = null;

  function clearPasses() {
    // Quita TODOS los pases (incluyendo renderPass) para reconfigurar.
    while (composer.passes.length) {
      composer.removePass(composer.passes[0]);
    }
  }

  function disposeRealism() {
    try { ssgiPass?.dispose?.(); } catch {}
    try { traaPass?.dispose?.(); } catch {}
    try { velocityDepthNormalPass?.dispose?.(); } catch {}
    ssgiPass = null;
    traaPass = null;
    ssgiEffect = null;
    traaEffect = null;
    velocityDepthNormalPass = null;
  }

  function applyLow() {
    clearPasses();
    disposeRealism();
    composer.addPass(renderPass);
  }

  function applyMedium() {
    clearPasses();
    disposeRealism();
    composer.addPass(renderPass);
  }

  function applyHigh() {
    // Alto: SSR/SSGI ligero, sin TRAA.
    clearPasses();
    disposeRealism();
    velocityDepthNormalPass = new VelocityDepthNormalPass(scene, camera);
    composer.addPass(velocityDepthNormalPass);
    ssgiEffect = new SSGIEffect(scene, camera, velocityDepthNormalPass, {
      ...SSGI_DEFAULTS,
      resolutionScale: 0.5,
      steps: 12,
      refineSteps: 3,
    });
    ssgiPass = new POSTPROCESSING.EffectPass(camera, ssgiEffect);
    composer.addPass(ssgiPass);
  }

  function applyUltra() {
    clearPasses();
    disposeRealism();
    velocityDepthNormalPass = new VelocityDepthNormalPass(scene, camera);
    composer.addPass(velocityDepthNormalPass);
    ssgiEffect = new SSGIEffect(scene, camera, velocityDepthNormalPass, SSGI_DEFAULTS);
    traaEffect = new TRAAEffect(scene, camera, velocityDepthNormalPass);
    // SSGI hace render por si mismo; TRAA en su propio pase.
    ssgiPass = new POSTPROCESSING.EffectPass(camera, ssgiEffect);
    traaPass = new POSTPROCESSING.EffectPass(camera, traaEffect);
    composer.addPass(ssgiPass);
    composer.addPass(traaPass);
  }

  function setQuality(level) {
    if (level === currentLevel) return;
    currentLevel = level;
    switch (level) {
      case 'low':    applyLow();    break;
      case 'medium': applyMedium(); break;
      case 'high':   applyHigh();   break;
      case 'ultra':  applyUltra();  break;
      default:       applyMedium(); break;
    }
  }

  function setSize(w, h) {
    composer.setSize(w, h);
  }

  function setSceneCamera(newScene, newCamera) {
    // Recrea RenderPass y los effects para usar la nueva escena.
    // (Util si en el futuro se intercambia la escena entera; por ahora
    // mantenemos la misma scene y solo cambiamos su contenido.)
  }

  return {
    composer,
    setQuality,
    setSize,
    setSceneCamera,
    get level() { return currentLevel; },
  };
}
