#!/bin/bash
# 口播剪辑技能一键安装：bash install.sh
set -e
cd "$(dirname "$0")"
SRC="$(pwd)"
DEST="$HOME/.claude/skills/koubo-edit"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "❌ 需要 Apple 芯片（M1/M2/M3/M4）的 Mac：语音转写用的 mlx-whisper 只能在这类电脑上跑。"; exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
  echo "⚠️  没找到 Claude Code（claude 命令）。技能会照常安装，但要先装好 Claude Code 才能用：https://claude.com/claude-code"
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "❌ 没找到 Homebrew。先在终端运行下面这行装好，再重新运行本脚本："
  echo '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'; exit 1
fi

echo "① 安装 ffmpeg 和 Python …"
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v python3 >/dev/null 2>&1 || brew install python

echo "② 复制技能到 $DEST …"
if [ "$SRC" != "$DEST" ]; then
  mkdir -p "$DEST"
  cp -R SKILL.md README.md install.sh config.example.json en.example.json scripts fonts "$DEST/"
fi

echo "③ 创建独立的 Python 环境，安装 pillow、jieba、mlx-whisper …"
python3 -m venv "$DEST/venv"
PIP="$DEST/venv/bin/pip"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
# 国内网络连 pypi.org 常常很慢：先试官方源，失败就自动换清华镜像
$PIP install -q --timeout 30 pillow jieba mlx-whisper || $PIP install -q --timeout 60 -i "$MIRROR" pillow jieba mlx-whisper

echo "④ 预先下载转写模型（约 1.6GB，只需要一次）…"
"$DEST/venv/bin/python" -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')" \
  || HF_ENDPOINT=https://hf-mirror.com "$DEST/venv/bin/python" -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/whisper-large-v3-turbo')" \
  || echo "⚠️  模型下载失败，第一次剪辑时会自动重试下载。"

echo "⑤ 自检 …"
"$DEST/venv/bin/python" -c "import PIL, jieba, mlx_whisper" && ffmpeg -version >/dev/null && \
  echo "✅ 安装完成。打开 Claude Code，说“剪口播 ~/Downloads/xxx_raw.MP4”就能开始。"
