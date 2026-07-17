# 10 Python API 与演示场景

## 最小可运行例子

```python
import lumencore as lc

scene = lc.Scene()
mat = scene.add_material(lc.Material(base_color=(0.8, 0.8, 0.8), roughness=0.5))
scene.add_mesh(lc.make_quad((0, 0, 0), (1, 0, 0), (0, 0, 1), mat))
cam = lc.Camera(eye=(0.5, 0.5, -1.5), lookat=(0.5, 0.2, 0.5), fov_y_deg=40, aspect=1.0)
cfg = lc.RenderConfig(width=512, height=512, spp=64, denoise=True, output_path="out.png")
lc.Renderer().render(scene, cam, cfg)
```

绑定在 `bindings/lumencore_module.cpp`：把 C++ `Scene` / `Material` / `PhysXWorld` 等暴露给 Python。

首页 Gallery：`atelier` 综合展示 + 两封面（`dusk_observatory` / `assembly_hall`）+ `gallery_compare` 特性 ON/OFF；下面各节仍用旧 `outputs/*.png` 单图做章节对照。

## 常用 API 速查

| 需求 | 调用 |
|------|------|
| 材质 | `scene.add_material(Material(...))` |
| 网格 | `add_mesh` → mesh index；`make_box` / `make_uv_sphere` / `make_quad` / `load_obj` |
| 实例 / PhysX | `add_instance(mesh_index, pose)`（IAS）；或 `apply_pose_to_*`（旧世界空间网格） |
| 变换 | `transform_mesh` / `apply_pose_to_*` |
| 面光 | `add_quad_light` |
| 聚光 | `add_spot_light` |
| 火焰 | `add_flame_volume` |
| HDRI | `load_env_map` / `clear_env_map` |
| 纹理 | `add_texture` + `Material.albedo_tex` / `normal_tex` |
| 物理 | `PhysXWorld().init()` … |

资源路径：Docker 内常用 `/work/...`；脚本里多用 `resolve_asset(...)` 兼容多种工作目录。

## 场景 ↔ 原理（带图）

### Atelier — 首页综合（Gallery 第一层）

脚本：`python/scenes/atelier.py` → `outputs/gallery/showcase.png`。PhysX 短仿真定格 + IAS，火焰 / HDRI / NEE / GGX / 法线 / Spot / Beer-Lambert 同框。

### 暮潮观测站 / Assembly Hall — 封面

- `python/scenes/dusk_observatory.py` → `outputs/gallery/dusk_observatory.png`：海岸暮色平台，多材质光学台 + Beer 潮池 + 火焰信标。
- `python/scenes/assembly_hall.py` → `outputs/gallery/assembly_hall.png`：工厂正午 HDR、磨砂透射炉火、吸收烟柱、PhysX 倾泻 Spot、糖果 Sparky 与镂空齿轮。

### gallery_compare — 特性 ON/OFF



脚本：`python/scenes/gallery_compare.py --feature … --mode on|off` → `outputs/gallery/compare/`。

### Cornell Box — 经典积分

![Cornell](../../outputs/cornell.png)

面光 NEE、玻璃、间接光。脚本：`python/scenes/cornell.py`。

### GGX Studio — 材质与 HDRI

![GGX Studio](../../outputs/ggx_studio.png)

粗糙度 / 金属度 / **玻璃粗糙度**梯度 + `studio.hdr`。脚本：`ggx_studio.py`。

### Fireplace — 体积光

![Fireplace](../../outputs/fireplace.png)

火焰体积 + 暗环境 + 多种吉祥物材质（Sparky 用法线贴图）。脚本：`fireplace.py`。

### PhysX Collapse — 双栈

![PhysX Collapse](../../outputs/physx_collapse.png)

GPU 刚体 + IAS 实例变换 + 玻璃火球。脚本：`physx_collapse.py`。

### Water Pool — 介质

![Water Pool](../../outputs/water_pool.png)

程序化水面、Beer-Lambert、角色反射。脚本：`water_pool.py`。

### Sparky — 资产管线

![Sparky](../../outputs/sparky.png)

OBJ + albedo / **法线贴图** + 聚光。脚本：`sparky.py`。

## 小结

- 改画面：先改 Python 场景。
- 改算法：下到 `shaders.cu` / `bsdf.h`。
- 每个 gallery 图都是某一章的「活教材」。

下一章：[11 构建与运行](11-build-and-run.md)。
