# 口播剪辑技能（koubo-edit）

让 Claude Code 帮你剪竖屏口播视频：

- 粗剪：去掉停顿、口误和重复。
- 字幕：生成整条字幕，可以加英文做成中英双语。
- 花字和清单：在关键词上加花字，在要点处加编号清单。
- 限流词：说到敏感词时放“哔”声，字幕里打码。
- 封面：出 3 版 3:4 封面供你挑。

每一步做完都会先给你看，再往下走。

## 电脑要求

- Apple 芯片（M1/M2/M3/M4）的 Mac。Intel Mac 和 Windows 都不行，因为语音转写依赖苹果芯片。
- 已安装 [Claude Code](https://claude.com/claude-code)，并且已经登录。
- 硬盘留出约 3GB 空间，用来放转写模型和 Python 环境。

## 安装（只需一次，约 5 到 10 分钟）

### 方式一：从 GitHub 安装（推荐，以后更新方便）

打开“终端”，粘贴下面这行，按回车：

```bash
git clone https://github.com/hahadu4520/koubo-edit.git ~/.claude/skills/koubo-edit && bash ~/.claude/skills/koubo-edit/install.sh
```

以后更新，只要运行：

```bash
cd ~/.claude/skills/koubo-edit && git pull
```

### 方式二：用压缩包安装

1. 解压收到的 `koubo-edit.zip`。
2. 打开“终端”，输入 `bash `（bash 后面有一个空格），把解压出来的 `install.sh` 拖进终端窗口，然后按回车。
3. 看到“✅ 安装完成”就装好了。

如果提示没找到 Homebrew，按提示先装 Homebrew，再重新运行第 2 步。

## 使用

1. 把口播原片放进“下载”文件夹，比如 `~/Downloads/0101_raw.MP4`。
2. 在下载文件夹里打开 Claude Code，对它说：

   > 剪口播 ~/Downloads/0101_raw.MP4

3. Claude 会依次给你：
   - 粗剪片，附上剪掉了哪些内容
   - 字幕里的错字和可能限流的词，请你确认
   - 花字和清单的关键帧预览
   - 成片，需要时也出中英双语版
   - 3 版封面

   每一步你都可以直接说“这里不要剪”“这个词换红色”之类的话来修改。

成片和封面都放在原片所在的文件夹里。中间文件放在 `~/Downloads/<编号>_work/`，剪完可以删掉。

## 文件说明

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 给 Claude 看的操作手册，包括流程和样式规范 |
| `scripts/koubo.py` | 剪辑脚本：粗剪、字幕、哔声、预览、烧录、封面 |
| `scripts/style.py` | 花字和清单的样式 |
| `config.example.json` | 一期完整配置的样板（11225《除了 A 股以外都有》） |
| `fonts/` | 内置字体：得意黑、思源宋体 Noto Serif CJK、马善政毛笔楷，都是 SIL OFL 开源字体，可免费商用和分发 |

## 更新

从 GitHub 装的，运行 `git pull` 就能更新；用压缩包装的，拿到新版后重新运行一次 `install.sh`。
