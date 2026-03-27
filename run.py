import logging
import sys
import os

from links-status.all_friends import fetch_and_process_data, deal_with_large_data
from links-status.utils.json import write_json
from links-status.utils.config import load_config
from links-status.link_status import check_links_status

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
    
    logging.info("✅ 爬虫已启用")
    json_url = config['spider_settings']['json_url']
    article_count = config['spider_settings']['article_count']
    specific_rss = config['specific_RSS']

    logging.info(f"📥 正在从 {json_url} 获取数据，每个博客获取 {article_count} 篇文章")
    result, lost_friends = fetch_and_process_data(
        json_url        = json_url,             # 包含朋友信息的 JSON 文件的 URL。
        specific_RSS    = specific_rss,         # 包含特定 RSS 源的字典列表 [{name, url}]（来自 YAML）。
        count           = article_count,        # 获取每个博客的最大文章数。
        cache_file      = "./temp/cache.json"   # 缓存文件路径。
    )

    article_count = len(result.get("article_data", []))
    logging.info(f"📦 数据获取完毕，共有 {article_count} 篇文章，正在处理数据")

    result = deal_with_large_data(result)

    write_json("./all.json", result)
    write_json("./errors.json", lost_friends)

# ========== 友链状态棄测模块 ==========
if config["link_status"]["enable"]:
    logging.info("✅ 友链状态检测已启用")
    try:
        logging.info("🔍 开始检测友链状态...")
        status_result = check_links_status(config, "./status.json")
        logging.info(f"✅ 友链状态检测完成，可访问: {status_result['accessible_count']}, 不可访问: {status_result['inaccessible_count']}")
    except Exception as e:
        logging.error(f"❌ 友链状态检测失败: {str(e)}")
else:
    logging.info("⚠️  友链状态检测未启用")
