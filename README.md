# Delta Force Loot Editor Skill

用于《三角洲行动》PC 录像的自动高光剪辑 Skill。它识别背包、容器、保险箱、物资详情、高价值物资、撤离成功和结算画面，生成可审计事件记录、剪映交接文件及可选的 1080p 成片。

## 包含内容

- `SKILL.md`：Codex Skill 工作流与行为约束
- `scripts/`：扫描、事件检测、时间线构建和视频渲染脚本
- `references/`：UI 标定和剪辑规则
- `assets/templates/manifest.json`：模板与 ROI 配置结构
- `tests/`：检测、扫描、时间线和渲染测试
- `agents/openai.yaml`：代理展示配置

仓库不包含原始录像、成片、抽帧、历史运行输出、虚拟环境或用户专用模板图片。

## 在 macOS Codex 中继续

克隆此私人仓库后，将仓库目录复制或链接到 `~/.codex/skills/delta-force-loot-editor`，然后创建 Python 虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

还需要确保 `ffmpeg` 和 `ffprobe` 可用。实际处理录像前，按 `SKILL.md` 使用目标 UI 截图重新标定模板与 ROI。
