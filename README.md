# 喵喵咕咯精灵 · CGmiaomiao

一套把 AI 生成的 3D 小猫精灵（**喵喵咕咯精灵**）做成**绑骨、带动画的 GLB**，再放进一个 **AR 网页 App** 的工程。正在重构成 **AR 为主的视觉小说桌宠**（电脑摄像头 + 图像标记真 AR + galgame 对话/剧情系统）。

> 名字固定写法是 **喵喵咕咯精灵**（不是"咕咕"也不是"骨咯"）。

## 两半

- **Blender 流水线（本仓库）**：headless 脚本，绑骨 → 做动画 → 导出 GLB / USDZ / 可打印 STL。
- **网页 App（`ar/`，独立仓库 `cgmiaomiao-ar`）**：model-viewer/three.js 显示小猫，Cloudflare Worker 提供聊天/语音。本仓库 `.gitignore` 忽略 `ar/`。

## 常用命令

Blender 在 `D:\Program Files\Blender Foundation\Blender 5.0\blender.exe`。

```sh
# 1. 绑骨：导入 PBR GLB、改腿、建骨架、蒙皮、存 .blend
blender --background --python rig_pipeline_v2.py

# 2. 做动画 + 导出：22 个动作 → 渲染校验帧 → 导出 character_v2.glb（自动拷进 ar/）
blender --background --python animate_v2.py

# 2b. (iOS) 刷新 Quick-Look 用的 usdz
blender --background --python export_usd_v2.py

# 2c. (3D 打印) 水密 STL（FDM + 树脂）和全彩 OBJ/GLB
blender --background --python export_print_v2.py
blender --background --python export_print_color_v2.py

# 3. 本地跑网页（model-viewer 需要 http 源）
cd ar && python -m http.server 8765
```

详细架构与坑见 `CLAUDE.md`。

## 文档

- `docs/计划.md` —— 当前重构的完整计划（P0–P6）。
- `docs/进度.md` —— 进度本子（接力用：新会话先读它 + `git log`）。
- `CLAUDE.md` —— 给 AI 协作者的项目说明与踩坑记录。

## 生成物（不入库，按需重建）

`verify/`（校验渲染图）、`print/` 里的 `.stl/.obj/.glb/.png`（打印产物）、`_archive/`（归档的旧文件/实验）都不进 git，可由脚本重新生成或在本地保留。
