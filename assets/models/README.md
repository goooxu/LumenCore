# Models

- `sparky.obj` / `sparky.mtl` / `sparky_albedo.png` — original **Sparky** boxy tread robot (~7k triangles): glass visor + pixel face, blue/white body, chest screen with **SPARKY** label, accordion arms, orange treads.
- `capsule_mascot.obj` / `capsule_mascot.mtl` — original **Capsule Mascot** (~5.8k triangles, CC0): warm yellow capsule body with visor, eyes, belt, gloves/boots, and antenna. Groups exported as `usemtl` for multi-material scenes.

Regenerate Sparky with:

```bash
python3 scripts/gen_sparky.py
```
