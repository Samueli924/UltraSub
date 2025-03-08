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
from dotenv import load_dotenv

async def main():
    # 加载环境变量
    load_dotenv()
    
    # 检查必要的环境变量
    required_env_vars = ['API_KEY', 'ENDPOINT', 'MODEL_NAME']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        LOGGER.error(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        LOGGER.info("请在.env文件中设置以下环境变量：")
        LOGGER.info("API_KEY=你的API密钥")
        LOGGER.info("ENDPOINT=https://api.deepseek.com")
        LOGGER.info("MODEL_NAME=deepseek-chat")
        return
    
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
            llm.chat_completion(messages=[msg])  # 不再直接指定model参数
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
