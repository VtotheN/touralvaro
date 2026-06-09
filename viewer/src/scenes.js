// Catalogo de escenas conocidas. Cada agente puede ir publicando .glb
// en /public/models/. Detectamos en runtime cuales existen y mostramos
// solo esas en el selector.

export const KNOWN_SCENES = [
  {
    id: 'test-apartment',
    label: 'Apartamento Test (Blender)',
    url: '/models/test-apartment.glb',
    baked: false,
  },
  {
    id: 'escena-demo-optimized',
    label: 'Escena demo (optimizada)',
    url: '/models/escena-demo.optimized.glb',
    baked: false,
  },
  {
    id: 'escena-demo',
    label: 'Escena demo',
    url: '/models/escena-demo.glb',
    baked: false,
  },
  {
    id: 'escena-demo-baked',
    label: 'Escena demo (baked)',
    url: '/models/escena-demo-baked.glb',
    baked: true,
  },
  {
    id: 'cayena-loft-optimized',
    label: 'Cayena loft (optimizada)',
    url: '/models/cayena-loft.optimized.glb',
    baked: false,
  },
  {
    id: 'cayena-loft',
    label: 'Cayena loft',
    url: '/models/cayena-loft.glb',
    baked: false,
  },
  {
    id: 'cabrera-casa-optimized',
    label: 'Casa Cabrera (optimizada)',
    url: '/models/cabrera-casa.optimized.glb',
    baked: false,
  },
  {
    id: 'cabrera-casa',
    label: 'Casa Cabrera',
    url: '/models/cabrera-casa.glb',
    baked: false,
  },
];

// Hace HEAD a cada URL y devuelve solo las que responden 200.
export async function discoverAvailableScenes(scenes = KNOWN_SCENES) {
  const checks = await Promise.all(
    scenes.map(async (s) => {
      try {
        const res = await fetch(s.url, { method: 'HEAD' });
        return res.ok ? s : null;
      } catch {
        return null;
      }
    })
  );
  return checks.filter(Boolean);
}

// Devuelve la escena por defecto entre las disponibles.
// Prioridad: la primera de KNOWN_SCENES que exista (orden manda).
export function pickDefaultScene(available) {
  if (!available.length) return null;
  return available[0];
}
