#!/bin/bash

PROCESS_NAME="run.py"

# 检查是否提供了 -c 或 --continuous 参数
CONTINUOUS_FLAG=""
if [ "$1" == "-c" ] || [ "$1" == "--continuous" ]; then
    CONTINUOUS_FLAG="-c"
    echo "使用持续运行模式"
else
    echo "使用单次运行模式"
fi

echo "正在查找 $PROCESS_NAME 进程..."
PID=$(pgrep -f "$PROCESS_NAME")

if [ -n "$PID" ]; then
    echo "找到进程: $PID"
    echo "正在终止进程..."
    kill $PID
    sleep 2
    
    # 检查是否成功终止
    if pgrep -f "$PROCESS_NAME" > /dev/null; then
        echo "普通终止失败，尝试强制终止..."
        kill -9 $PID
    fi
    
    echo "$PROCESS_NAME 已终止"
else
    echo "未找到 $PROCESS_NAME 进程"
fi

source ~/code/org_crawler/.venv/bin/activate
python run.py $CONTINUOUS_FLAG &
