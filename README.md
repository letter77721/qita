# NotePilot 2.0

理工科学生的证据学习伴侣。Expo / React Native 手机端，FastAPI 后端，同一份界面可导出 Web 在电脑浏览器演示。浅米白、深蓝、薄荷绿，五个底部入口：首页、笔记、拍摄、AI学习、我的。

## 立即使用

本机已经安装依赖并构建 Web，在项目目录执行：

```powershell
cd 'D:\Zzm\其他\智能体\NotePilot'
.\start.ps1
```

打开 <http://127.0.0.1:8501>。重启后可从笔记页进入已有课程，资料与记录不会丢失。`演示 · 流体力学（合成资料）` 是独立的合成示例课程，不是真实使用统计。

新环境：Python 3.11+、Node 20.19+、pnpm 10+（或 npm）。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd mobile
pnpm install --frozen-lockfile
pnpm build:web
cd ..
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8501
```

本机运行时使用 `.packages` 中补齐的 Python 依赖，`start.ps1` 自动加入路径。为兼容本机已有 PyArrow 使用原有 NumPy 1.x，没有修改全局包。重新安装推荐使用独立虚拟环境。

## 手机测试

工程锁定 **Expo SDK 54 / React Native 0.81.5**，已提供 pnpm 锁文件。开发时在 `mobile` 执行 `pnpm start`。Expo Go 必须匹配 SDK 54；若设备当前版本不支持，请使用该 SDK 的开发构建，不要直接混装新版 Expo 包。Android 原生开发构建需要 Android Studio / SDK：`pnpm android`；iOS 原生构建需要 macOS / Xcode：`pnpm ios`。

后端通过 `./start.ps1 -Lan` 在局域网监听；手机与电脑应在同一网络，在「我的」输入电脑局域网地址，例如 `http://192.168.1.5:8501`。可在 `.env` 设置 `NOTEPILOT_TOKEN`，手机填写同一访问口令。当前为单用户应用，不提供多租户隔离，不应部署公网。

浏览器相机需要安全上下文（localhost 或 HTTPS），普通手机局域网 HTTP 可能不允许使用相机；手机拍摄建议使用原生 Expo 开发构建。后端本机默认只监听 localhost，不自动调整防火墙。

## 已实现的闭环

1. 新建课程，拍摄 / 预览 / 重拍 / 四边比例裁剪，或导入 PDF、图片、UTF-8 文本。裁剪需点击应用；保存时使用当前预览图。原件保留于后端。
2. 后台线程池处理，SQLite 持久化任务阶段、成功或失败状态。客户端轮询真实状态。服务重启时未完成任务标记中断，可手动重试。当前仅支持单后端进程（不要启用多个 uvicorn workers），不是分布式队列。
3. PDF 保留真实页码，文本层自动提取。勾选授权且后端配置视觉接口时，识别图片与扫描页。未配置时显示待识别，可手动录入。
4. 跨资料知识诊断，区分条件不同、片段条件缺失、同条件相反措辞及识别不确定。每个问题可回到真实原页并记录复核。源文本校正会使旧复核失效。
5. SymPy 对受限显式代数表达式做等价核验。只支持名称、有限数字、加减乘除和小整数幂，不执行用户公式代码；不能比较不同符号定义、隐式乘法、任意 LaTeX 或复杂推导。发现不等价也只是核实线索。
6. 基于上传原文生成主动回忆问题，先作答、后展示原文、自评；两次能回忆后加深到前提核查。没有资料不会生成固定演示问答，开放回答不由规则自动评分。
7. 近期五次自评、未复核线索、考试日期共同影响复习顺序与日期。自评并非客观理解程度评估。
8. 课程隔离、关键词检索、原页校正、资料删除确认、数据 JSON 导出、可选访问口令。连接口令只保留在当前会话；模型密钥只在后端。

## 模型设置

复制 `.env.example` 为 `.env`，填写 `VISION_BASE_URL`、`VISION_API_KEY`、`VISION_MODEL`。BASE_URL 是支持图像的兼容接口根路径，程序追加 `/chat/completions`。相应服务会收到已获用户勾选授权的页面。图像转录结果标为未核验。不要把 `.env` 提交到仓库。

## 文件结构与备份

```
mobile/       Expo 源码、配置、锁文件；dist 是有效 Web 发布产物
backend/      API、持久化任务与学习调度
agents/       解析、知识组织、诊断、复习基础逻辑
services/     视觉识别、检索、受限公式核验
database/     SQLite 存储与旧版数据迁移
workflows/    LangGraph 组织和诊断工作流
data/         数据库、上传原件、明确标注的示例
tests/        后端闭环、课程隔离、权限、公式和 PDF 测试
```

备份时同时复制 `data/notepilot.db` 和 `data/uploads`。旧版 `attempts` 表保留供导出；新版反馈使用按课程隔离的 `practice` 表。旧资料自动归入流体力学课程。

## 验证与边界

```powershell
python -m pytest -q
cd mobile
pnpm build:web
# 原生 JS/Hermes 打包检查，不等同 APK 或真机测试
pnpm exec expo export --platform android --output-dir .native-check
```

已验证 API 上传→解析→诊断→原页→校正→复核→自评→追问加深，以及 Web UI 导入与资料浏览。Web、Android JS/Hermes 构建通过。尚未生成安装 APK、未进行 Android/iOS 真机相机测试；没有真实手写材料和模型凭据，OCR 效果尚未评估。

本版本的知识组织仍为预设概念和关键词匹配，诊断比较同一行片段，可能漏报或误报。尚未实现语义向量检索、通用 LLM 推理、自由问答、跨课程知识迁移、录音、批注、推送、离线同步、自动文档边缘检测或透视校正；这些不能作为已完成能力演示。原生的裁剪功能为手动比例裁剪。

API 参考：[Expo Camera](https://docs.expo.dev/versions/v54.0.0/sdk/camera/)、[ImageManipulator](https://docs.expo.dev/versions/v54.0.0/sdk/imagemanipulator/)、[PyMuPDF](https://pymupdf.readthedocs.io/en/latest/page.html)、[FastAPI](https://fastapi.tiangolo.com/)。
