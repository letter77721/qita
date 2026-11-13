# NotePilot Lite

面向大学生的 AI 主动学习与自适应复习智能体。保留 Expo / React Native 手机界面、FastAPI、公网部署与 SQLite；删除相机、图像裁剪、图片 OCR 和视觉调用。

四个页面：首页、AI练习、错题本、我的。公网界面免登录使用，通过签名 HttpOnly Cookie 为每个浏览器分配独立 SQLite 空间。旧个人空间和管理接口继续由原口令保护。

## 学习闭环

新建目标并粘贴教材文字 → Planner 按到期日推荐 → 文本模型 Tutor 出题/提示 → 用户作答 → 文本模型 Evaluator 结构化错因与追问 → Scheduler 更新任务 → 可保存、编辑、删除错题。

模型结果通过严格 Pydantic JSON Schema 校验。引用必须逐字来自资料；无依据、不确定或引用不匹配，不计为正确样本。最近五次有效回答估计近期表现，连续正确三次才延长间隔，不宣称一次答对即完全掌握。旧问题保存资料快照；重复提交同一题不会增加练习次数。

PDF/TXT/MD 上传、逐页文字浏览与校正、历史原件预览、课程与考试日期、导出数据仍可用。新图片上传拒绝，扫描页改为手工输入文字。旧表和上传原件不删除；新增 lite_* 表。

## 配置与启动

```
TEXT_BASE_URL=https://open.bigmodel.cn/api/paas/v4
TEXT_MODEL=glm-4.7-flash
TEXT_API_KEY=在后端配置真实智谱密钥
NOTEPILOT_TOKEN=个人空间口令
```

兼容已部署的 VISION_API_KEY 作为文本密钥回退，只复用凭据，不发送图片、不调用视觉模型。无模型输出时显示错误，不以模板冒充执行结果。不自动切换其他付费模型。

```powershell
python -m pip install -r requirements.txt
cd mobile
pnpm install --frozen-lockfile
pnpm build:web
cd ..
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8501
```

Render 的 Dockerfile 构建同一前端与 API，健康检查 `/api/health`。免费实例的磁盘仍非持久化；更新前必须备份数据，有用户原件时需先完成持久化安排，不能因代码迁移未删表就声称云端数据一定不会丢失。

## 验证

`python -m pytest -q`；`pnpm build:web`。受保护的 `POST /api/lite/model-check` 使用明确的合成教材文字验证真实 Tutor/Evaluator，不保存为用户练习记录或学习统计。

测试、构建、真实模型调用与手机真机交互是不同层次；没有真实设备测试时，不宣称真机通过。详细范围见 docs/Lite重构计划.md。其余旧 docs 为历史版本记录。

匿名入口为 /api/open/*，不提供管理员模型检查或认证接口。模型调用每网络每小时30次、全站每日200次（单进程计数，重启重置）；资料每空间20份、总计40 MB。请允许 Cookie、及时导出，免费部署仍不能保证跨发布持久化。

## 切换 DeepSeek

在 Render → Environment 添加以下配置并保存部署，原有 TEXT_* 不必删除；DEEPSEEK_API_KEY 存在时优先使用该配置：

```
DEEPSEEK_API_KEY=仅在 Render 填写新密钥
DEEPSEEK_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-flash
```

DeepSeek 官方 API 按量计费；不自动切换供应商。当前官方模型名称见 https://api-docs.deepseek.com/ ，旧 deepseek-chat 已停用。保持 JSON Schema 校验、证据核对和失败不记学习记录；不把旧智谱密钥发给 DeepSeek。密钥不写入源码或前端。删除 DEEPSEEK_API_KEY 可回退原 TEXT_* 配置。
