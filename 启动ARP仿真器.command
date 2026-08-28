#!/bin/zsh

set -e
PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
    echo "未找到项目虚拟环境 .venv。"
    echo "请先按照 README.md 中的环境准备步骤安装依赖。"
    read -r "?按回车键关闭窗口..."
    exit 1
fi

exec .venv/bin/python main.py
