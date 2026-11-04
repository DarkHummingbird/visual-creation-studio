# 视觉创作工作台 Demo

电脑浏览器中的本地单用户创作工作台。两个入口：商品图、短剧；各自拥有独立草稿箱，共用素材库。无需本地大模型。

## 快速开始（克隆后从零运行）

环境要求：**Python 3.12+、Node 22+、FFmpeg（含 ffprobe）**。macOS 用 `brew install ffmpeg` 安装；Windows 需把 ffmpeg 加入 PATH。

```bash
git clone <仓库地址> && cd <仓库目录>
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
cp .env.example .env   # 然后填入自己的 API Key，见下节「模型配置」
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器访问 http://127.0.0.1:8765 。服务仅监听本机，无登录体系，适合个人单机使用。Python 依赖与 npm 依赖版本均已锁定，无需额外部署数据库（SQLite 随首次运行自动创建）。

macOS 用户配置好后也可以直接双击 `启动.command`（zsh 脚本，仅适用于 macOS）。

## 模型配置

根目录`.env`保存密钥（已被 `.gitignore` 排除，不会进入版本库），参数名称见`.env.example`。密钥只在本地服务读取，不进入浏览器。

| 用途 | 变量 | 默认模型 | 说明 |
| --- | --- | --- | --- |
| 文字 | `DEEPSEEK_API_KEY`（+可选 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`） | `deepseek-flash` | 剧本、参考卡、分镜分析 |
| 图片 | `DASHSCOPE_API_KEY` | `qwen-image-3.0` | 文生图、参考改图，最多3张参考 |
| 视频 | `DASHSCOPE_API_KEY`（同一变量） | `wan3.0-video-prime` | 首帧生视频，显式有声/无声，画幅跟随设置 |

图片与视频走 DashScope 兼容协议，默认接入地址 `DASHSCOPE_BASE_URL=https://cn-beijing.maas.qianwenaiapi.com/api/v1`。

**切换到自己的阿里云百炼账号**：在阿里云百炼控制台创建 API Key 后，把 `DASHSCOPE_BASE_URL` 改为控制台给出的业务空间 API Host（形如 `https://<WorkspaceId>.cn-beijing.maas.aliyuncs.com/api/v1`，[官方文档](https://help.aliyun.com/zh/model-studio/first-api-call-to-qwen)）。注意各地域、各业务空间的 Key 不通用，账号内需开通 `qwen-image-3.0` 与 `wan3.0-video-prime` 的调用权限，否则生成会返回模型不可用。

**注意**：本项目默认接入地址虽然使用阿里云百炼的接口协议，但域名归属请以你获取 Key 的渠道说明为准；更换端点后请先用小批量生成验证连通性（`scripts/check_model_connectivity.py`）。

点击生成会弹出本次付费调用确认。实际费用功能未实现：`GET /api/v1/costs`返回`actual:null`、`NOT_IMPLEMENTED`，扩展点位于`app/costs.py`；应用不提供实际费用上限控制或账单对账。单份制作按顺序执行，不提供跨任务并发。

## 商品图流程

1. 新建商品图草稿，填写商品名称、已知资料，添加款式并分别绑定照片。
2. 在制作清单选择款式、展示图/场景图和每款数量；单批最多20张。
3. 生成后切到“检查与采用”，逐张与原图对照并采用，可只重做一张。
4. 加入画布，添加文字、图片或色块，拖动、等比缩放、旋转、调整图层顺序、锁定、撤销重做；局部改图生成候选后只替换该图片层。
5. 从尺寸预设选新尺寸并检查排版，分别导出PNG；“导出”页可以打包当前成品、素材和创作记录。
6. “检查与采用”下方可对当前草稿已采用的商品图批量改风格；原图与旧候选保留。

## 短剧流程

1. 导入故事或已有剧本：粘贴文字、TXT、MD、DOCX、PDF。只读文字，不识图；文件最多20MB、正文最多200,000字符。PDF文字顺序需人工核对，缺页或超限会显示提示。超过5,000字符的粘贴正文自动保存为TXT素材。
2. 逐步制作：整理剧本 → 检查人物/场景/道具卡 → 生成并采用参考 → 镜头清单 → 画面 → 视频 → 合成。镜头数量可编辑，不固定四镜。每镜最多3张参考，包含人物、场景和道具。
3. 同一人物换衣服可以“添加新造型”，保留人物身份ID。声音描述用于提示，不保证严格锁定音色。
4. 一键成片：正文确认完整后到“一键成片”，选择风格、比例、声音、清晰度，以及最多镜头与自动参考数量，确认后执行；已有有效阶段会复用。超范围或分析有歧义时暂停，分析结果全部保留；在剧本页核对并清除警告后，可点“继续”从暂停处接着一键完成，无需转逐步模式。
5. 逐步模式需采用每项候选，再进入下一阶段；一键模式自动采用只表示文件与流程检查通过，仍需人检查剧情、身份、动作和声音。
6. 只重做某镜头后，采用新视频再重新合成，其他视频与旧成片均保留。上游改变会提示复查，未确认前阻止完整合成。

## 自动保存与失败恢复

编辑停止约1.8秒后自动保存；切步骤和开始生成前立即保存。浏览器IndexedDB保留未落盘修改，保存冲突不覆盖，重新打开可恢复本地内容或另存副本。

后台运行不依赖浏览器在线。暂停只停止后续提交，已提交的视频继续查询和下载。服务重启后制作暂停；继续时查询原视频任务、复用已返回响应恢复文件，不自动重新生成。无远端编号的结果不明请求禁止自动续发；核对后从对应页面显式新建生成尝试。

本地数据位于`data/studio-v1.sqlite3`和`data/files/`。原文、候选与成品均保留；删除草稿只做逻辑删除，不物理删除共享文件。复制草稿引用同一底层素材，编辑内容独立。

## 验证与边界

```bash
.venv/bin/python -m pytest -q tests
npm --prefix frontend run build
```

模型固定输出结构在`app/schemas.py`，可通过`/api/v1/contracts`读取。测试使用隔离临时数据库与替身模型验证完整执行、去重、异常和恢复，不把测试替身当成真实模型评测。

没有多用户、手机适配、专业时间线、OCR、独立配音或真实费用结算。长文分段能记录正文覆盖范围，但覆盖完整不等于所有剧情语义都无损；生成内容须检查。模型支持的参数组合与实际效果独立验证。

第三方直接复用代码及固定版本见`third_party/README.md`，许可证已保留。旧版应用入口已删除；唯一入口是`app.main:app`。
