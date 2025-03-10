#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
工具函数模块

该模块包含各种辅助函数，用于：
- SRT文件的读取和解析
- 翻译提示的格式化
- 上下文管理
- 结果输出和文件生成

Author: Samueli924
Date: 2025-03
License: MIT
Version: 1.0.0
"""

import os
from typing import List, Dict
from src.logging import LOGGER

def read_srt_file(file_path: str) -> List[Dict]:
    """
    读取SRT文件并解析内容
    
    Args:
        file_path: SRT文件路径
        
    Returns:
        包含字幕信息的字典列表，每个字典包含序号、时间戳和文本内容
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")
        
    LOGGER.info(f"开始读取字幕文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:  # 使用 utf-8-sig 来自动处理 BOM
            content = f.read().strip()
            
        # 按空行分割字幕块
        subtitle_blocks = content.split('\n\n')
        subtitles = []
        
        for block in subtitle_blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                LOGGER.warning(f"跳过无效字幕块: {block}")
                continue
                
            try:
                # 解析字幕块
                subtitle_number = int(lines[0])  # 现在不会包含BOM了
                timestamp = lines[1]
                text = ' '.join(lines[2:])  # 合并可能的多行文本
                
                subtitles.append({
                    'number': subtitle_number,
                    'timestamp': timestamp,
                    'text': text
                })
            except ValueError as e:
                LOGGER.error(f"解析字幕块时出错: {str(e)}, 块内容: {block}")
                continue
            
        LOGGER.info(f"成功读取字幕文件，共 {len(subtitles)} 条字幕")
        return subtitles
        
    except Exception as e:
        LOGGER.error(f"读取字幕文件时发生错误: {str(e)}")
        raise

def display_translation_results(subtitles: List[Dict], results: List[tuple]) -> None:
    """
    显示翻译结果
    
    Args:
        subtitles: 原字幕列表
        results: 翻译结果列表
    """
    for subtitle, (translation, _) in zip(subtitles, results):
        if translation:
            LOGGER.info(f"\n字幕 #{subtitle['number']}:")
            LOGGER.info(f"时间: {subtitle['timestamp']}")
            LOGGER.info(f"原文: {subtitle['text']}")
            LOGGER.info(f"译文: {translation}")
        else:
            LOGGER.warning(f"字幕 #{subtitle['number']} 翻译失败")

def format_translation_prompt_with_context(subtitles: List[Dict], start_index: int, batch_size: int = 3) -> Dict:
    """
    格式化带上下文的批量翻译提示
    
    Args:
        subtitles: 所有字幕列表
        start_index: 批次起始索引
        batch_size: 批次大小，默认3行
        
    Returns:
        格式化的消息字典
    """
    end_index = min(start_index + batch_size, len(subtitles))
    
    # 获取上文（最多两句）
    context_before = []
    for i in range(max(0, start_index - 2), start_index):
        context_before.append(subtitles[i]['text'])
    
    # 获取下文（最多两句）
    context_after = []
    for i in range(end_index, min(len(subtitles), end_index + 2)):
        context_after.append(subtitles[i]['text'])
    
    # 获取当前批次的字幕
    current_batch = []
    for i in range(start_index, end_index):
        current_batch.append({
            "编号": subtitles[i]['number'],
            "文本": subtitles[i]['text']
        })
    
    # 构建上下文字典
    context = {
        "上文": " - ".join(context_before) if context_before else "",
        "当前批次": current_batch,
        "下文": " - ".join(context_after) if context_after else ""
    }
    
    return {
        "role": "user",
        "content": (
            str(context)
        )
    }

def parse_batch_translation_result(result: str, subtitles: List[Dict], start_index: int, batch_size: int = 3) -> List[tuple]:
    """
    解析批量翻译结果
    
    Args:
        result: LLM返回的翻译结果文本
        subtitles: 原字幕列表
        start_index: 批次起始索引
        batch_size: 批次大小
        
    Returns:
        解析后的翻译结果列表，与原始format兼容
    """
    import json
    import re
    
    # 尝试从结果中提取JSON格式的翻译数据
    try:
        # 使用正则表达式查找JSON数组
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            translations = json.loads(json_str)
            
            # 构建与单行翻译结果格式兼容的结果
            parsed_results = []
            end_index = min(start_index + batch_size, len(subtitles))
            
            # 创建一个编号到翻译的映射
            translation_map = {item["编号"]: item["译文"] for item in translations}
            
            for i in range(start_index, end_index):
                subtitle = subtitles[i]
                number = subtitle['number']
                
                if number in translation_map:
                    # 返回 (翻译文本, 推理过程, None)，与chat_completion返回格式兼容
                    parsed_results.append((translation_map[number], None, None))
                else:
                    LOGGER.warning(f"字幕 #{number} 在批量翻译结果中未找到，将使用原文")
                    parsed_results.append((subtitle['text'], None, None))
                    
            return parsed_results
            
        else:
            raise ValueError("无法在结果中找到JSON格式的翻译数据")
    
    except Exception as e:
        LOGGER.error(f"解析批量翻译结果时出错: {str(e)}")
        LOGGER.error(f"原始结果: {result}")
        
        # 返回空结果，保持与原始字幕数量一致
        end_index = min(start_index + batch_size, len(subtitles))
        return [(None, None, None) for _ in range(start_index, end_index)]

def generate_translated_srt(subtitles: List[Dict], translations: List[tuple], output_dir: str, original_filename: str) -> str:
    """
    生成翻译后的SRT文件
    
    Args:
        subtitles: 原字幕列表
        translations: 翻译结果列表 (可能包含2元组或3元组)
        output_dir: 输出目录
        original_filename: 原始文件名
        
    Returns:
        生成的文件路径
    """
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        LOGGER.info(f"创建输出目录: {output_dir}")
    
    # 生成输出文件名
    base_name = os.path.splitext(os.path.basename(original_filename))[0]
    output_file = os.path.join(output_dir, f"{base_name}_zh.srt")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for subtitle, translation_data in zip(subtitles, translations):
                # 适应旧版返回值 (text, reasoning) 和新版返回值 (text, reasoning, usage)
                if isinstance(translation_data, tuple):
                    if len(translation_data) >= 1:
                        translation = translation_data[0]
                    else:
                        translation = None
                else:
                    translation = translation_data
                
                if not translation:
                    LOGGER.warning(f"字幕 #{subtitle['number']} 没有翻译结果，将保持原文")
                    translation = subtitle['text']
                
                # 写入SRT格式
                f.write(f"{subtitle['number']}\n")
                f.write(f"{subtitle['timestamp']}\n")
                f.write(f"{translation}\n")
                f.write("\n")
                
        LOGGER.info(f"成功生成译文字幕文件: {output_file}")
        return output_file
        
    except Exception as e:
        LOGGER.error(f"生成译文字幕文件时发生错误: {str(e)}")
        raise
