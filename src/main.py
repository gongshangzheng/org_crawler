"""主程序入口"""

import sys
import time
from pathlib import Path
from datetime import datetime

from .utils.logger import setup_logger, get_logger
from .utils.config_loader import load_global_config, load_rule_config
from .crawler.crawler_manager import CrawlerManager
from .storage.file_manager import FileManager
from .storage.org_exporter import OrgExporter


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
    org_exporter = OrgExporter()
    
    # 创建爬虫（使用 CrawlerManager 自动选择）
    crawler = CrawlerManager.get_crawler(site_config)
    logger.info(f"使用爬虫: {crawler.__class__.__name__}")
    
    # 执行一次爬取
    logger.info("开始执行爬取...")
    result = crawler.crawl()
    
    if result.success:
        logger.info(f"爬取成功，获取到 {result.items_count} 个条目")
        
        if result.items_count > 0:
            # 保存结果
            storage_path = file_manager.get_storage_path(
                result.site_name,
                result.crawl_time
            )
            
            # 保存 JSON（可选）
            output_format = storage_config.get('output_format', 'org')
            if output_format in ['json', 'both']:
                file_manager.save_json(result, storage_path)
                logger.info(f"已保存 JSON 文件: {storage_path / 'items.json'}")
            
            # 保存 Org-mode
            if output_format in ['org', 'both']:
                org_path = storage_path / "items.org"
                org_exporter.export(result, org_path)
                logger.info(f"已保存 Org-mode 文件: {org_path}")
            
            # 更新元数据
            file_manager.update_metadata(result)
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

