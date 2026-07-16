# 08 Host 管线与后处理

## 一次 `Renderer::render` 做什么？

入口：`src/host/renderer.cpp` 的 `Renderer::render(scene, camera, config)`。

```mermaid
flowchart LR
  upload[上传网格材质灯HDRI] --> gas[构建或更新GAS]
  gas --> loop[循环optixLaunch]
  loop --> accum[累加缓冲]
  accum --> denoise[可选Denoiser]
  denoise --> tonemap[ACES加gamma]
  tonemap --> png[写PNG]
```

*图：Host 侧从上传到出图。*

### 1. 合并网格 → GAS

场景里多个 `Mesh` 拼成大顶点/索引数组，上传 GPU，构建 **GAS**（Geometry Acceleration Structure）。  
Hitgroup SBT 记录指向 `HitGroupData`（顶点、UV、法线、材质 id）。

### 2. 填 `LaunchParams`

包括：遍历句柄、分辨率、相机基、材质数组、灯光、火焰体积、纹理、背景色、HDRI 指针与 CDF、NEE 开关、最大深度等。见 `src/common/LaunchParams.h`。

### 3. 渐进累加

`spp` 次 launch（或按 `samples_per_launch` 打包）。每次更新 `sample_index`，raygen 把新样本与历史 `accum_buffer` 做递推平均。

### 4. AOV（辅助缓冲）

为 Denoiser 准备 **albedo**、**normal** 引导缓冲（首命中记录）。路径越噪，引导越重要。

### 5. OptiX Denoiser

`optixDenoiserCreate`（HDR 模型）→ `Setup` → `Invoke`。  
输入：嘈杂的 HDR 累加；输出：平滑很多的 HDR 图。

### 6. 色调映射与 PNG

线性 HDR 不能直接当 8-bit 图。本项目用 **ACES** 近似后接 gamma，再经 `stb_image_write` 写 PNG。

## 相机模型

`Camera`：`eye` / `lookat` / `fov` / `aspect`，可选 `aperture` + `focus_dist` 做薄透镜景深（raygen 里对镜头采样）。

## 与 Python 的边界

`lumencore.Renderer().render(...)` 只是薄封装；重活全在 C++/CUDA。  
场景内容（网格、灯、PhysX）在调用前由脚本准备好。

## 小结

- Host：资源上传、GAS、launch 循环、去噪、 tonemap。
- Device：路径积分本身。
- 输出默认是去噪后的展示向 PNG。

下一章：[09 PhysX 集成](09-physx-integration.md)。
