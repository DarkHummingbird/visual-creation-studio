# 新版 Demo 的第三方复用记录

## 直接复用并修改的源码

| 来源 | 固定提交 | 实际使用位置 | 修改 |
| --- | --- | --- | --- |
| [palxiao/poster-design，mit-version](https://github.com/palxiao/poster-design/tree/mit-version) | e6749f6781915ae6fafe5ee5819eeac3a1833827 | frontend/src/pagePresets.ts | 移除图标，供尺寸选择使用；MIT |
| [wzj177/ecommerce-image-suite](https://github.com/wzj177/ecommerce-image-suite) | 2d508bd990df0397026406f210a5915b2c955469 | app/scene_presets.py | 仅提取纯场景映射函数，用于商品场景提示词；Apache-2.0 |
| [64johnlee/qwen-showrunner](https://github.com/64johnlee/qwen-showrunner) | c91b03acc6e02b2fdc38e7d350e870ee809c258b | app/concat_media.py | 提取标准化片段的合并与转码回退，增加超时、路径检查、清理和faststart；MIT |

原许可证随对应目录保留。未引入上游的关闭TLS校验、并发生成、固定单主角或独立配音逻辑。

## 本次另外检查的仓库

- coolqoo/1click-ecom-detailpage：主要是商品详情页Skill，不是两个场景共用的持久化工作台；未复制代码。
- LingGuoAI/LingGuo-Drama：README说明MIT；Go/Gin、Vue、MySQL、Redis体系，流程接近，但整体接入会改变当前单机Python方案；未复制代码。
- yuebuluo168/--demo：需要后端、前端与SQL配套，未采用整套项目。
- liangdabiao/Fashion-AI：包含检索、Milvus与服装宣传图流程，与当前通用款式绑定任务有差异，未采用。
- LYL-TUST/AIGC-Short-Drama-Workbench（82eeb054e761c7e1a3c89e69e3b22ec7e6dff1eb）：主要为大纲、分镜和提示词，不能直接替代真实图像视频执行器；未复制代码。
- swimmingkiim/react-image-editor：React画布项目，整套界面包含额外工具，本版直接使用其同类底层react-konva完成必要图层能力；未复制该项目代码。

## 包依赖复用

React、react-konva/Konva、Dexie、FastAPI、Pydantic、python-docx、pypdf、Pillow和系统FFmpeg/ffprobe分别承担网页、画布、暂存、接口、校验、文档解析与媒体处理。具体版本见requirements.txt及frontend/package-lock.json。项目并非从零实现这些底层能力。
