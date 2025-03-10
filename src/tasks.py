#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
异步任务管理模块

该模块提供异步任务的管理功能，包括：
- 任务队列管理
- 并发控制
- 任务状态跟踪
- 结果获取和错误处理

Author: Samueli924
Date: 2025-03
License: MIT
Version: 1.0.0
"""

import asyncio
from typing import Optional, Any, Callable
from dataclasses import dataclass
from src.logging import LOGGER

@dataclass
class Task:
    """任务数据类"""
    func: Callable  # 要执行的函数
    args: tuple     # 位置参数
    kwargs: dict    # 关键字参数
    result: Optional[Any] = None  # 任务结果
    error: Optional[Exception] = None  # 任务错误
    completed: bool = False  # 任务是否完成

class TaskManager:
    def __init__(self, max_workers: int = 15):
        """
        初始化任务管理器
        
        Args:
            max_workers: 最大并发任务数
        """
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        self.tasks = {}
        self._task_counter = 0
        self.loop = asyncio.get_event_loop()
        LOGGER.info(f"任务管理器初始化完成，最大并行数: {max_workers}")
        
    async def _execute_task(self, task_id: int, task: Task):
        """执行单个任务"""
        async with self.semaphore:
            LOGGER.info(f"开始执行任务 {task_id}")
            # try:
            if asyncio.iscoroutinefunction(task.func):
                result = await task.func(*task.args, **task.kwargs)
            else:
                # 如果不是协程函数，在线程池中执行
                result = await self.loop.run_in_executor(
                    None, task.func, *task.args, **task.kwargs
                )
            task.result = result
            task.completed = True
            LOGGER.info(f"完成任务 {task_id}")
            # except Exception as e:
            #     LOGGER.error(f"任务 {task_id} 执行出错: {str(e)}")
            #     task.error = e
            # finally:
            #     task.completed = True
            #     LOGGER.info(f"完成任务 {task_id}")
    
    async def submit(self, func: Callable, *args, **kwargs) -> int:
        """
        提交任务到队列
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            task_id: 任务ID
        """
        task_id = self._task_counter
        self._task_counter += 1
        
        task = Task(func=func, args=args, kwargs=kwargs)
        self.tasks[task_id] = task
        
        # 创建异步任务并立即执行
        asyncio.create_task(self._execute_task(task_id, task))
        LOGGER.info(f"提交任务 {task_id} 到队列")
        return task_id
        
    async def get_result(self, task_id: int, timeout: Optional[float] = None) -> Optional[Task]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            
        Returns:
            Task对象或None（如果超时）
        """
        if task_id not in self.tasks:
            return None
            
        task = self.tasks[task_id]
        start_time = self.loop.time()
        
        while not task.completed:
            if timeout and (self.loop.time() - start_time) > timeout:
                return None
            await asyncio.sleep(0.1)
            
        return task
