# Models

- `sparky.obj` / `sparky.mtl` / `sparky_albedo.png` / `sparky_normal.png` — **Sparky** boxy tread robot (~7k triangles, **AI-generated**): glass visor + pixel face, blue/white body, chest screen with **SPARKY** label, accordion arms, orange treads. Albedo + tangent-space normal atlas share UV layout; mesh/atlas can be regenerated via `scripts/gen_sparky.py`.
- `capsule_mascot.obj` / `capsule_mascot.mtl` — **Capsule Mascot** (~5.8k triangles, **AI-generated**): warm yellow capsule body with visor, eyes, belt, gloves/boots, and antenna. Groups exported as `usemtl` for multi-material scenes.
- `spot_triangulated.obj` / `spot_texture.png` — **Spot** (~5.9k triangles), Keenan Crane’s cow from the [CMU 3D Model Repository](https://www.cs.cmu.edu/~kmcrane/Projects/ModelRepository/). Triangulated mesh + 1024² albedo; no `.mtl` (bind texture via `Material.albedo_tex` in scenes).

Water surfaces are generated at runtime via `lumencore.make_water_surface(...)` (no baked water OBJ).

Regenerate Sparky with:

```bash
python3 scripts/gen_sparky.py
```
