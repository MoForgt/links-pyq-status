"""
友链状态检测模块
基于 links-status-main 的逻辑，提供友链可访问性检测功能
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
import aiohttp
import requests
from zoneinfo import ZoneInfo

from friend_circle_lite.utils.json import write_json


class LinkStatusChecker:
    """友链状态检测器"""
    
    def __init__(self, config: dict):
        """
        初始化检测器
        
        Args:
            config: 配置字典，包含检测相关参数
        """
        self.config = config
        self.detection_config = config.get('link_status', {})
        self.timeout = self.detection_config.get('timeout', 30)
        self.max_attempts = self.detection_config.get('max_attempts', 3)
        self.retry_delay = self.detection_config.get('retry_delay', 1000) / 1000  # 转换为秒
        self.batch_size = self.detection_config.get('batch_size', 10)
        self.batch_delay = self.detection_config.get('batch_delay', 200) / 1000  # 转换为秒
        self.success_status_min = self.detection_config.get('success_status_min', 200)
        self.success_status_max = self.detection_config.get('success_status_max', 399)
        self.use_backup_api = self.detection_config.get('use_backup_api', True)
        self.backup_api_url = self.detection_config.get('backup_api_url', 'https://v1.nsuuu.com/api/netCheck')
        
        # 请求头配置
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 (Friend-Circle-Lite/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
        # SSL验证配置
        self.ssl_verify = self.detection_config.get('ssl_verify', False)
        
        # 错误计数存储
        self.error_count = {}
        
    def extract_domain(self, url: str) -> str:
        """从URL中提取域名"""
        try:
            parsed = urlparse(url)
            return parsed.hostname or url
        except Exception:
            return url
    
    def format_shanghai_time(self, dt: datetime = None) -> str:
        """格式化为上海时间字符串"""
        if dt is None:
            dt = datetime.now()
        
        # 转换为上海时间
        shanghai_tz = ZoneInfo("Asia/Shanghai")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=shanghai_tz)
        else:
            dt = dt.astimezone(shanghai_tz)
        
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    async def check_with_backup_api(self, session: aiohttp.ClientSession, url: str, name: str) -> Optional[Dict[str, Any]]:
        """使用备用API检测链接"""
        if not self.use_backup_api:
            return None
        
        try:
            logging.info(f"🔍 {name}: 使用备用API检测...")
            api_url = f"{self.backup_api_url}?host={url}"
            start_time = time.time()
            
            async with session.get(api_url, timeout=self.timeout) as response:
                latency = round((time.time() - start_time), 2)
                
                if response.status == 200:
                    data = await response.json()
                    status_code = int(data.get('data', {}).get('https', {}).get('status', 0))
                    success = int(data.get('code', 0)) == 200 and (
                        self.success_status_min <= status_code <= self.success_status_max
                    )
                    
                    if success:
                        logging.info(f"✅ {name}: 备用API检测成功 (状态码: {status_code}, 延迟: {latency}s)")
                        return {
                            'success': True,
                            'latency': latency,
                            'status': status_code,
                            'attempts': 4,  # 表示使用了备用API
                            'method': 'backup_api'
                        }
                    else:
                        logging.warning(f"❌ {name}: 备用API检测失败 (状态码: {status_code})")
                        return {
                            'success': False,
                            'latency': -1,
                            'status': status_code,
                            'attempts': 4,
                            'method': 'backup_api',
                            'error': f'备用API检测失败，状态码: {status_code}'
                        }
                else:
                    logging.warning(f"❌ {name}: 备用API请求失败 (HTTP {response.status})")
                    return {
                        'success': False,
                        'latency': -1,
                        'status': 0,
                        'attempts': 4,
                        'method': 'backup_api',
                        'error': f'备用API请求失败，HTTP {response.status}'
                    }
                    
        except Exception as e:
            logging.error(f"❌ {name}: 备用API检测异常 - {str(e)}")
            return {
                'success': False,
                'latency': -1,
                'status': 0,
                'attempts': 4,
                'method': 'backup_api',
                'error': f'备用API检测异常: {str(e)}'
            }
    
    async def check_link_with_retry(self, session: aiohttp.ClientSession, url: str, name: str) -> Dict[str, Any]:
        """带重试的链接检测"""
        
        # 直接访问重试
        for attempt in range(1, self.max_attempts + 1):
            try:
                if attempt > 1:
                    logging.info(f"🔄 {name}: 第{attempt}次直接访问重试...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logging.info(f"🔍 检测 {name} ({url})...")
                
                start_time = time.time()
                
                async with session.get(url, timeout=self.timeout) as response:
                    latency = round((time.time() - start_time), 2)
                    success = self.success_status_min <= response.status <= self.success_status_max
                    
                    if success:
                        if attempt > 1:
                            logging.info(f"✅ {name}: 第{attempt}次直接访问重试成功 (状态码: {response.status}, 延迟: {latency}s)")
                        else:
                            logging.info(f"✅ {name}: 直接访问检测成功 (状态码: {response.status}, 延迟: {latency}s)")
                        
                        return {
                            'success': True,
                            'latency': latency,
                            'status': response.status,
                            'attempts': attempt,
                            'method': 'direct'
                        }
                    else:
                        if attempt < self.max_attempts:
                            logging.warning(f"⚠️  {name}: 第{attempt}次直接访问失败 (状态码: {response.status}), 准备重试...")
                        else:
                            logging.warning(f"⚠️  {name}: 第{self.max_attempts}次直接访问失败 (状态码: {response.status}), 尝试使用备用API...")
                        
            except Exception as e:
                if attempt < self.max_attempts:
                    logging.warning(f"⚠️  {name}: 第{attempt}次直接访问异常 - {str(e)}, 准备重试...")
                else:
                    logging.warning(f"⚠️  {name}: 第{self.max_attempts}次直接访问异常 - {str(e)}, 尝试使用备用API...")
        
        # 直接访问都失败了，尝试使用备用API
        backup_result = await self.check_with_backup_api(session, url, name)
        if backup_result and backup_result['success']:
            return backup_result
        
        # 所有检测方法都失败了
        return {
            'success': False,
            'latency': -1,
            'status': 0,
            'error': f'经过{self.max_attempts}次直接访问和备用API检测后仍然失败',
            'attempts': self.max_attempts + 1,
            'method': 'all_failed'
        }
    
    async def batch_check_links(self, links_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量检测链接状态"""
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        # 根据SSL验证设置配置连接器
        if self.ssl_verify:
            connector = aiohttp.TCPConnector(limit=self.batch_size, limit_per_host=5)
        else:
            connector = aiohttp.TCPConnector(limit=self.batch_size, limit_per_host=5, ssl=False)
        
        async with aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout,
            connector=connector
        ) as session:
            
            results = []
            
            # 分批处理
            for i in range(0, len(links_data), self.batch_size):
                batch = links_data[i:i + self.batch_size]
                
                # 并发检测当前批次
                tasks = [
                    self.check_link_with_retry(session, link['link'], link['name'])
                    for link in batch
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 处理结果
                for j, result in enumerate(batch_results):
                    link = batch[j]
                    
                    if isinstance(result, Exception):
                        logging.error(f"检测 {link['name']} 时发生异常: {str(result)}")
                        result = {
                            'success': False,
                            'latency': -1,
                            'status': 0,
                            'error': f'检测异常: {str(result)}',
                            'attempts': 1,
                            'method': 'exception'
                        }
                    
                    # 更新错误计数
                    domain = self.extract_domain(link['link'])
                    if result['success']:
                        if domain in self.error_count and self.error_count[domain] > 0:
                            logging.info(f"✅ {domain}: 恢复正常，异常次数已重置 (之前: {self.error_count[domain]})")
                        self.error_count[domain] = 0
                    else:
                        self.error_count[domain] = self.error_count.get(domain, 0) + 1
                        logging.warning(f"⚠️  {domain}: 异常次数增加到 {self.error_count[domain]}")
                    
                    # 组装最终结果
                    final_result = {
                        'name': link['name'],
                        'link': link['link'],
                        'favicon': link.get('favicon', ''),
                        'latency': result['latency'],
                        'success': result['success'],
                        'status': result['status'],
                        'error': result.get('error', ''),
                        'attempts': result['attempts'],
                        'method': result['method'],
                        'error_count': self.error_count[domain]
                    }
                    
                    results.append(final_result)
                
                # 批次间延迟
                if i + self.batch_size < len(links_data):
                    await asyncio.sleep(self.batch_delay)
            
            return results
    
    def load_friends_data(self, json_url: str) -> List[Dict[str, Any]]:
        """加载友链数据"""
        try:
            logging.info(f"📡 从 {json_url} 获取友情链接数据...")
            verify = self.ssl_verify
            response = requests.get(json_url, headers=self.headers, timeout=30, verify=verify)
            response.raise_for_status()
            
            data = response.json()
            logging.info("✅ 源数据获取成功")
            
            # 适配友链数据格式：从friends数组获取数据
            if not data or 'friends' not in data or not isinstance(data['friends'], list):
                raise ValueError('源数据格式错误，未找到friends数组')
            
            # 将friends数组转换为对象数组：{ name, link, favicon }
            links_to_check = []
            for friend in data['friends']:
                if isinstance(friend, list) and len(friend) >= 2:
                    link_data = {
                        'name': friend[0],       # 名称在数组第一个位置
                        'link': friend[1],       # 链接在数组第二个位置
                        'favicon': friend[2] if len(friend) > 2 else ''  # 图标URL在数组第三个位置
                    }
                    links_to_check.append(link_data)
            
            logging.info(f"📋 获取到 {len(links_to_check)} 个友情链接")
            return links_to_check
            
        except Exception as e:
            logging.error(f"❌ 获取友链数据失败: {str(e)}")
            raise
    
    async def check_all_links(self, json_url: str = None) -> Dict[str, Any]:
        """检测所有友链状态"""
        try:
            # 使用配置中的URL或传入的URL
            source_url = json_url or self.config['spider_settings']['json_url']
            
            # 加载友链数据
            links_data = self.load_friends_data(source_url)
            
            logging.info('🔍 开始检测所有链接...')
            
            # 批量检测
            check_results = await self.batch_check_links(links_data)
            
            # 统计结果
            accessible_count = sum(1 for result in check_results if result['success'])
            inaccessible_count = len(check_results) - accessible_count
            
            # 组装最终数据
            result_data = {
                'timestamp': self.format_shanghai_time(),
                'accessible_count': accessible_count,
                'inaccessible_count': inaccessible_count,
                'total_count': len(check_results),
                'link_status': check_results
            }
            
            logging.info('=' * 50)
            logging.info('📊 检测统计:')
            logging.info(f"✅ 可访问链接: {accessible_count}")
            logging.info(f"❌ 不可访问链接: {inaccessible_count}")
            logging.info(f"📈 总链接数: {len(check_results)}")
            logging.info(f"📅 检测时间: {result_data['timestamp']}")
            logging.info('=' * 50)
            
            return result_data
            
        except Exception as e:
            logging.error(f"检测友链状态时发生错误: {str(e)}")
            raise


def check_links_status(config: dict, output_path: str = "./status.json") -> Dict[str, Any]:
    """
    检测友链状态的主函数
    
    Args:
        config: 配置字典
        output_path: 输出文件路径
        
    Returns:
        检测结果字典
    """
    try:
        # 创建检测器
        checker = LinkStatusChecker(config)
        
        # 运行异步检测
        result = asyncio.run(checker.check_all_links())
        
        # 保存结果
        write_json(output_path, result)
        logging.info(f"✅ 状态检测结果已保存到: {output_path}")
        
        return result
        
    except Exception as e:
        logging.error(f"友链状态检测失败: {str(e)}")
        raise