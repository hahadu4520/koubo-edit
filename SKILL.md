---
name: koubo-edit
description: 口播视频剪辑流水线：粗剪（去停顿/口误/重复）、限流词哔声+字幕打码、整条字幕（可中英双语）、花字、清单列表、3:4 封面。当用户说“剪口播”“粗剪这个视频”“加花字/清单/字幕”“做封面”，或给出一个口播原片（如 *_raw.MP4）时使用。
---

# 口播剪辑流水线

所有每期要判断的内容都写在 `<workdir>/config.json`，脚本只读配置。样板：`config.example.json`（11225《除了 A 股以外都有》的完整配置）、`en.example.json`（对应英文字幕）。

下面的 `<SKILL>` 指这个 SKILL.md 所在的目录（Claude Code、Codex 等 Agent 都可能把它装在 `~/.claude/skills/koubo-edit`、`~/.codex/skills/koubo-edit` 或 `~/.agents/skills/koubo-edit`，这几个位置是同一份）。

```
macOS:    python3 <SKILL>/scripts/koubo.py <命令> <workdir> ...
Windows:  python  <SKILL>\scripts\koubo.py <命令> <workdir> ...
workdir:  ~/Downloads/<id>_work      # 每期一个工作目录，config.json 放这里
```

用任何 python 启动都行，脚本会自动切换到技能自带的 venv。下文写成 `koubo <命令>`。

依赖：ffmpeg 和技能自带的 venv。如果 `<SKILL>/venv` 不存在，先让用户安装：macOS 运行 `bash <SKILL>/install.sh`，Windows 运行 `powershell -ExecutionPolicy Bypass -File <SKILL>\install.ps1`。

- **语音转写**：Apple 芯片 Mac 用 mlx-whisper，其他电脑（Windows、Intel Mac）用 faster-whisper，脚本会自动选择。Windows 没有 NVIDIA 显卡时，转写会比较慢，一条 6 分钟的视频大约要 5 到 15 分钟。
- **视频编码**：Mac 用 VideoToolbox，NVIDIA 显卡用 NVENC，其他情况用 libx264，也是自动选择。
- **字体**：字幕在 Mac 上用冬青黑体，在 Windows 上用微软雅黑 Bold；得意黑、Noto Serif CJK Black、马善政都在 `<SKILL>/fonts/` 里。
- **防休眠**：长任务前，Mac 上先运行 `caffeinate`；Windows 上提醒用户把电源设置改成“不睡眠”。

## 步骤（每步做完先给用户看，再往下）

1. **建工作目录**：建好 `<workdir>`，写 config.json，先只填 `src`、`id`。
2. **粗剪**：`koubo roughcut <workdir>`。它会转写原片，生成 `raw_transcript.txt`。读一遍，把口误、重复、卡顿的句子写进 `manual_cuts`（原片时间轴，[开始, 结束, 原因]）。剪点要落在能量低谷：用 `--dry` 只出计划不渲染，确认后再正式跑。输出 `<id>_粗剪.mp4` 和 `roughcut_report.md`。告诉用户剪掉了什么。
3. **字幕断句**：`koubo cues <workdir>`，生成 `cues.txt`。检查识别错字，写进 `fix`（[错, 对]）；被拆开的词写进 `jieba_words`。重复跑到字幕干净为止。口播内容本身说错的地方（比如说成“三道”，其实讲了四道）要告诉用户，不要自作主张改。
4. **限流词**：在 cues 里找敏感词（私募+起投金额、诱导开户、对制度的负面评价、造假等）。用 `find` 拿时间，再用 RMS 能量曲线把边界对准，写进 `beeps`（粗剪时间轴，[开始, 结束, "词的字"]）。核心论点里的词（比如“制度差”）列给用户定，不要默认哔掉。然后跑 `koubo beep <workdir>`，再转写哔声段落，确认词听不出来、前后的字没被吃掉。
5. **花字和清单**：写 `highlights`（[时间, 词, 样式]）和 `lists`（items、每条出现时间 reveal、消失时间 end）。每分钟大约 4 到 5 处花字。样式：A 黄色重点、B 红色警示、C1/C2 黄蓝对比、H 放大（开场、核心数字、结尾金句）。跑 `koubo preview <workdir> t1 t2 ...`，**先把关键帧发给用户确认**，用户要求关键帧一做好就发。
6. **英文字幕（需要时）**：按 cues.txt 逐行翻译，写成 `en.json`（行数必须等于 cue 数）。专有名词统一译法；要打码的词用 `[[ ]]` 包起来。用 `preview ... --en` 看效果。
7. **烧录**：`koubo burn <workdir> [--en]`，输出 `<id>_成片.mp4` / `<id>_成片_双语.mp4`。抽几帧检查同步。
8. **封面**：先挑帧，再跑 `koubo cover <workdir>`。在 `cover.frames` 里填时间 t、脸中心 cx、眼睛高度 eye、裁切宽度 cw 和版式 layout（stack / brush / stagger）。

## 样式规范（剪辑者已经确认过）

- 字幕：冬青黑体 W6，白字黑边，在画面 76% 高度；出清单时下移到 87.5%。每行不超过 14 字，按词断行，不拆词。
- 清单：得意黑 76px，①②③ 黄色，讲到哪条出哪条。
- 封面风格（参考小红书知识博主封面）：粗宋体或毛笔大字，白字加柔和阴影，**不能像字幕**；字要端正、横排，不倾斜，不用夸张卡通字。
- 封面挑帧：**先挑有笑容、脸居中的帧**，再挪字的位置，不要为了留白挑帧；字可以压到头发，**不能压五官**；**放大检查镜片，有反光就不用**。
- 做 3 版给用户挑。
