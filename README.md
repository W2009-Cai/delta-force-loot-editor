# Delta Force Loot Editor Skill

用于《三角洲行动》PC 录像的自动剪辑 Skill。它可以识别背包、容器搜索、保险箱、房卡拾取/使用、技能、高价值物资、撤离和结算画面，并为唠嗑跑刀视频保留必要的对话与路线上下文。

默认交付包括完整候选事件、人工审核页面、剪映交接素材和可选的 1080p 粗剪。视觉检测只负责提出候选；容器子类、对话边界、路线意义和物品实际价值仍需要人工复核。

## 包含内容

- `SKILL.md`：Codex Skill 工作流与行为约束
- `scripts/`：扫描、事件检测、时间线构建和视频渲染脚本
- `references/`：UI 标定、事件分类、唠嗑剪辑和时间线规则
- `assets/templates/`：模板、ROI、阈值和事件上下文配置
- `tests/`：检测、扫描、时间线和渲染测试
- `agents/openai.yaml`：代理展示配置

仓库不包含原始录像、成片、抽帧、历史运行输出或虚拟环境。自带模板只针对初始 1280×720 中文 PC 样本；不同分辨率、HUD、干员或游戏版本需要重新标定。

## 安装

克隆公开仓库：

```bash
git clone https://github.com/W2009-Cai/delta-force-loot-editor.git
cd delta-force-loot-editor
```

将仓库目录复制或链接到 `~/.codex/skills/delta-force-loot-editor`，然后创建 Python 虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

还需要确保 `ffmpeg` 和 `ffprobe` 可用。实际处理录像前，按 `SKILL.md` 使用目标 UI 截图重新标定模板与 ROI。

## 基础流程

```bash
python scripts/scan_video.py input.mp4 --output-dir output
python scripts/build_timeline.py output/events.json \
  --video-info output/video_info.json \
  --output-dir output
python scripts/render_video.py input.mp4 \
  --timeline output/timeline.json \
  --output-dir output \
  --timeline-clips-only
```

查看 `output/review_uncertain.html` 复核不确定候选。完整候选始终保留在 `events.json`；人工排除和补充应写入 overrides 或审核时间线，不要覆盖检测证据。
