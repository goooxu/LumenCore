# PhysX 5 (NVIDIA Omniverse PhysX)

Headers under `include/` are vendored for convenience. Static libraries (`lib/*.a`)
and the GPU runtime (`bin/libPhysXGpu_64.so`) are **not** committed — build them with:

```bash
./scripts/setup_physx.sh
```

Or point CMake at an existing install:

```bash
cmake -S . -B build -DPHYSX_ROOT=/path/to/physx
```

Tested with tag `106.1-physx-5.4.2`. GPU rigid bodies need `libPhysXGpu_64.so` on
`LD_LIBRARY_PATH` (docker/run.sh adds `third_party/physx/bin` automatically).
If the GPU dispatcher is unavailable, LumenCore falls back to CPU PhysX.
