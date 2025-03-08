#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
装饰器模块

该模块提供各种装饰器，用于：
- 错误重试机制
- 性能监控
- 参数验证
- 异常处理

Author: Samueli924
Date: 2025-03
License: MIT
Version: 1.0.0
"""

import time
from functools import wraps
from typing import Callable, Optional, Any
from src.logging import LOGGER

def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    重试装饰器，用于处理LLM API调用失败的情况
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff_factor: 重试延迟时间的增长因子
        exceptions: 需要重试的异常类型
    
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Optional[Any]:
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if result is None:  # 如果返回None也视为失败
                        raise ValueError("API返回为空")
                    return result
                    
                except exceptions as e:
                    if attempt == max_retries:
                        LOGGER.error(f"函数 {func.__name__} 已达到最大重试次数 {max_retries}，最后一次错误: {str(e)}")
                        return None
                    
                    LOGGER.warning(f"函数 {func.__name__} 第 {attempt + 1} 次调用失败: {str(e)}")
                    LOGGER.info(f"等待 {current_delay:.2f} 秒后重试...")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
            return None
        return wrapper
    return decorator
