# AGENTS.md

这个仓库是一个口播视频剪辑技能，任何编程 Agent 都可以使用，包括 Claude Code、Codex、Cursor、Gemini CLI 等。

- **流程和样式规范**：完整写在 [SKILL.md](SKILL.md)。用户说“剪口播”“粗剪这个视频”“加花字/清单/字幕”“做封面”，或者给出一个口播原片（如 `*_raw.MP4`）时，先读 SKILL.md，再照着做。
- **所有操作**：都通过 `python scripts/koubo.py <命令> <workdir>` 完成，macOS 和 Windows 通用。脚本会自动切换到技能自带的 venv。
- **还没安装时**（技能目录下没有 `venv/`）：先让用户安装。macOS 运行 `bash install.sh`；Windows 运行 `powershell -ExecutionPolicy Bypass -File install.ps1`。
- **每一步做完都先给用户看，再往下**：粗剪结果、限流词清单、花字关键帧、封面，都要等用户确认。

修改代码时：`scripts/koubo.py` 放流水线，`scripts/style.py` 放花字和清单样式。`config.example.json` 是一期完整配置的样板。
