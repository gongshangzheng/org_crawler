"""主程序入口"""

import sys
import time
import signal
from pathlib import Path
from datetime import datetime, timedelta

from .utils.logger import setup_logger, get_logger
from .utils.config_loader import load_global_config, load_rule_config
from .utils.keyword_classifier import KeywordClassifier
from .crawler.crawler_manager import CrawlerManager
from .storage.file_manager import FileManager
from .storage.exporter_manager import ExporterManager
from .storage.path_manager import PathManager
from .storage.index_manager import IndexManager


# 需要运行的规则文件列表（可以添加多个）
RULE_FILES = [
    "rules/arxiv_rss.yaml",
    # 在这里继续添加其他规则文件路径，例如：
    # "rules/another_site.yaml",
]


# 全局变量用于信号处理
running = True


def signal_handler(signum, frame):
    """信号处理函数，用于优雅退出"""
    global running
    logger = get_logger()
    logger.info("收到退出信号，正在停止...")
    running = False


def run_crawl(crawler, path_manager, org_exporter, index_manager,
              file_manager, storage_config, logger):
    """
    执行一次爬取任务
    
    Args:
        crawler: 爬虫实例
        path_manager: 路径管理器
        org_exporter: 导出器
        index_manager: 索引管理器（可选）
        file_manager: 文件管理器
        storage_config: 存储配置
        logger: 日志记录器
        
    Returns:
        bool: 是否成功
    """
    try:
        logger.info("=" * 60)
        logger.info(f"开始执行爬取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
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
                    # 如果启用了分类，传递分类信息
                    categorized_items = None
                    if org_exporter.keyword_classifier and result.items_count > 0:
                        categorized_items = org_exporter.keyword_classifier.classify_items(result.items)
                    
                    index_manager.update_index(
                        site_name=result.site_name,
                        crawl_time=result.crawl_time,
                        items=result.items,
                        date_file_path=org_path,
                        categorized_items=categorized_items,
                        category_folders=org_exporter.category_folders
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
            return False
        
        logger.info("=" * 60)
        logger.info("本次爬取完成")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"爬取过程中发生错误: {e}", exc_info=True)
        return False


def setup_runtime(global_config, logger, rule_file: str):
    """
    加载指定规则文件并初始化与站点相关的组件。
    每次调用都会重新读取该规则文件，以便运行中修改配置可以生效。
    """
    # 加载规则配置
    if not Path(rule_file).exists():
        logger.error(f"规则文件不存在: {rule_file}")
        logger.info("请先创建规则配置文件")
        raise FileNotFoundError(f"规则文件不存在: {rule_file}")

    # 加载规则（传入全局配置以获取默认更新频率）
    site_config = load_rule_config(rule_file, global_config)
    logger.info(f"加载规则: {site_config.name}")
    logger.info(f"  URL: {site_config.url}")
    logger.info(f"  更新频率: {site_config.update_frequency} 分钟")
    if site_config.keywords:
        logger.info(f"  关键词: {', '.join(site_config.keywords)}")

    # 从规则配置中读取自定义配置
    custom_config = site_config.custom_config or {}

    # 读取存储配置
    storage_config = global_config.get('storage', {})

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

        # 读取表头和模板配置
        table_headers = index_config.get('table_headers', ["{title}", "{first_author}", "{link}"])
        cell_templates = index_config.get('cell_templates', {
            "title": "{title}",
            "first_author": "{first_author}",
            "link": "[[{link}][查看]]"
        })
        # 读取表头标签映射（可选，用于将变量名转换为中文显示）
        header_labels = index_config.get('header_labels', {
            "title": "标题",
            "first_author": "第一作者",
            "link": "链接"
        })

        index_manager = IndexManager(
            index_path=index_path,
            table_headers=table_headers,
            cell_templates=cell_templates,
            header_labels=header_labels
        )
        logger.info(f"索引文件: {index_path}")
        logger.info(f"索引表头: {table_headers}")

    # 创建爬虫（使用 CrawlerManager 自动选择）
    crawler = CrawlerManager.get_crawler(site_config)
    logger.info(f"使用爬虫: {crawler.__class__.__name__}")

    return (
        site_config,
        custom_config,
        storage_config,
        path_manager,
        org_exporter,
        index_manager,
        crawler,
    )


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

    # 初始化组件（与全局配置相关的，只需初始化一次）
    storage_config = global_config.get('storage', {})
    file_manager = FileManager(
        base_path=storage_config.get('base_path', 'data'),
        date_format=storage_config.get('date_format', '%Y-%m-%d')
    )

    # 注册信号处理器（用于优雅退出）
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # 终止信号

    logger.info("进入持续运行模式，配置将在每轮循环前重新加载")
    logger.info("按 Ctrl+C 停止程序")

    # 持续运行循环
    while running:
        try:
            if not RULE_FILES:
                logger.error("RULE_FILES 为空，没有可运行的规则文件")
                break

            # 以第一个规则文件作为调度基准，计算等待时间
            primary_rule_file = RULE_FILES[0]
            (
                site_config,
                custom_config,
                _storage_config_site,
                _path_manager_site,
                _org_exporter_site,
                _index_manager_site,
                _crawler_site,
            ) = setup_runtime(global_config, logger, primary_rule_file)

            # 获取更新频率（分钟）
            update_frequency_minutes = site_config.update_frequency
            update_frequency_seconds = update_frequency_minutes * 60

            # 获取定时爬取时间（从 custom_config 中读取）
            crawl_time_str = custom_config.get('crawl_time', None)

            # 计算本轮开始前需要等待的秒数
            next_crawl_time = None
            wait_seconds = update_frequency_seconds

            if crawl_time_str:
                try:
                    # 解析时间字符串（格式：HH:MM，例如 "08:00"）
                    hour, minute = map(int, crawl_time_str.split(':'))
                    if not (0 <= hour < 24 and 0 <= minute < 60):
                        raise ValueError("时间格式错误")

                    now = datetime.now()
                    today_crawl_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # 如果今天的时间已过，则设置为明天
                    if today_crawl_time <= now:
                        next_crawl_time = today_crawl_time + timedelta(days=1)
                    else:
                        next_crawl_time = today_crawl_time

                    wait_seconds = max(0, (next_crawl_time - now).total_seconds())
                    logger.info(f"[调度] 已设置定时爬取时间: {crawl_time_str}")
                    logger.info(f"[调度] 下次爬取时间: {next_crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
                except (ValueError, AttributeError) as e:
                    logger.warning(f"[调度] 解析爬取时间失败 ({crawl_time_str}): {e}，将使用更新频率 {update_frequency_minutes} 分钟")
                    wait_seconds = update_frequency_seconds

            # 等待至本轮开始时间
            if wait_seconds > 0:
                wait_minutes = int(wait_seconds // 60)
                if next_crawl_time:
                    logger.info(f"[调度] 等待到 {next_crawl_time.strftime('%Y-%m-%d %H:%M:%S')} 开始本轮爬取（约 {wait_minutes} 分钟）...")
                else:
                    logger.info(f"[调度] 等待 {wait_minutes} 分钟后开始本轮爬取...")

                wait_interval = 60  # 每60秒检查一次
                waited = 0
                while waited < wait_seconds and running:
                    sleep_time = min(wait_interval, wait_seconds - waited)
                    time.sleep(sleep_time)
                    waited += sleep_time
                    if waited % 300 == 0:  # 每5分钟打印一次剩余时间
                        remaining_minutes = int(max(0, (wait_seconds - waited) // 60))
                        logger.info(f"[调度] 距离本轮爬取还有约 {remaining_minutes} 分钟")

                if not running:
                    break

            # 到达本轮执行时间后，依次跑每一个规则文件
            for rule_file in RULE_FILES:
                try:
                    logger.info("=" * 60)
                    logger.info(f"开始处理规则文件: {rule_file}")
                    logger.info("=" * 60)

                    (
                        site_config,
                        custom_config,
                        storage_config_site,
                        path_manager,
                        org_exporter,
                        index_manager,
                        crawler,
                    ) = setup_runtime(global_config, logger, rule_file)

                    # 对于每个站点，使用其自己的存储配置（目前来自全局 storage，但为将来扩展保留）
                    run_crawl(
                        crawler=crawler,
                        path_manager=path_manager,
                        org_exporter=org_exporter,
                        index_manager=index_manager,
                        file_manager=file_manager,
                        storage_config=storage_config_site,
                        logger=logger,
                    )
                except FileNotFoundError:
                    # 某个规则文件不存在时，记录错误但继续处理其他规则
                    logger.error(f"规则文件不存在，跳过: {rule_file}")
                    continue

        except KeyboardInterrupt:
            logger.info("收到键盘中断信号")
            break
        except FileNotFoundError:
            # 规则文件不存在时直接退出
            break
        except Exception as e:
            logger.error(f"循环中发生错误: {e}", exc_info=True)
            # 即使出错也继续运行，等待下次更新
            logger.info("将按照当前更新频率在下一轮重试...")

    logger.info("=" * 60)
    logger.info("程序已停止")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

