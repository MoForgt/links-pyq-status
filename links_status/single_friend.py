# -*- coding: utf-8 -*-
import logging
from datetime import datetime
import re
import os
import json
import subprocess
import feedparser
from links_status import HEADERS_XML
from links_status.utils.time import format_published_time
from links_status.utils.url import replace_non_domain


def curl_get(url: str, headers: dict = None, timeout_seconds: int = 15) -> tuple:
    """
    使用 curl 命令获取 HTTP 内容

    参数:
        url (str): 请求 URL
        headers (dict): 请求头字典
        timeout_seconds (int): 超时秒数

    返回:
        tuple: (status_code, content, success)
    """
    cmd = [
        "curl", "-s", "-L", "-w", "\n%{http_code}",
        "--connect-timeout", "10",
        "--max-time", str(timeout_seconds),
    ]

    # 添加 headers
    if headers:
        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])

    # 添加 User-Agent
    cmd.extend(["-A", HEADERS_XML.get("User-Agent", "Mozilla/5.0")])

    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds + 5)

        if result.returncode != 0:
            logging.debug(f"curl 请求失败 {url}: {result.stderr}")
            return (0, "", False)

        # 解析输出，最后一行是状态码
        lines = result.stdout.split('\n')
        if len(lines) < 2:
            return (0, "", False)

        try:
            status_code = int(lines[-1])
        except ValueError:
            status_code = 200

        content = '\n'.join(lines[:-1])
        return (status_code, content, True)

    except subprocess.TimeoutExpired:
        logging.debug(f"curl 请求超时 {url}")
        return (0, "", False)
    except Exception as e:
        logging.debug(f"curl 请求异常 {url}: {e}")
        return (0, "", False)


def check_feed(blog_url):
    """
    检查博客的 RSS 或 Atom 订阅链接

    优化点：
    - 检查 HTTP 状态码
    - 检查响应内容前几百字节内是否有 RSS/Atom 的特征标签
    """
    possible_feeds = [
        ('atom', '/atom.xml'),
        ('rss', '/rss.xml'),
        ('rss2', '/rss2.xml'),
        ('rss3', '/rss.php'),
        ('feed', '/feed'),
        ('feed2', '/feed.xml'),
        ('feed3', '/feed/'),
        ('feed4', '/feed.php'),
        ('index', '/index.xml')
    ]

    for feed_type, path in possible_feeds:
        feed_url = blog_url.rstrip('/') + path
        try:
            status_code, content, success = curl_get(feed_url, headers=HEADERS_XML, timeout_seconds=15)

            if success and status_code == 200 and content:
                # 检查内容是否是 RSS/Atom
                text_head = content[:1000].lower()
                if ('<rss' in text_head or '<feed' in text_head or '<rdf:rdf' in text_head):
                    return [feed_type, feed_url]
        except Exception:
            continue

    logging.warning(f"无法找到 {blog_url} 的订阅链接")
    return ['none', blog_url]


def parse_feed(url, count=5, blog_url=''):
    """
    解析 Atom 或 RSS2 feed 并返回包含网站名称、作者、原链接和每篇文章详细内容的字典

    参数：
        url (str): Atom 或 RSS2 feed 的 URL
        count (int): 获取文章数的最大数
        blog_url (str): 博客URL，用于处理链接

    返回：
        dict: 包含网站名称、作者、原链接和每篇文章详细内容的字典
    """
    try:
        status_code, content, success = curl_get(url, headers=HEADERS_XML, timeout_seconds=15)

        if not success or status_code != 200 or not content:
            logging.error(f"无法获取FEED内容：{url}，状态码：{status_code}")
            return {
                'website_name': '',
                'author': '',
                'link': '',
                'articles': []
            }

        feed = feedparser.parse(content)

        result = {
            'website_name': feed.feed.title if 'title' in feed.feed else '',
            'author': feed.feed.author if 'author' in feed.feed else '',
            'link': feed.feed.link if 'link' in feed.feed else '',
            'articles': []
        }

        for _ , entry in enumerate(feed.entries):

            if 'published' in entry:
                published = format_published_time(entry.published)
            elif 'updated' in entry:
                published = format_published_time(entry.updated)
                logging.warning(f"文章 {entry.title} 未包含发布时间，已使用更新时间 {published}")
            else:
                published = ''
                logging.warning(f"文章 {entry.title} 未包含任何时间信息")

            # 处理链接中可能存在的错误
            article_link = replace_non_domain(entry.link, blog_url) if 'link' in entry else ''

            article = {
                'title': entry.title if 'title' in entry else '',
                'author': result['author'],
                'link': article_link,
                'published': published,
                'summary': entry.summary if 'summary' in entry else '',
                'content': entry.content[0].value if 'content' in entry and entry.content else entry.description if 'description' in entry else ''
            }
            result['articles'].append(article)

        # 对文章按时间排序
        result['articles'] = sorted(result['articles'], key=lambda x: datetime.strptime(x['published'], '%Y-%m-%d %H:%M'), reverse=True)
        if count < len(result['articles']):
            result['articles'] = result['articles'][:count]

        return result
    except Exception as e:
        logging.error(f"无法解析FEED地址：{url}，错误信息: {str(e)}")
        return {
            'website_name': '',
            'author': '',
            'link': '',
            'articles': []
        }


def process_friend(friend, count: int, specific_and_cache=None):
    """
    处理单个朋友的博客信息

    参数：
        friend (list/tuple): [name, blog_url, avatar]
        count (int): 每个博客最大文章数
        specific_and_cache (list[dict]): 合并后的特殊 + 缓存列表

    返回：
        dict: 处理结果
    """
    if specific_and_cache is None:
        specific_and_cache = []

    # 解包 friend
    try:
        name, blog_url, avatar = friend
    except Exception:
        logging.error(f"friend 数据格式不正确: {friend!r}")
        return {
            'name': None,
            'status': 'error',
            'articles': [],
            'feed_url': None,
            'feed_type': 'none',
            'cache_update': {'action': 'none', 'name': None, 'url': None, 'reason': 'bad_friend_data'},
            'source_used': 'none',
        }

    rss_lookup = {e['name']: e for e in specific_and_cache if 'name' in e and 'url' in e}
    cache_update = {'action': 'none', 'name': name, 'url': None, 'reason': ''}
    feed_url, feed_type, source_used = None, 'none', 'none'

    # 1. 优先使用 specific 或 cache
    entry = rss_lookup.get(name)
    if entry:
        feed_url = entry['url']
        feed_type = 'specific'
        source_used = entry.get('source', 'unknown')
        logging.info(f"{name} 使用预设 RSS 源：{feed_url} （source={source_used}）")
    else:
        # 2. 自动探测
        feed_type, feed_url = check_feed(blog_url)
        source_used = 'auto'
        logging.info(f"{name} 自动探测 RSS：type：{feed_type}, url：{feed_url}")

        if feed_type != 'none' and feed_url:
            cache_update = {'action': 'set', 'name': name, 'url': feed_url, 'reason': 'auto_discovered'}

    # 3. 尝试解析 RSS
    articles, parse_error = [], False
    if feed_type != 'none' and feed_url:
        try:
            feed_info = parse_feed(feed_url, count, blog_url)
            if isinstance(feed_info, dict) and 'articles' in feed_info:
                articles = [
                    {
                        'title': a['title'],
                        'created': a['published'],
                        'link': a['link'],
                        'author': name,
                        'avatar': avatar,
                    }
                    for a in feed_info['articles']
                ]

                for a in articles:
                    logging.info(f"{name} 发布了新文章：{a['title']}，时间：{a['created']}，链接：{a['link']}")
            else:
                parse_error = True
        except Exception as e:
            logging.warning(f"解析 RSS 失败（{name} -> {feed_url}）：{e}")
            parse_error = True

    # 4. 如果缓存 RSS 无效则重新探测
    if parse_error and source_used in ('cache', 'unknown'):
        logging.info(f"缓存 RSS 无效，重新探测：{name} ({blog_url})")
        new_type, new_url = check_feed(blog_url)
        if new_type != 'none' and new_url:
            try:
                feed_info = parse_feed(new_url, count, blog_url)
                if isinstance(feed_info, dict) and 'articles' in feed_info:
                    articles = [
                        {
                            'title': a['title'],
                            'created': a['published'],
                            'link': a['link'],
                            'author': name,
                            'avatar': avatar,
                        }
                        for a in feed_info['articles']
                    ]

                    for a in articles:
                        logging.info(f"{name} 发布了新文章：{a['title']}，时间：{a['created']}，链接：{a['link']}")

                    feed_type, feed_url, source_used = new_type, new_url, 'auto'
                    cache_update = {'action': 'set', 'name': name, 'url': new_url, 'reason': 'repair_cache'}
                    parse_error = False
            except Exception as e:
                logging.warning(f"重新探测解析仍失败：{name} ({new_url})：{e}")
                cache_update = {'action': 'delete', 'name': name, 'url': None, 'reason': 'remove_invalid'}
                feed_type, feed_url = 'none', None
        else:
            cache_update = {'action': 'delete', 'name': name, 'url': None, 'reason': 'remove_invalid'}
            feed_type, feed_url = 'none', None

    # 5. 最终状态
    status = 'active' if articles else 'error'
    if not articles:
        if feed_type == 'none':
            logging.warning(f"{name} 的博客 {blog_url} 未找到有效 RSS")
        else:
            logging.warning(f"{name} 的 RSS {feed_url} 未解析出文章")

    return {
        'name': name,
        'status': status,
        'articles': articles,
        'feed_url': feed_url,
        'feed_type': feed_type,
        'cache_update': cache_update,
        'source_used': source_used,
    }


def get_latest_articles_from_link(url, count=5, last_articles_path="./temp/newest_posts.json"):
    """
    从指定链接获取最新的文章数据并与本地存储的上次的文章数据进行对比

    参数：
        url (str): 数据链接
        count (int): 获取文章数的最大数
        last_articles_path (str): 上次文章数据存储路径

    返回：
        tuple: (新文章列表, 当前文章列表)
    """
    try:
        # 使用 curl 获取数据
        status_code, content, success = curl_get(url, timeout_seconds=15)

        if not success or status_code != 200:
            logging.error(f"无法获取数据：{url}，状态码：{status_code}")
            return [], []

        data = json.loads(content)
        articles = data.get('article_data', [])[:count]
    except Exception as e:
        logging.error(f"无法获取最新文章数据：{url}，错误信息: {str(e)}")
        return [], []

    # 读取上次的文章数据
    if os.path.exists(last_articles_path):
        try:
            with open(last_articles_path, 'r', encoding='utf-8') as f:
                last_articles = json.load(f)
        except Exception as e:
            logging.warning(f"读取上次文章数据失败：{str(e)}")
            last_articles = []
    else:
        last_articles = []

    # 对比文章数据，找出新文章
    new_articles = [article for article in articles if article not in last_articles]

    # 保存当前文章数据到本地
    os.makedirs(os.path.dirname(last_articles_path), exist_ok=True)
    with open(last_articles_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    return new_articles, articles
