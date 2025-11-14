#!/usr/bin/env python3
"""运行脚本 - 方便直接运行爬虫"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.main import main

if __name__ == "__main__":
    # print("Starting crawler...")
    main()

