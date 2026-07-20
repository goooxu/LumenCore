# 05 NEE、MIS 与 HDRI

## 为什么只靠 BSDF 弹射不够？

若场景有一盏又小又亮的灯，BSDF 随机弹射很难「碰巧」打中它 → 高方差（噪点、萤火虫）。

**下一事件估计（Next Event Estimation, NEE）**：在表面点**显式采样光源**，连一条阴影射线，直接加上灯的贡献。

![NEE 与 MIS](figures/nee-mis.avif)

*图：左边 NEE 直接连灯；右边 BSDF 继续弹；中间用 MIS 按 pdf 加权，避免「算两遍」。*

## 本项目的灯

| 类型 | API | 备注 |
|------|-----|------|
| 四边形面光 | `Scene.add_quad_light` | 可配可见发光网格 |
| 聚光灯 | `Scene.add_spot_light` | 锥角 + penumbra |
| 火焰代理面光 | `add_flame_volume(..., add_proxy_light=True)` | 照亮房间 |
| HDRI | `Scene.load_env_map` | 环境当无限远光源 |

NEE 在 closesthit 中、且材质**不是玻璃、不是自发光**时启用（`enable_nee`）。**玻璃仍仅 BSDF 采样（无 NEE/MIS）**——粗糙透射的 pdf 与折射阴影留待后续版本。

对面光 / 聚光：采样灯 → 阴影测试 → `eval_opaque_bsdf` 得 $`f_r`$ → 按下方规则加权；若路径当前在均匀介质内（`medium_sigma ≠ 0`），再乘 **单程** Beer–Lambert $`T_r=e^{-\sigma d}`$（见 [06](06-volumes-media.md)）。对 HDRI：不在介质内时用平衡 MIS；**介质内跳过 env NEE**（距离无穷，避免武断 cap）。

## 平衡启发式 MIS

同一光照贡献可能被「灯采样」和「BSDF 采样」两种策略估到。Balance heuristic：

```math
w_a=\frac{p_a}{p_a+p_b}.
```

代码：`mis_balance(pdf_a, pdf_b)`（`bsdf.h`）。

**重要区分：**

| 光源 | BSDF 能否命中？ | NEE 权重 | BSDF 命中发光网格 |
|------|-----------------|----------|-------------------|
| `add_quad_light`（默认） | 否（纯虚拟） | **恒为 1** | 若另有 mesh emission：全权（与虚拟 NEE 不配对） |
| `add_quad_light(..., use_mis=True)` | 能（需同姿态发光网格） | `mis_balance(p_{\mathrm{light}}, p_{\mathrm{bsdf}})` | **depth>0**：`mis_balance(p_{\mathrm{bsdf}}, p_{\mathrm{light}})`，与 NEE 对称 |
| `add_spot_light` | 否 | **恒为 1** | — |
| HDRI 环境 | 能（miss） | `mis_balance` | miss 用 `last_pdf` 加权 |
| 仅网格 `emission`（无配对 quad） | 能（命中后路径终止） | 不做 NEE | 全权 |

需要**看得见的灯板**时：发光网格 + `add_quad_light(..., use_mis=True)`（同一 corner/u/v/emission）。灯板材质应把 **反射率**（`base_color`，近白）与 **出射**（`emission`）分开，不要 `base_color=(0,0,0)`。不要在 `use_mis=False` 时双注册。纯虚拟 fill / spot 可无灯具网格，金属高光来自 NEE，属预期。

**自发光命中（`shaders.cu`）：**

1. 累加 `throughput * emission * w`，然后终止路径。  
2. **相机直接看见灯**（`depth == 0`）：$`w=1`$。  
3. **BSDF 弹到 `use_mis` 面光**：用上一跳 `last_pdf` 与灯的立体角 pdf（含 `1/N_{\mathrm{lights}}` 选择）做 balance MIS，与 NEE 侧同一套公式，避免「撞灯全权 + NEE 半权」的偏亮。  
4. Denoiser 的 albedo 引导对自发光用 `base + clamp(emission,0,1)`，**不改 beauty 估计量**，避免纯黑 albedo 把灯像素抹掉。

NEE 时 HDRI 权重为 $`w = p_{\mathrm{env}} / (p_{\mathrm{env}} + p_{\mathrm{bsdf}})`$；miss 打到 HDRI 时，用上一跳存的 `last_pdf` 与 `pdf_env_map` 再加权。

## HDRI 环境贴图

环境光常用**等距柱状**（equirectangular）图：一张 2:1 的矩形表示整球方向。

![HDRI 等距柱状](figures/hdri-equirect.avif)

*图：上图是展开的环境；方向 $(\theta,\phi)$ 映射到像素 $(u,v)$。*

本项目流程（`src/host/env_map.cpp` + `shaders.cu`）：

1. `stbi_loadf` 读 Radiance `.hdr`。
2. 按亮度 × $\sin\theta$ 建行 CDF / 列 CDF（重要性采样亮区域）。
3. Miss 时 `sample_env_equirect` 查颜色。
4. NEE 时 `sample_env_map` 按 CDF 抽方向，并算立体角 pdf。

演示：`ggx_studio` / `materials_ball` / `outdoor_env` 使用 `assets/env/studio.hdr`。

## 阴影射线与自相交

`trace_shadow` / 路径续射使用几何法线上的 `offset_ray_origin`（Ray Tracing Gems 稳健偏移），`tmin` 约 $10^{-4}$，避免硬 epsilon 导致的痤疮或漏光。火焰体积代理盒与**玻璃**对阴影透明（`anyhit` 里 `IgnoreIntersection`），否则火球/玻璃里的灯照不出来。介质内 NEE 因此只做 **沿连线距离的指数衰减近似**，不模拟阴影路径的折射。

## 小结

- NEE：主动连灯，降方差；不透明表面 + 可选介质单程吸收。  
- 虚拟 quad/spot：默认 NEE 权重为 1；与发光网格配对的面光用 `use_mis=True`，**NEE 与 BSDF 命中双侧 MIS**；HDRI：MIS。  
- 自发光表面：命中后终止；配对面光时 depth>0 做 MIS。  
- 玻璃：v1 仅 BSDF，无 NEE/MIS。  
- HDRI：环境当光源，用亮度 CDF 采样；介质内不做 env NEE。  
- 射线原点沿几何法线偏移，减轻自相交。

下一章：[06 体积与介质](06-volumes-media.md)。
