#!/bin/bash
# 口播剪辑技能一键安装（macOS / Linux）：bash install.sh
# Windows 请用 install.ps1
set -e
cd "$(dirname "$0")"
SRC="$(pwd)"
NAME="koubo-edit"

# 技能放在哪：如果已经在某个 skills 目录里（比如 git clone 到 ~/.claude/skills/koubo-edit），就地安装；否则复制到 ~/.claude/skills/
case "$SRC" in
  */skills/$NAME) DEST="$SRC" ;;
  *) DEST="$HOME/.claude/skills/$NAME" ;;
esac

if [ "$(uname -s)" = "Darwin" ] && ! command -v brew >/dev/null 2>&1; then
  echo "❌ 没找到 Homebrew。先在终端运行下面这行装好，再重新运行本脚本："
  echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'; exit 1
fi

echo "① 检查 ffmpeg 和 Python …"
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then brew install ffmpeg
  else echo "❌ 请先安装 ffmpeg（例如 sudo apt install ffmpeg）"; exit 1; fi
fi
if ! command -v python3 >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then brew install python
  else echo "❌ 请先安装 Python 3.10 或更新版本"; exit 1; fi
fi

if [ "$SRC" != "$DEST" ]; then
  echo "② 复制技能到 $DEST …"
  mkdir -p "$DEST"
  cp -R SKILL.md AGENTS.md README.md install.sh install.ps1 config.example.json en.example.json scripts fonts "$DEST/"
fi

# 语音转写：Apple 芯片 Mac 用 mlx-whisper（快），其他电脑用 faster-whisper
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then ASR=mlx-whisper; ASR_MOD=mlx_whisper
else ASR=faster-whisper; ASR_MOD=faster_whisper; fi

echo "③ 创建独立的 Python 环境，安装 pillow、jieba、$ASR …"
python3 -m venv "$DEST/venv"
PIP="$DEST/venv/bin/pip"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
# 国内网络连 pypi.org 常常很慢：先试官方源，失败就自动换清华镜像
$PIP install -q --timeout 30 pillow jieba $ASR || $PIP install -q --timeout 60 -i "$MIRROR" pillow jieba $ASR

echo "④ 预先下载转写模型（约 1.6GB，只需要一次）…"
if [ "$ASR" = "mlx-whisper" ]; then MODEL=mlx-community/whisper-large-v3-turbo; else MODEL=mobiuslabsgmbh/faster-whisper-large-v3-turbo; fi
DL="from huggingface_hub import snapshot_download; snapshot_download('$MODEL')"
"$DEST/venv/bin/python" -c "$DL" || HF_ENDPOINT=https://hf-mirror.com "$DEST/venv/bin/python" -c "$DL" \
  || echo "⚠️  模型下载失败，第一次剪辑时会自动重试下载。"

echo "⑤ 让 Claude Code、Codex 和其他 Agent 都能找到这个技能 …"
for dir in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
  mkdir -p "$dir"
  if [ "$dir/$NAME" != "$DEST" ] && [ ! -e "$dir/$NAME" ]; then ln -s "$DEST" "$dir/$NAME" && echo "   已链接 $dir/$NAME"; fi
done

echo "⑥ 自检 …"
"$DEST/venv/bin/python" -c "import PIL, jieba, $ASR_MOD" && ffmpeg -version >/dev/null && \
  echo "✅ 安装完成。打开 Claude Code 或 Codex，说“剪口播 ~/Downloads/xxx_raw.MP4”就能开始。"
