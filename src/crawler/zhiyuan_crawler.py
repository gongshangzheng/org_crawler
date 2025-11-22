"""智源社区 HTML 爬虫实现"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Optional

from .base import BaseCrawler
from ..models.site_config import SiteConfig
from ..models.crawl_result import CrawlResult
from ..models.crawl_item import CrawlItem


class ZhiyuanHTMLCrawler(BaseCrawler):
    """智源社区 HTML 爬虫，解析HTML页面获取论文信息"""
    
    def __init__(self, site_config: SiteConfig, translator=None):
        """
        初始化智源社区 HTML 爬虫
        
        Args:
            site_config: 网站配置
            translator: 翻译器实例（可选）
        """
        super().__init__(site_config)
        self.translator = translator
        self.update_frequency_hours = site_config.update_frequency / 60  # 转换为小时
    
    def crawl(self) -> CrawlResult:
        """
        执行 HTML 爬取
        
        Returns:
            CrawlResult: 爬取结果
        """
        crawl_time = datetime.now()
        from ..utils.logger import get_logger
        logger = get_logger()
        
        try:
            # 开始抓取
            logger.info(f"[HTML 抓取] 开始抓取网页: {self.site_config.url}")
            logger.info(f"[HTML 抓取] 站点: {self.site_config.name}")
            
            # 获取网页内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.site_config.url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            logger.info("[HTML 抓取] 网页获取成功")
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找所有论文条目（paper-item）
            paper_items = soup.find_all('div', class_='paper-item')
            
            if not paper_items:
                logger.warning("[HTML 抓取] 未找到论文条目")
                return CrawlResult(
                    site_name=self.site_config.name,
                    crawl_time=crawl_time,
                    items_count=0,
                    success=True,
                    error_message="未找到论文条目"
                )
            
            logger.info(f"[HTML 抓取] 找到 {len(paper_items)} 个原始条目")
            
            # 检查是否配置了时间过滤器
            has_time_filter = False
            if self.filters:
                from ..filters.time_filter import TimeRangeFilter
                for flt in self.filters:
                    if isinstance(flt, TimeRangeFilter):
                        has_time_filter = True
                        break
                    # 检查嵌套的过滤器
                    if hasattr(flt, 'filters'):
                        for sub_flt in getattr(flt, 'filters', []):
                            if isinstance(sub_flt, TimeRangeFilter):
                                has_time_filter = True
                                break
            
            # 解析条目
            items = []
            for paper_item in paper_items:
                try:
                    # 将 BeautifulSoup 元素转换为字典格式，以便使用统一的 extract_* 方法
                    entry = {'soup_element': paper_item}
                    item = self.parse_entry(entry)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.warning(f"[HTML 抓取] 解析条目时出错: {e}")
                    continue
            
            logger.info(f"[HTML 抓取] 初步处理后剩余 {len(items)} 个条目")
            
            # 如果没有条目，提前返回
            if len(items) == 0:
                logger.warning(f"[HTML 抓取] 初步处理后没有符合条件的条目")
                return CrawlResult(
                    site_name=self.site_config.name,
                    crawl_time=crawl_time,
                    items_count=0,
                    success=True,
                    error_message="时间过滤后没有符合条件的条目"
                )
            
            # 应用过滤器
            logger.info(f"[HTML 抓取] 开始应用过滤器...")
            filtered_items = self.apply_filters(items)
            logger.info(f"[HTML 抓取] 过滤器处理后剩余 {len(filtered_items)} 个条目")
            
            # 转换为字典列表
            items_dict = [item.to_dict() for item in filtered_items]
            
            # 应用翻译（如果启用了翻译器）
            if self.translator and self.translator.enabled:
                logger.info(f"[翻译] 开始翻译 {len(items_dict)} 个条目的标题和摘要...")
                translated_count = 0
                for item_dict in items_dict:
                    translated_item = self.translator.translate_item(item_dict)
                    if 'title_zh' in translated_item or 'summary_zh' in translated_item:
                        translated_count += 1
                    item_dict.update(translated_item)
                logger.info(f"[翻译] 完成翻译，成功翻译 {translated_count} 个条目")
            
            # 检查是否成功爬取到条目
            items_count = len(filtered_items)
            
            if items_count > 0:
                logger.info(f"[HTML 抓取] ✓ 成功爬取到 {items_count} 个条目")
                logger.info("[HTML 抓取] 前几个条目预览:")
                preview_count = min(5, items_count)
                for i, item_dict in enumerate(items_dict[:preview_count], 1):
                    title = item_dict.get('title', '无标题')
                    link = item_dict.get('link', '')
                    published_time_str = item_dict.get('published_time_str', '')
                    logger.info(f"  {i}. [{title[:60]}{'...' if len(title) > 60 else ''}]")
                    logger.info(f"     链接: {link}")
                    logger.info(f"     发布时间: {published_time_str}")
            else:
                error_msg = f"爬取失败：未能获取到任何条目（站点: {self.site_config.name}, URL: {self.site_config.url}）"
                logger.error(f"[HTML 抓取] ✗ {error_msg}")
                return CrawlResult(
                    site_name=self.site_config.name,
                    crawl_time=crawl_time,
                    items_count=0,
                    success=False,
                    error_message=error_msg
                )
            
            return CrawlResult(
                site_name=self.site_config.name,
                crawl_time=crawl_time,
                items_count=items_count,
                items=items_dict,
                success=True
            )
            
        except Exception as e:
            logger.error(f"[HTML 抓取] ✗ 爬取过程中发生异常: {str(e)}", exc_info=True)
            return CrawlResult(
                site_name=self.site_config.name,
                crawl_time=crawl_time,
                items_count=0,
                success=False,
                error_message=f"爬取失败: {str(e)}"
            )
    
    def extract_published_time(self, entry: Dict) -> Optional[datetime]:
        """
        提取发布时间
        
        Args:
            entry: 包含 BeautifulSoup 元素的字典
            
        Returns:
            datetime 对象，如果解析失败返回 None
        """
        try:
            soup_element = entry.get('soup_element')
            if not soup_element:
                return None
            
            # 查找发布时间元素
            time_elem = soup_element.find('span', class_='paper-item-time')
            if not time_elem:
                return None
            
            time_text = time_elem.get_text(strip=True)
            if not time_text:
                return None
            
            # 解析时间文本，格式如 "2025年11月17日"
            # 移除可能的空格和换行
            time_text = time_text.strip()
            
            # 尝试解析中文日期格式：2025年11月17日
            match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', time_text)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3)) + 1 # 智源社区的发布时间比标注时间晚一天,不知道为什么
                return datetime(year, month, day)
            
            # 如果解析失败，返回 None
            return None
            
        except Exception as e:
            return None
    
    def extract_title(self, entry: Dict) -> str:
        """
        提取标题
        
        Args:
            entry: 包含 BeautifulSoup 元素的字典
            
        Returns:
            标题字符串
        """
        try:
            soup_element = entry.get('soup_element')
            if not soup_element:
                return ''
            
            # 查找标题元素
            title_elem = soup_element.find('h6', class_='paper-item-title')
            if title_elem:
                return title_elem.get_text(strip=True)
            
            # 备用：查找 title 属性
            title_elem = soup_element.find(attrs={'title': True})
            if title_elem:
                return title_elem.get('title', '').strip()
            
            return ''
        except Exception:
            return ''
    
    def extract_link(self, entry: Dict) -> str:
        """
        提取链接
        
        Args:
            entry: 包含 BeautifulSoup 元素的字典
            
        Returns:
            链接字符串
        """
        try:
            soup_element = entry.get('soup_element')
            if not soup_element:
                return ''
            
            # 查找链接元素
            link_elem = soup_element.find('a', href=True)
            if link_elem:
                href = link_elem.get('href', '')
                # 如果是相对路径，转换为绝对路径
                if href.startswith('/'):
                    base_url = 'https://hub.baai.ac.cn'
                    return base_url + href
                return href
            
            return ''
        except Exception:
            return ''
    
    def extract_other_info(self, entry: Dict) -> Dict:
        """
        提取其他信息（摘要、作者、分类等）
        
        Args:
            entry: 包含 BeautifulSoup 元素的字典
            
        Returns:
            其他信息的字典
        """
        other_info = {
            'summary': '',
            'authors': [],
            'categories': [],
            'id': '',
        }
        
        try:
            soup_element = entry.get('soup_element')
            if not soup_element:
                return other_info
            
            # 提取摘要
            summary_elem = soup_element.find('div', class_='paper-item-summary')
            if summary_elem:
                summary_text = summary_elem.get_text(strip=True)
                # 也可以尝试获取 title 属性（可能包含完整摘要）
                summary_title = summary_elem.get('title', '')
                if summary_title and len(summary_title) > len(summary_text):
                    other_info['summary'] = summary_title
                else:
                    other_info['summary'] = summary_text
            
            # 提取作者
            author_elems = soup_element.find_all('span', class_='paper-author-name')
            authors = []
            for author_elem in author_elems:
                author_text = author_elem.get_text(strip=True)
                if author_text and author_text != '...':
                    authors.append(author_text)
            other_info['authors'] = authors
            
            # 提取智源社区ID（从链接中提取）
            link = self.extract_link(entry)
            if link:
                # 链接格式：/paper/e9847a14-bb0f-4a32-9411-351d0b502838
                # 或：https://hub.baai.ac.cn/paper/e9847a14-bb0f-4a32-9411-351d0b502838
                match = re.search(r'/paper/([a-f0-9\-]+)', link)
                if match:
                    other_info['zhiyuan_id'] = match.group(1)
                    other_info['id'] = match.group(1)  # 同时设置通用 id
            
            # 如果没有提取到 id，使用链接作为 id
            if not other_info['id']:
                other_info['id'] = link
            
            return other_info
            
        except Exception as e:
            return other_info
