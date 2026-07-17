# LumenCore 技术报告

面向**刚开始学习计算机图形学**的同学：用尽量白话的方式，讲清楚 LumenCore 这套 **PhysX 5 刚体 + OptiX 9 路径追踪** 双栈演示里用到的数学与工程实现。

本报告与仓库源码一一对应；公式先讲直觉，再落到 `src/`、`python/scenes/` 里的具体函数。

## 建议阅读路线

1. 先读 [01 项目总览](01-overview.md)，建立「物理仿真 → 三角网格 → 光线追踪 → PNG」的大图。
2. 按 [02](02-rendering-equation.md) → [03](03-monte-carlo-path-tracing.md) → [04](04-materials-bsdf.md) → [05](05-nee-mis-hdri.md) 理解**画面是怎么算出来的**。
3. 再读 [06](06-volumes-media.md)（水与火焰）、[07](07-optix-implementation.md) / [08](08-host-pipeline.md)（OptiX 与 Host）、[09](09-physx-integration.md)（刚体）。
4. 最后用 [10](10-python-api-demos.md) 对照演示场景，用 [11](11-build-and-run.md) 自己跑一遍。

遇到符号不熟，翻 [附录：符号与术语](appendix-symbols.md)。

## 章节目录

| 章 | 文件 | 内容 |
|----|------|------|
| 01 | [01-overview.md](01-overview.md) | 项目总览与数据流 |
| 02 | [02-rendering-equation.md](02-rendering-equation.md) | 渲染方程入门 |
| 03 | [03-monte-carlo-path-tracing.md](03-monte-carlo-path-tracing.md) | 蒙特卡洛与路径追踪 |
| 04 | [04-materials-bsdf.md](04-materials-bsdf.md) | 材质与 BSDF（GGX / 玻璃） |
| 05 | [05-nee-mis-hdri.md](05-nee-mis-hdri.md) | NEE、MIS 与 HDRI |
| 06 | [06-volumes-media.md](06-volumes-media.md) | 体积与介质 |
| 07 | [07-optix-implementation.md](07-optix-implementation.md) | OptiX 实现 |
| 08 | [08-host-pipeline.md](08-host-pipeline.md) | Host 管线与后处理 |
| 09 | [09-physx-integration.md](09-physx-integration.md) | PhysX 集成 |
| 10 | [10-python-api-demos.md](10-python-api-demos.md) | Python API 与演示场景 |
| 11 | [11-build-and-run.md](11-build-and-run.md) | 构建与运行 |
| 附录 | [appendix-symbols.md](appendix-symbols.md) | 符号、术语、进阶阅读 |

## 演示场景 ↔ 原理对照

| 场景 | Gallery | 主要演示 |
|------|---------|----------|
| Cornell Box | `outputs/cornell.png` | 面光 NEE、玻璃折射、间接照明 |
| GGX Studio | `outputs/ggx_studio.png` | GGX 粗糙度 / 金属度、HDRI |
| Fireplace | `outputs/fireplace.png` | 火焰体积、暗场景、吉祥物材质 |
| PhysX Collapse | `outputs/physx_collapse.png` | GPU 刚体 + OptiX IAS 实例化 |
| Water Pool | `outputs/water_pool.png` | Beer-Lambert、水面法线 |
| Sparky | `outputs/sparky.png` | OBJ / albedo+法线贴图 / 聚光灯 |

## 配图说明

- `figures/`：概念示意图（半球、路径、微表面、NEE/MIS、HDRI、体积、Fresnel、OptiX、PhysX 循环）
- `../../outputs/`：本仓库在 RTX 5090 上渲出的真实结果图

---

*版本对应 LumenCore ≈ 0.13.x。报告描述以当前源码为准；未实现特性（如 BDPT、完整光谱、玻璃 NEE）不会假装写进去。*
