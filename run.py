#!/usr/bin/env python3
"""运行脚本 - 方便直接运行爬虫"""

import sys
from pathlib import Path
import argparse
# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.main import main

parser = argparse.ArgumentParser(description='Org Crawler')
parser.add_argument('-c', '--continuous', action='store_true', help='持续运行模式')
parser.add_argument('-r', '--repair', action='store_true', help='修复模式')
args = parser.parse_args()

if __name__ == "__main__":
    # print("Starting crawler...")
    main(continuous=args.continuous, repair=args.repair)

