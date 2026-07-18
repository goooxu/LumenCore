# 04 材质与 BSDF

## BSDF 是什么？

**BSDF**（双向散射分布函数）描述：光从 $`\omega_i`$ 进来，有多大比例往 $`\omega_o`$ 出去。  
只反射、不透射时也称 **BRDF**。

在渲染方程里，它就是 $`f_r`$。单位要保证能量不凭空变多（实现上会做各种夹紧与近似）。

## 本项目的材质参数

Python / C++ 的 `Material` 大致包括：

| 字段 | 作用 |
|------|------|
| `base_color` | 漫反射底色或金属反射色 |
| `metallic` | 0 电介质 ↔ 1 金属 |
| `roughness` | 0 光滑 ↔ 1 粗糙 |
| `transmission` | >0.5 走 GGX 粗糙玻璃路径 |
| `ior` | 折射率（玻璃） |
| `emission` | 自发光 |
| `absorption` | 介质 Beer-Lambert 吸收 |
| `albedo_tex` | 可选漫反射纹理 |
| `normal_tex` | 可选切线空间法线贴图（OpenGL 约定，RGB→[-1,1]） |

不透明路径走 GGX；`transmission` 高则走 **GGX 微表面电介质**（粗糙透射/反射），仍支持 Beer-Lambert 吸收。

## 漫反射（Lambert）部分

理想漫反射 BRDF 常取：

```math
f_{\mathrm{diff}}=\frac{C}{\pi}.
```

其中 $C$ 为 `base_color`。采样用余弦半球：更常抽到法线附近方向，pdf 含 $\cos\theta/\pi$。

## 微表面与 GGX

真实金属/塑料高光不是完美镜面。微表面模型认为：宏观表面由许多微小镜面「小面」组成，法线分布由粗糙度控制。

![微表面粗糙度](figures/microfacet-roughness.avif)

*图：左光滑、右粗糙。粗糙时反射方向更分散，高光更糊。*

Cook–Torrance 风格镜面项可写成：

```math
f_s=\frac{D\cdot G\cdot F}{4\,(n\cdot\omega_o)\,(n\cdot\omega_i)}.
```

本项目（`src/common/bsdf.h`）：

| 符号 | 实现 |
|------|------|
| $D$ | GGX 法线分布 `ggx_d` |
| $G$ | Smith–GGX 几何遮挡 `smith_g_ggx` |
| $F$ | Schlick Fresnel `fresnel_schlick3` |
| $`F_0`$ | 电介质约 0.04；金属则用 `base_color` |

不透明最终 BRDF ≈ **漫反射 × (1−metal)×(1−F) + 镜面**，见 `eval_opaque_bsdf`。

### 采样：VNDF

`sample_ggx_vndf` 按可见法线分布抽微表面法线 $h$，再关于 $h$ 反射得到 $`\omega_i`$。  
漫反射与镜面用随机选择混合，pdf 在 `eval_opaque_bsdf` 里一并估算，供 MIS 使用。

![GGX Studio](../../outputs/ggx_studio.avif)

*图：后排金属球粗糙度递增；前排金属度递增。对应 `python/scenes/ggx_studio.py`。*

## 玻璃：GGX 粗糙透射

当 `transmission > 0.5`：

1. 用 **VNDF** 采样微表面法线 $`h`$（与不透明镜面相同）；
2. 在 $`h`$ 上算 Schlick Fresnel，按概率选择**反射**或**折射**（Snell 关于 $`h`$）；
3. 用 Heitz 风格权重 $`G_1(\omega_i)`$ 更新吞吐（实现里 `pdf=1`，`f` 已含蒙特卡洛权重）；
4. 进入介质时可设置 `medium_sigma = absorption`（Beer-Lambert，见 [06](06-volumes-media.md)）。

粗糙度低 → 接近清晰玻璃；粗糙度高 → 磨砂/雾化折射。

![Fresnel 反射/折射](figures/fresnel-refract.avif)

图注：空气→玻璃界面上，入射光分成反射与折射。掠射角时反射更强（Fresnel）。粗糙时这些方向绕微法线散开。

首版玻璃路径**不做**与面光/HDRI 的 NEE/MIS（与旧理想玻璃策略一致），避免双计。

## 法线贴图（切线空间）

当 `normal_tex >= 0` 且网格有 UV / 切线时：

1. 主机侧 `ensure_mesh_tangents` 补全顶点法线，并按 Lengyel/Mikkt 风格累积切线（`float4.w` = 手性 ±1）。
2. closesthit 插值 $T$、$N$，算 $B = N\times T\cdot w$，把贴图中的切线空间法线变到物体空间，再 `optixTransformNormal...` 到世界空间。
3. **着色 / NEE / BSDF** 用扰动后的 shading normal；**正反面判定**仍用几何面法线。

Sparky 的 `sparky_normal.avif` 与 albedo 共用 UV 图集（面板线、屏框、胸口浮雕等）。演示：`sparky` / `fireplace` / `physx_collapse`。

![Sparky](../../outputs/sparky.avif)

图注：右侧 Sparky 使用 albedo + 法线贴图。

## 代码地图

| 函数 | 文件 | 作用 |
|------|------|------|
| `eval_opaque_bsdf` | `bsdf.h` | 不透明求值 + pdf |
| `sample_opaque_bsdf` | `bsdf.h` | 不透明采样 |
| `sample_dielectric_bsdf` | `bsdf.h` | GGX 玻璃反射/透射采样 |
| `apply_normal_map` | `shaders.cu` | 切线空间法线 → 着色法线 |
| `ensure_mesh_tangents` | `mesh.cpp` | 顶点法线 / 切线 |
| closesthit 玻璃分支 | `shaders.cu` | 调用 dielectric 采样 + 介质 |
| `Material` | `nrtx.h` / bindings | 主机侧参数（含 `normal_tex`） |

## 小结

- 不透明：GGX 金属度-粗糙度；可选法线贴图。
- 玻璃：GGX 粗糙透射/反射 + 可选吸收。
- 看 `ggx_studio` 第三排（玻璃粗糙度渐变）与 `sparky`（法线）最容易对照。

下一章：[05 NEE、MIS 与 HDRI](05-nee-mis-hdri.md)。
