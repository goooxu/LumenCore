# 附录：符号与术语表

## 常用符号

| 符号 | 读法 / 含义 |
|------|-------------|
| $`L_o, L_i, L_e`$ | 出射 / 入射 / 自发光辐射亮度 |
| $`f_r`$ | BSDF（或 BRDF） |
| $n$ | 表面法线 |
| $`\omega_o, \omega_i`$ | 出射、入射方向（通常指从表面指向外） |
| $\mathcal{H}^+$ | 法线朝上的半球 |
| $p(\omega)$ | 方向采样的概率密度（立体角测度） |
| $T$ / throughput | 路径吞吐 |
| $D, G, F$ | 微表面分布、几何项、Fresnel |
| $`\sigma_t`$ | 介质消光 / 吸收相关量 |
| spp | 每像素样本数 |
| NEE | 下一事件估计 |
| MIS | 多重重要性采样 |
| GAS | 几何加速结构（OptiX） |
| IAS | 实例加速结构（OptiX） |
| SBT | Shader Binding Table |
| HDRI | 高动态范围环境贴图 |
| AOV | 任意输出变量（如 albedo、normal） |
| RR | 俄罗斯轮盘 |

## 中英术语对照

| 中文 | English |
|------|---------|
| 路径追踪 | Path tracing |
| 渲染方程 | Rendering equation |
| 双向散射分布函数 | BSDF |
| 微表面 | Microfacet |
| 重要性采样 | Importance sampling |
| 下一事件估计 | Next Event Estimation |
| 多重重要性采样 | Multiple Importance Sampling |
| 辐射亮度 | Radiance |
| 色调映射 | Tone mapping |
| 刚体动力学 | Rigid-body dynamics |
| 加速结构 | Acceleration structure |
| 降噪 | Denoising |

## 本仓库关键文件速查

| 主题 | 文件 |
|------|------|
| GGX / MIS | `src/common/bsdf.h` |
| 路径内核 | `src/device/shaders.cu` |
| 参数块 | `src/common/LaunchParams.h` |
| OptiX Host | `src/host/renderer.cpp` |
| HDRI | `src/host/env_map.cpp` |
| PhysX | `src/host/physx_world.cpp` |
| Python 绑定 | `bindings/lumencore_module.cpp` |

## 推荐进阶阅读

1. Pharr, Jakob, Humphreys — *Physically Based Rendering (PBRT)*：路径追踪与材料的标准教材。  
2. NVIDIA OptiX Programming Guide：Pipeline / SBT / 穿越语义。  
3. Walter et al. — Microfacet Models for Refraction（微表面经典）；Heitz — VNDF 采样相关笔记。  
4. Veach — *Robust Monte Carlo Methods for Light Transport*：MIS 理论。  
5. NVIDIA PhysX SDK Guide：场景、刚体、CUDA 管理器。

这些材料比本报告更深；建议先跑通 LumenCore 演示，再带着问题去读。

---

返回 [总目录](README.md)。
