"""主程序入口"""

import sys
import time
from pathlib import Path
from datetime import datetime

from .utils.logger import setup_logger, get_logger
from .utils.config_loader import load_global_config, load_rule_config
from .utils.keyword_classifier import KeywordClassifier
from .crawler.crawler_manager import CrawlerManager
from .storage.file_manager import FileManager
from .storage.exporter_manager import ExporterManager
from .storage.path_manager import PathManager
from .storage.index_manager import IndexManager


def main():
    """主函数"""
    # 加载全局配置
    global_config = load_global_config()
    
    # 设置日志
    log_config = global_config.get('logging', {})
    logger = setup_logger(
        level=log_config.get('level', 'INFO'),
        log_file=log_config.get('file'),
        max_size_mb=log_config.get('max_size_mb', 10)
    )
    
    logger.info("=" * 60)
    logger.info("Org Crawler 启动")
    logger.info("=" * 60)
    
    # 加载规则配置（示例：ArXiv）
    rule_file = "rules/arxiv_rss.yaml"
    if not Path(rule_file).exists():
        logger.error(f"规则文件不存在: {rule_file}")
        logger.info("请先创建规则配置文件")
        sys.exit(1)
    
    try:
        # 加载规则配置（传入全局配置以获取默认更新频率）
        site_config = load_rule_config(rule_file, global_config)
        logger.info(f"加载规则: {site_config.name}")
        logger.info(f"  URL: {site_config.url}")
        logger.info(f"  更新频率: {site_config.update_frequency} 分钟")
        logger.info(f"  关键词: {', '.join(site_config.keywords)}")
    except Exception as e:
        logger.error(f"加载规则配置失败: {e}")
        sys.exit(1)
    
    # 初始化组件
    storage_config = global_config.get('storage', {})
    file_manager = FileManager(
        base_path=storage_config.get('base_path', 'data'),
        date_format=storage_config.get('date_format', '%Y-%m-%d')
    )
    
    # 从规则配置中读取配置
    custom_config = site_config.custom_config or {}
    
    # 初始化关键词分类器（如果配置了类别映射）
    keyword_classifier = None
    category_folders = {}
    
    category_mapping = custom_config.get('category_mapping', {})
    if category_mapping:
        keyword_classifier = KeywordClassifier(category_mapping)
        logger.info(f"已启用关键词分类，类别数: {len(category_mapping)}")
    
    category_folders = custom_config.get('category_folders', {})
    if category_folders:
        logger.info(f"已配置类别文件夹映射: {category_folders}")
    
    # 初始化 PathManager
    exporter_config = custom_config.get('exporter', {})
    path_config = exporter_config.get('path', {})
    path_type = path_config.get('type', 'relative')
    path_base = path_config.get('base_path', storage_config.get('base_path', 'data'))
    path_template = path_config.get('template', 'data/{site_name}/{date}.org')
    
    path_manager = PathManager(
        base_path=path_base,
        path_type=path_type,
        path_template=path_template
    )
    logger.info(f"路径管理器: 类型={path_type}, 基础路径={path_base}")
    
    # 初始化 Exporter
    exporter_config_dict = custom_config.get('exporter', {})
    if not exporter_config_dict:
        # 向后兼容：如果没有exporter配置，使用旧的配置方式
        exporter_config_dict = {
            'class': 'BaseOrgExporter',
            'org_format': custom_config.get('org_format', 'detailed')
        }
    
    org_exporter = ExporterManager.create_exporter(
        exporter_config=exporter_config_dict,
        keyword_classifier=keyword_classifier,
        category_folders=category_folders
    )
    logger.info(f"使用 Exporter: {exporter_config_dict.get('class', 'BaseOrgExporter')}")
    
    # 初始化 IndexManager（如果启用）
    index_config = exporter_config.get('index', {})
    index_enabled = index_config.get('enabled', False)
    index_manager = None
    
    if index_enabled:
        index_path_config = index_config.get('path')
        if index_path_config:
            index_path = Path(path_base) / site_config.name / index_path_config
        else:
            index_path = path_manager.get_index_path(site_config.name)
        index_manager = IndexManager(index_path)
        logger.info(f"索引文件: {index_path}")
    
    # 创建爬虫（使用 CrawlerManager 自动选择）
    crawler = CrawlerManager.get_crawler(site_config)
    logger.info(f"使用爬虫: {crawler.__class__.__name__}")
    
    # 执行一次爬取
    logger.info("开始执行爬取...")
    result = crawler.crawl()
    
    if result.success:
        logger.info(f"爬取成功，获取到 {result.items_count} 个条目")
        
        if result.items_count > 0:
            # 使用 PathManager 获取输出路径
            org_path = path_manager.get_output_path(
                site_name=result.site_name,
                date=result.crawl_time
            )
            
            # 保存 JSON（可选，使用新的路径格式）
            output_format = storage_config.get('output_format', 'org')
            if output_format in ['json', 'both']:
                # 使用与 org 文件相同的路径，但扩展名为 .json
                json_path = org_path.with_suffix('.json')
                json_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 保存 JSON 数据
                import json
                data = {
                    'site_name': result.site_name,
                    'crawl_time': result.crawl_time.isoformat(),
                    'items_count': result.items_count,
                    'items': result.items
                }
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"已保存 JSON 文件: {json_path}")
            
            # 保存 Org-mode
            if output_format in ['org', 'both']:
                org_exporter.export(result, org_path)
                
                # 如果启用了分类，显示每个类别的文件路径
                if org_exporter.keyword_classifier and result.items_count > 0:
                    categorized_items = org_exporter.keyword_classifier.classify_items(result.items)
                    for category, items in categorized_items.items():
                        category_folder = org_exporter.category_folders.get(category, category)
                        category_path = org_path.parent / category_folder / org_path.name
                        logger.info(f"已保存 {category} 类别 Org-mode 文件: {category_path} ({len(items)} 个条目)")
                else:
                    logger.info(f"已保存 Org-mode 文件: {org_path}")
            
            # 更新索引文件
            if index_manager:
                index_manager.update_index(
                    site_name=result.site_name,
                    crawl_time=result.crawl_time,
                    items=result.items,
                    date_file_path=org_path
                )
                logger.info(f"已更新索引文件: {index_manager.index_path}")
            
            # 更新元数据
            json_path_for_metadata = None
            if output_format in ['json', 'both']:
                json_path_for_metadata = org_path.with_suffix('.json')
            file_manager.update_metadata(result, json_path=json_path_for_metadata)
            logger.info("已更新元数据")
            
            # 显示前几个条目
            logger.info("前几个条目:")
            for i, item in enumerate(result.items[:3], 1):
                logger.info(f"  {i}. {item.get('title', '无标题')[:60]}...")
        else:
            logger.info("本次爬取没有新条目")
    else:
        logger.error(f"爬取失败: {result.error_message}")
    
    logger.info("=" * 60)
    logger.info("爬取完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

