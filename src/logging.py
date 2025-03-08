#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志管理模块

该模块配置全局日志系统，提供：
- 控制台和文件双重输出
- 日志分级和格式化
- 日志文件轮转
- 异步日志写入

Author: Samueli924
Date: 2025-03
License: MIT
Version: 1.0.0
"""

import sys
from loguru import logger
import os
from datetime import datetime

def setup_logger():
    """
    配置全局日志设置
    
    特点:
    1. 同时输出到控制台和文件
    2. 按日期分割日志文件
    3. 自动删除超过7天的日志
    4. 包含详细的日志格式
    """
    
    # 创建logs目录
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 移除默认的处理器
    logger.remove()
    
    # 日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        format=log_format,
        level="INFO",
        colorize=True
    )
    
    # 添加文件输出
    logger.add(
        os.path.join(log_dir, "{time:YYYY-MM-DD}.log"),
        format=log_format,
        level="DEBUG",
        rotation="00:00",  # 每天零点创建新文件
        retention="7 days",  # 保留7天的日志
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
        enqueue=True  # 异步写入
    )
    
    # 记录程序启动信息
    logger.info("日志系统初始化完成")
    return logger

# 创建全局logger实例
LOGGER = setup_logger()

# 导出logger供其他模块使用
__all__ = ["LOGGER"]
