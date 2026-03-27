import logging
import sys
import os

from links_status.all_friends import fetch_and_process_data, deal_with_large_data
from links_status.utils.json import write_json
from links_status.utils.config import load_config
from links_status.link_status import check_links_status

# ========== 日志设置 ==========
logging.basicConfig(
    level=logging.INFO,
    format='😋 %(levelname)s: %(message)s'
)

# ========== 加载环境变量 ==========
# if os.getenv("GITHUB_TOKEN") is None:
#     from dotenv import load_dotenv
#     load_dotenv()

# ========== 加载配置 ==========
config = load_config("./conf.yaml")

# ========== 爬虫模块 ==========
if config["spider_settings"]["enable"]:
    
    logging.info("�?爬虫已启�?)
    json_url = config['spider_settings']['json_url']
    article_count = config['spider_settings']['article_count']
    specific_rss = config['specific_RSS']

    logging.info(f"📥 正在�?{json_url} 获取数据，每个博客获�?{article_count} 篇文�?)
    result, lost_friends = fetch_and_process_data(
        json_url        = json_url,             # 包含朋友信息�?JSON 文件�?URL�?        specific_RSS    = specific_rss,         # 包含特定 RSS 源的字典列表 [{name, url}]（来�?YAML）�?        count           = article_count,        # 获取每个博客的最大文章数�?        cache_file      = "./temp/cache.json"   # 缓存文件路径�?    )

    article_count = len(result.get("article_data", []))
    logging.info(f"📦 数据获取完毕，共�?{article_count} 篇文章，正在处理数据")

    result = deal_with_large_data(result)

    write_json("./all.json", result)
    write_json("./errors.json", lost_friends)

# ========== 友链状态棄测模�?==========
if config["link_status"]["enable"]:
    logging.info("�?友链状态检测已启用")
    try:
        logging.info("🔍 开始检测友链状�?..")
        status_result = check_links_status(config, "./status.json")
        logging.info(f"�?友链状态检测完成，可访�? {status_result['accessible_count']}, 不可访问: {status_result['inaccessible_count']}")
    except Exception as e:
        logging.error(f"�?友链状态检测失�? {str(e)}")
else:
    logging.info("⚠️  友链状态检测未启用")
