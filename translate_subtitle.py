from src.llm import TranslationModel
from src.logging import LOGGER
from src.funcs import (
    read_srt_file, 
    format_translation_prompt_with_context, 
    display_translation_results,
    generate_translated_srt
)
import os
import asyncio
import time
import argparse

async def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='字幕翻译工具')
    parser.add_argument('srt_file', help='要翻译的srt英文单轨文件路径')
    parser.add_argument(
        '--domains', 
        nargs='+', 
        help='专业领域列表，例如：--domains 科技 医疗 金融'
    )
    args = parser.parse_args()
    
    try:
        # 读取SRT文件
        subtitles = read_srt_file(args.srt_file)
        
        # 初始化翻译模型
        llm = TranslationModel(
            os.getenv("API_KEY"), 
            os.getenv("ENDPOINT"),
            domains=args.domains
        )
        
        # 准备翻译请求
        messages = [
            format_translation_prompt_with_context(subtitles, i)
            for i in range(len(subtitles))
        ]
        
        # 并行发送所有请求
        start_time = time.time()
        
        # 使用asyncio.gather并发执行所有请求
        tasks = [
            llm.chat_completion(messages=[msg], model="deepseek-chat")
            for msg in messages
        ]
        results = await asyncio.gather(*tasks)
        
        # 等待所有结果
        end_time = time.time()
        LOGGER.info(f"总共处理 {len(messages)} 个请求，耗时: {end_time - start_time:.2f} 秒")
        
        # 显示翻译结果
        # display_translation_results(subtitles, results)
        
        # 生成译文SRT文件
        output_dir = "output"
        translated_file = generate_translated_srt(subtitles, results, output_dir, args.srt_file)
        LOGGER.info(f"翻译完成！译文文件已保存至: {translated_file}")
            
    except Exception as e:
        LOGGER.error(f"程序执行出错: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
