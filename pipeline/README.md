# touralvaro pipeline

Automated pipeline: floor plan image + architectural renders → live 3D virtual tour.

## Quick start

```bash
# Single command — full automation
./pipeline/pipeline_zero.sh my-project floor_plan.jpg renders/ [--bake]
```

## Phases

| Phase | Script | Input | Output |
|---|---|---|---|
| 1. Read plan | auto_plan_reader.py | floor_plan.jpg | config.json |
| 2. Generate 3D | gen_apartment.py | config.json | model.glb |
| 3. Materials | render_to_pbr.py | renders/*.jpg | apply_materials.py |
| 4. Bake | instant_bake.py | model.glb | model_baked.glb |
| 5. Optimize | gltf-transform | model_baked.glb | model_final.glb |
| 6+7. Deploy | pipeline_zero.sh | — | ?scene=project-name |

## Requirements

```bash
pip install -r pipeline/requirements.txt
brew install tesseract          # OCR for plan reading
npm i -g @gltf-transform/cli    # GLB optimizer
# Blender 4.5+ at /Applications/Blender.app
```

## Config JSON schema

```json
{
  "name": "my-project",
  "ceiling_height": 2.8,
  "rooms": [
    {
      "id": "sala", "label": "Sala",
      "x": 0, "y": 0, "w": 5.0, "d": 4.0,
      "doors": [{"wall": "right", "offset": 0.5, "width": 0.9, "height": 2.1}],
      "windows": [{"wall": "front", "offset": 1.0, "width": 1.8, "height": 1.2, "sill": 0.9}]
    }
  ]
}
```
