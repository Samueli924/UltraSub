#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
字幕翻译工具 - Web API服务

该模块提供了字幕翻译的Web API接口，支持：
- 异步任务处理
- 文件上传和验证
- 任务状态监控
- 结果文件管理

Author: Samueli924
Date: 2024-02
License: MIT
Version: 1.0.0
"""

from flask import Flask, request, jsonify
from src.llm import TranslationModel
from src.funcs import (
    read_srt_file, 
    generate_translated_srt, 
    format_translation_prompt_with_context
)
from src.logging import LOGGER
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime
import uuid
from typing import Dict, Optional

app = Flask(__name__)

# 存储任务状态
tasks: Dict[str, Dict] = {}

# 加载环境变量
load_dotenv()

# 初始化翻译模型
llm = TranslationModel(
    os.getenv("API_KEY"),
    os.getenv("ENDPOINT")
)

def get_task_info(task_id: str) -> Optional[Dict]:
    """获取任务信息"""
    if task_id not in tasks:
        return None
    return {
        "task_id": task_id,
        "status": tasks[task_id]["status"],
        "progress": tasks[task_id]["progress"],
        "total": tasks[task_id]["total"],
        "created_at": tasks[task_id]["created_at"],
        "completed_at": tasks[task_id].get("completed_at"),
        "output_file": tasks[task_id].get("output_file"),
        "error": tasks[task_id].get("error")
    }

async def process_translation(task_id: str, file_path: str, domains: Optional[list] = None):
    """处理翻译任务"""
    try:
        # 更新任务状态
        tasks[task_id]["status"] = "processing"
        
        # 读取SRT文件
        subtitles = read_srt_file(file_path)
        tasks[task_id]["total"] = len(subtitles)
        
        # 准备翻译请求
        messages = [
            format_translation_prompt_with_context(subtitles, i)
            for i in range(len(subtitles))
        ]
        
        # 并行发送所有请求
        translation_tasks = [
            llm.chat_completion(messages=[msg])
            for msg in messages
        ]
        
        # 使用asyncio.gather执行所有请求
        results = []
        usages = []
        for i, task_coro in enumerate(translation_tasks):
            result_tuple = await task_coro
            # 提取翻译文本（第一个元素）
            translation_text = result_tuple[0] if result_tuple else None
            results.append(translation_text)
            
            # 提取token使用情况（第三个元素，如果存在）
            if result_tuple and len(result_tuple) > 2:
                usage = result_tuple[2]
                usages.append(usage)
                
            # 更新进度
            tasks[task_id].update({
                "progress": i + 1,
                "percentage": round((i + 1) * 100 / len(subtitles), 2)
            })
        
        # 生成译文文件
        output_dir = "output"
        translated_file = generate_translated_srt(subtitles, results, output_dir, file_path)
        
        # 更新任务状态
        total_usage = llm.get_total_usage()
        tasks[task_id].update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "output_file": translated_file,
            "percentage": 100,
            "tokens_usage": total_usage
        })
        
        # 清理上传的文件
        if os.path.exists(file_path):
            os.remove(file_path)
            LOGGER.info(f"清理上传文件: {file_path}")
        
    except Exception as e:
        LOGGER.error(f"翻译任务 {task_id} 执行失败: {str(e)}")
        tasks[task_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now().isoformat()
        })
        # 清理文件
        if os.path.exists(file_path):
            os.remove(file_path)

def validate_srt_file(file) -> bool:
    """验证SRT文件"""
    if not file:
        return False
    if not file.filename:
        return False
    if not file.filename.lower().endswith('.srt'):
        return False
    return True

@app.route('/api/translate', methods=['POST'])
async def start_translation():
    """
    启动翻译任务
    
    请求参数：
    - file: SRT文件
    - domains: 可选，专业领域列表，用逗号分隔
    
    返回：
    - task_id: 任务ID
    """
    try:
        if 'file' not in request.files:
            return jsonify({"error": "没有上传文件"}), 400
            
        file = request.files['file']
        if not validate_srt_file(file):
            return jsonify({"error": "无效的SRT文件"}), 400
        
        # 保存上传的文件
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
            
        file_path = os.path.join(upload_dir, f"{uuid.uuid4()}.srt")
        file.save(file_path)
        
        # 获取专业领域参数
        domains = request.form.get('domains', '').split(',') if request.form.get('domains') else None
        
        # 创建任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        tasks[task_id] = {
            "status": "pending",
            "progress": 0,
            "total": 0,
            "percentage": 0,
            "created_at": datetime.now().isoformat(),
            "file_path": file_path,
            "original_filename": file.filename
        }
        
        # 启动异步任务
        asyncio.create_task(process_translation(task_id, file_path, domains))
        
        return jsonify({
            "task_id": task_id,
            "message": "翻译任务已提交",
            "status_url": f"/api/tasks/{task_id}"
        })
        
    except Exception as e:
        LOGGER.error(f"提交翻译任务失败: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    task_info = get_task_info(task_id)
    if task_info is None:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(task_info)

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    """获取所有任务列表"""
    return jsonify([
        get_task_info(task_id)
        for task_id in tasks
    ])

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除任务记录"""
    if task_id not in tasks:
        return jsonify({"error": "任务不存在"}), 404
        
    # 如果任务正在进行中，不允许删除
    if tasks[task_id]["status"] == "processing":
        return jsonify({"error": "无法删除正在进行的任务"}), 400
        
    # 清理输出文件
    output_file = tasks[task_id].get("output_file")
    if output_file and os.path.exists(output_file):
        os.remove(output_file)
        
    # 删除任务记录
    del tasks[task_id]
    return jsonify({"message": "任务已删除"})

if __name__ == '__main__':
    # 确保必要的目录存在
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    
    app.run(host='0.0.0.0', port=5000) 