# Escenas Cayena & Cabrera — Notas de modelado

Documenta las dos escenas Blender generadas a partir de los brochures de
Alvaro: **Cayena Residences Fase 02 (PH Loft)** y **Cabrera Hills Aparthotel
(Tipo I)**. Ambas se generan en Blender headless y se exportan a glTF para el
visor Three.js.

```bash
bash scripts/build-escenas.sh
# → viewer/public/models/cayena-loft.glb
# → viewer/public/models/cabrera-casa.glb
```

---

## 1 · Cayena Loft (PH Loft · Tipo B · 105 m²)

**Script:** `blender/scripts/cayena-loft.py`
**Salida:** `viewer/public/models/cayena-loft.glb`

### Datos extraídos del brochure

Fuentes:
- `~/Desktop/Cayena_Residences_Phase_02.pdf` (26 páginas, narrativa + áreas)
- `~/Desktop/Cayena_Fase_02_v4_renders (1).pdf` (igual al anterior con renders)
- `~/Desktop/Cayena_Loft_brochure.html` (inventario + precios)

| Dato | Valor |
|---|---|
| Proyecto | Cayena Residences · Fase 02 |
| Constructor | Inversiones 74GM SRL |
| Ubicación | Playa Encuentro, Cabarete, Costa Norte, RD |
| Unidades totales Fase 02 | 16 (8 ground floor + 8 PH loft) |
| **Tipo A — Ground Floor** | 72 m², 1 hab, 1.5 baños, terraza/playroom, piscina opcional |
| **Tipo B — PH Loft (este modelo)** | 105 m², 1 hab principal, 1.5 baños, mezzanine, doble altura (~5 m), lavandería, piscina opcional |
| Precios | Loft US$155.000 · PH US$195.000 |
| Concepto material | Piedra local, carpintería madera clara, "cinco metros de techo, ventanales verticales de piso a techo, una tabla de surf apoyada al lado" |

### Por qué modelé el PH Loft (Tipo B) y no el Ground Floor

El PH Loft tiene la doble altura + mezzanine que es lo más distintivo visualmente
del proyecto. Es el tipo que el brochure usa para los renders interiores
("Cinco metros de techo… un living que respira como un estudio de arquitecto").

### Dimensiones modeladas

| Dato | Valor del brochure | Valor en el modelo |
|---|---|---|
| Área construida | 105 m² | 10.5 × 10.0 = 105 m² ✓ |
| Altura libre sala (doble altura) | "5 metros de techo" | 5.0 m ✓ |
| Altura bajo mezzanine | (no especificada) | 2.6 m (asunción típica) |
| Espesor losa mezzanine | (no especificado) | 0.20 m (asunción) |
| Franja del mezzanine | (no especificada) | 4.0 m de profundidad sobre cocina + servicios |
| Habitaciones | 1 principal | 1 en mezzanine ✓ |
| Baños | 1.5 | 1 medio en PB + 1 completo en mezzanine ✓ |
| Lavandería | sí | sí (esquina NE planta baja) ✓ |
| Mezzanine | sí | sí (franja norte) ✓ |
| Ventanales sur | "verticales piso a techo" | 3 paneles vidrio, 4 pilastras madera clara ✓ |
| Piscina privada | opcional | NO modelada (depende de unidad) |

### Layout planta baja (extraído del concepto, sin plano cotado)

```
   ┌───────────────────────────────────────────┐
   │ Lavandería    Cocina abierta    Baño 1/2  │   ← mezzanine arriba
N  │  (NE)      (counter + isla)      (NO)     │     (franja 4m)
↑  ├──────────────── escalera ───────────────┤
   │                                           │
   │   Living + Comedor                        │
   │   doble altura 5m                         │
   │   sofá L + comedor 4 puestos              │
   │                                           │
   └──── ventanales piso-techo (3 paneles) ───┘
                       ↓ S (vista)
```

### Layout mezzanine

```
   ┌───────────────────────────────────────────┐
   │  Baño completo    Closet                  │
   │  (este)                                   │
   │                                           │
   │  Cama king (mirando al doble altura)      │
   │  + mesas de noche                         │
   │                                           │
   ├──── baranda metálica (mira al living) ───┤
                    (vacío al sur)
```

### Mobiliario modelado

- Living: sofá modular en L (3.0×0.95 + 0.95×1.8), mesa centro 1.4×0.7,
  comedor 1.6×0.9 con 4 sillas, "tabla de surf" decorativa apoyada
  (referencia explícita del brochure).
- Cocina: isla 2.4×0.9 + counter contra pared norte 4.5×0.65 + alacenas
  superiores + campana.
- Baño social: inodoro + lavamanos en mueble madera oscura.
- Lavandería: lavadora + secadora apiladas con puertas circulares cromadas.
- Mezzanine: cama king + 2 mesas de noche + closet de pared este +
  baño completo con doble lavamanos + ducha de vidrio.
- Escalera recta de 13 escalones contra pared oeste.

### Materiales (paleta del brochure)

- Piso planta baja: madera clara
- Piedra local en pared norte (referencia "piedra local del concepto")
- Paredes blancas
- Pilastras + carpintería: madera clara
- Counter cocina: granito oscuro
- Vidrio templado (alpha 0.25)

### Asunciones (qué no estaba en el PDF)

- Plano cotado real: el PDF muestra el plano como imagen pero sin medidas.
  Las 10.5×10.0 m son una deducción del área (105 m²) asumiendo planta
  rectangular.
- Distribución interna (cocina al norte, master en mezzanine sur del
  bloque norte): no especificada en el brochure. Asumida por lógica
  arquitectónica (servicios al fondo, sala al ventanal).
- Dimensiones exactas del mezzanine: el PDF dice "doble altura" pero no
  cuánta superficie ocupa el mezzanine. Asumí 4.0 × 10.5 = 42 m² (40%
  de la planta) como típico.
- Materiales: PBR Principled BSDF con colores base derivados de las
  descripciones del brochure ("madera clara", "piedra local"). No hay
  texturas reales — son colores planos. Para una versión final habría
  que sustituir por texturas PolyHaven/ambientCG (madera roble, piedra
  caliza local, granito oscuro).

---

## 2 · Cabrera Casa (Tipo I · 141 m²)

**Script:** `blender/scripts/cabrera-casa.py`
**Salida:** `viewer/public/models/cabrera-casa.glb`

### Datos extraídos del brochure

Fuente: `~/Desktop/Cabrera_Hills_Brochure_v2_180.pdf` (14 páginas).

| Dato | Valor |
|---|---|
| Proyecto | Cabrera Hills · 180° · Aparthotel |
| Desarrollo | Inversiones Rogue 2023 |
| Ubicación | Cabrera, Costa Norte, RD (filo del farallón, 125 m sobre el Atlántico) |
| Clasificación | CONFOTUR (turístico residencial) |
| Residencias totales | 16 |
| Niveles del edificio | 3 |
| Arquitectura | "Latones de madera natural, vidrio de piso a techo, geometría limpia" |
| **Tipo I (este modelo)** | 141 m², 3 hab, 2.5 baños, 1 parqueo, balcón cristal templado, porcelanato 60×60, cocina roble + granito, vista 180° |
| **Tipo II (no modelado)** | 211 m² Penthouse, 3 hab, 2.5 baños, terraza privada, pérgola, BBQ gas integrado, cerámica madera |
| Plan de pago | Reserva US$5.000 + 10% firma + 40% obra + 50% entrega |

### Por qué modelé el Tipo I y no el Penthouse

El Tipo I es el apartamento estándar (la mayoría de las 16 unidades son
Tipo I; sólo 1-2 son Penthouse). Modelar el estándar muestra la unidad
representativa del proyecto.

### Dimensiones modeladas

| Dato | Valor del brochure | Valor en el modelo |
|---|---|---|
| Área | 141 m² | 14.0 × 10.0 = 140 m² (objetivo 141) ✓ |
| Habitaciones | 3 | 3 (master 4.5×4.5, hab2 3.5×3.5, hab3 3.5×3.5) ✓ |
| Baños | 2.5 | 1 en-suite + 1 compartido + 1 medio social ✓ |
| Altura libre | (no especificada) | 2.7 m (asunción típica residencial) |
| Balcón | "cristal templado" | voladizo 14×1.5 m al sur con baranda de vidrio ✓ |
| Piso | "porcelanato 60×60" | material PBR claro tipo porcelanato (sin textura aún) |
| Cocina | "roble · granito" | counter en roble + topcounter granito oscuro ✓ |
| Latones de madera | sí en fachada | 18 latones verticales en pared norte ✓ |
| Vidrio piso a techo | sí | 4 paneles glass al sur con marcos de aluminio negro ✓ |
| Vista | 180° Atlántico | balcón orientado al sur con muebles lounge ✓ |

### Layout

```
                          ↑ N (latones de madera natural)
   ┌─────────────────────────────────────────────┐
   │ Cls   Hab.2     Hab.3       Baño compartido │
   │ M2    3.5×3.5   3.5×3.5     2.5×2.0         │
   ├──────────┬─────────┬────────┬───────────────┤
   │ Bath M   │ Closet M│        │ Cocina        │
   │ 2.5×2.0  │ 2.0×2.0 │        │ 2.5×4.0       │
   ├──────────┴─────────┤   Living + Comedor     │  ← cocina con
   │                    │   7.0×6.5              │     isla central
   │  Habitación        │   sofá L + chaise      │
   │  Principal         │   comedor 6 puestos    │
   │  (Master)          │   TV mural             │
   │  4.5×4.5           │                        │
   └────────────────────┴────────────────────────┘
   ═══════════════════════════════════════════════
        Balcón en voladizo 14.0 × 1.5 m
        cristal templado · 2 lounge + mesa
   ═══════════════════════════════════════════════
                          ↓ S (Atlántico · 180°)
```

### Mobiliario modelado

- Living: sofá modular L (3.2×1.0 + chaise 0.95×2.0), 3 cojines, mesa
  centro de roble, TV mural 1.6×0.95 + consola.
- Comedor: mesa 2.0×0.95 + 6 sillas (3 a cada lado).
- Cocina: counter en L contra pared este (4.0 m) + norte (2.2 m) en
  roble con topcounter granito, isla 1.8×0.9 con 3 banquetas, estufa +
  campana, alacenas superiores.
- Master: cama king + cabecera de listón de madera + 2 mesas de noche +
  banca al pie + closet walk-in.
- Master bath: doble lavamanos + espejo + ducha con plato terrazo +
  paneles de vidrio + inodoro.
- Hab 2 y Hab 3: cama queen + cabecera + mesa de noche + closet de pared.
- Baño compartido: lavamanos + espejo + ducha vidrio + inodoro.
- Balcón: 2 lounge chairs + mesa baja circular.

### Materiales

- Pisos: porcelanato 60×60 (color claro plano)
- Paredes: blancas
- Cocina: roble + granito oscuro
- Carpintería interior: roble (alacenas, cabeceras, comedor)
- Latones fachada norte: madera natural mid-tone
- Vidrio: cristal templado (alpha 0.22)
- Marcos: aluminio negro mate
- Terrazo: baños (plato ducha + topcounter)

### Asunciones

- El brochure no incluye plano cotado, sólo las áreas (141 y 211 m²) y
  los acabados/elementos. La planta 14×10 se eligió por proporción
  típica residencial (cliffside, frente largo al mar para maximizar
  vista 180°).
- Distribución interna: 3 habitaciones al norte (alejadas del filo),
  living abierto al sur (al mar) — es el partido lógico de cliffside
  residential.
- Altura libre 2.7 m: típica residencial. El brochure menciona "doble
  altura" en la experiencia común (Mirador Café), no en las residencias
  Tipo I — el Tipo II penthouse podría tener mayor altura pero no se
  detalla.
- El balcón se modela como voladizo, no como terraza interior. El
  brochure dice "balcón de cristal templado" lo cual sugiere voladizo
  con baranda de vidrio.
- Latones de madera están modelados como elemento de fachada norte
  (interior visible). El brochure los describe en la fachada del
  edificio — los reproduzco también en pared norte interior como
  acento visual.

---

## 3 · Qué falta para una versión "final" / producción

### Geometría
- Plano cotado real de cada tipología (pedir al arquitecto los DWG/PDF
  con dimensiones internas). Hoy son **deducciones** del área total.
- Subdivisión de muros con boolean cuts para huecos de puerta reales
  (los muros internos están sólidos hoy; las puertas son aberturas
  conceptuales).
- Modelado de detalles arquitectónicos: zócalos, batientes de puerta,
  herrería, sistema de iluminación empotrada.
- Penthouse Tipo II de Cabrera (211 m²) con terraza + pérgola + BBQ.
- Tipo A Ground Floor de Cayena (72 m²) con piscina privada + playroom.

### Materiales / texturas
- Reemplazar colores planos por texturas PBR reales:
  - Cayena: piedra local (jaspe/coralina), madera clara teca, granito
  - Cabrera: porcelanato 60×60 con grano, roble, granito, cerámica
    madera (tipo II), terrazo
- Bake de lightmap con The Lightmapper (descrito en
  `pipeline-completo.md`) para iluminación indirecta hiperrealista
- HDRI ambiental con la vista real del sitio (Playa Encuentro / cliff
  Atlántico).

### Mobiliario / props
- Substituir muebles primitivos por assets BlenderKit / PolyHaven /
  Sketchfab del estilo que muestra cada brochure:
  - Cayena: muebles modernos costeros (lino, madera clara, hilo)
  - Cabrera: muebles refinados resort (cuero, roble, metal negro)
- Plantas, libros, decoración, ropa de cama detallada.

### Exterior / contexto
- Modelar el conjunto (3 niveles, fachada con latones, piscina común,
  gazebo, jardines).
- Sitio: en Cayena la loma de Encuentro; en Cabrera el filo del
  farallón a 125 m con el Atlántico.

### Pipeline visor
- Tras tener .glb completos, optimizar con `scripts/optimize.sh` (Draco
  + WebP) para producción.
- Wiring en `viewer/src/main.js` para cargar las 3 escenas
  (escena-demo + cayena-loft + cabrera-casa) con un selector — eso es
  trabajo del AGENTE A/C (no en zona de este agente).

---

## 4 · Referencia rápida de archivos

| Archivo | Contenido |
|---|---|
| `blender/scripts/cayena-loft.py` | Script generador Cayena PH Loft |
| `blender/scripts/cabrera-casa.py` | Script generador Cabrera Tipo I |
| `blender/cayena/cayena-loft.blend` | Archivo Blender Cayena |
| `blender/cabrera/cabrera-casa.blend` | Archivo Blender Cabrera |
| `viewer/public/models/cayena-loft.glb` | glTF exportado Cayena (~199 KB) |
| `viewer/public/models/cabrera-casa.glb` | glTF exportado Cabrera (~271 KB) |
| `scripts/build-escenas.sh` | Runner que genera ambas escenas |
| `blender/ESCENAS-README.md` | Este documento |
