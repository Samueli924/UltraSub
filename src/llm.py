#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM翻译模型模块

该模块负责与DeepSeek API的交互，提供：
- 翻译模型的初始化和配置
- 系统提示的生成
- 异步翻译请求的处理
- 参数的环境变量管理

Author: Samueli924
Date: 2025-03
License: MIT
Version: 1.0.0
"""

from openai import AsyncOpenAI
from typing import Optional, List, Dict
from src.logging import LOGGER
from src.decorators import retry_on_failure
from openai.types.chat import ChatCompletionMessage
from src.tasks import TaskManager
import os

def generate_system_prompt(domains: Optional[List[str]] = None) -> str:
    """
    生成系统提示
    
    Args:
        domains: 专业领域列表
        
    Returns:
        格式化的系统提示
    """
    base_prompt = """你是一位专业的视频字幕翻译专家。你的任务是将英文字幕翻译成中文，需要注意以下几点：

1. 你将收到包含上下文的字幕内容，格式为：
   {
     "上文": "前两句字幕内容",
     "当前批次": [
       {"编号": 1, "文本": "第一条字幕内容"},
       {"编号": 2, "文本": "第二条字幕内容"},
       {"编号": 3, "文本": "第三条字幕内容"}
     ],
     "下文": "后两句字幕内容"
   }
   请以JSON格式返回结果：[{"编号": 1, "译文": "中文翻译1"}, {"编号": 2, "译文": "中文翻译2"}, ...]

2. 翻译要求：
   - 准确传达原文含义
   - 符合中文表达习惯
   - 保持对话的连贯性
   - 考虑上下文语境
   - 对于专有名词保持一致性
   - 对于人称代词，根据上下文补充明确的主语"""

    if domains:
        domain_prompt = "\n\n3. 专业领域要求：\n"
        domain_prompt += "这是一个涉及以下领域的内容：" + "、".join(domains) + "\n"
        domain_prompt += "请确保：\n"
        domain_prompt += "- 使用这些领域的专业术语和行业用语\n"
        domain_prompt += "- 保持专业术语的准确性和一致性\n"
        domain_prompt += "- 符合相关领域的表达习惯"
        base_prompt += domain_prompt
    
    output_format = """\n\n输出要求：
- 不要包含任何解释或其他内容
- 不要翻译上下文内容

记住：保持翻译的自然流畅，同时确保与上下文的连贯性。"""

    return base_prompt + output_format

class TranslationModel:
    def __init__(self, _api_key: str, _endpoint: str, domains: Optional[List[str]] = None):
        """
        初始化翻译模型
        
        Args:
            _api_key: API密钥
            _endpoint: API端点URL
            domains: 专业领域列表
        """
        self.client = AsyncOpenAI(api_key=_api_key, base_url=_endpoint, timeout=300)
        
        # 从环境变量读取配置，添加错误处理
        try:
            max_workers = int(os.getenv("MAX_WORKERS", "15").strip())
        except (ValueError, TypeError):
            LOGGER.warning("MAX_WORKERS 环境变量格式无效，使用默认值: 15")
            max_workers = 15
            
        try:
            self.temperature = float(os.getenv("TEMPERATURE", "1.3").strip())
        except (ValueError, TypeError):
            LOGGER.warning("TEMPERATURE 环境变量格式无效，使用默认值: 1.3")
            self.temperature = 1.3
        
        self.task_manager = TaskManager(max_workers=max_workers)
        self.system_prompt = generate_system_prompt(domains)
        self.model = os.getenv("MODEL_NAME", "deepseek-chat")
        
        # 添加tokens统计
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        
        # 记录配置信息
        LOGGER.info(f"OpenAI客户端初始化成功，API端点: {_endpoint}")
        LOGGER.info(f"使用模型: {self.model}")
        LOGGER.info(f"最大并行数: {max_workers}")
        LOGGER.info(f"Temperature: {self.temperature}")
        if domains:
            LOGGER.info(f"设置专业领域: {', '.join(domains)}")
    
    @retry_on_failure(max_retries=5, delay=3.0, backoff_factor=2.0)
    async def chat_completion(self, messages: list, model: Optional[str] = None) -> tuple[Optional[str], Optional[str], Optional[Dict]]:
        """
        发送聊天请求到LLM
        
        Args:
            messages: 消息列表
            model: 模型名称（可选，如果不指定则使用环境变量中的设置）
            
        Returns:
            tuple: (翻译文本, 推理内容, tokens使用情况)
        """
        async def _do_completion():
            # 添加系统提示
            full_messages = [
                {"role": "system", "content": self.system_prompt}
            ] + messages
            LOGGER.info(f"发送请求: {full_messages[1:]}")
            response = await self.client.chat.completions.create(
                model=model or self.model,
                messages=full_messages,
                temperature=self.temperature
            )
            
            message = response.choices[0].message
            reasoning_content = None
            if isinstance(message, ChatCompletionMessage) and hasattr(message, "reasoning_content"):
                reasoning_content = message.reasoning_content
                
            result = message.content
            LOGGER.info(f"响应: {result}")
            # 获取tokens使用情况
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return result, reasoning_content, usage
            
        # 提交任务到队列
        task_id = await self.task_manager.submit(_do_completion)
        # 等待任务完成并获取结果
        task = await self.task_manager.get_result(task_id)
        
        if task and task.completed:
            if task.error:
                raise task.error
            result, reasoning, usage = task.result
            # 累加tokens
            self.total_prompt_tokens += usage["prompt_tokens"]
            self.total_completion_tokens += usage["completion_tokens"]
            return result, reasoning, usage
        return None, None, None
    
    def get_total_usage(self) -> Dict:
        """
        获取总的tokens使用情况
        
        Returns:
            包含tokens统计的字典
        """
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens
        }

