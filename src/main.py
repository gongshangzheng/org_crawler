"""主程序入口"""

import sys
import time
import signal
from pathlib import Path
from datetime import datetime, timedelta

from typing import Dict
import argparse
from .utils.logger import setup_logger, get_logger
from .utils.config_loader import load_global_config, load_rule_config
from .crawler.crawler_manager import CrawlerManager
from .storage.file_manager import FileManager
from .storage.exporter_manager import ExporterManager
from .storage.path_manager import PathManager
from .storage.index_manager import IndexManager
from .filters import FilterManager, CategoryRuleClassifier
from .tools import Translator

parser = argparse.ArgumentParser(description='Org Crawler')
parser.add_argument('-c', '--continuous', action='store_true', help='持续运行模式')
parser.add_argument('-r', '--repair', action='store_true', help='修复模式')
args = parser.parse_args()


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
                
                # 如果启用了分类，先进行分类（避免重复计算）
                categorized_items = None
                if org_exporter.keyword_classifier and result.items_count > 0:
                    categorized_items = org_exporter.keyword_classifier.classify_items(result.items)
                
                # 保存 Org-mode
                if output_format in ['org', 'both']:
                    org_exporter.export(result, org_path)
                    
                    # 如果启用了分类，显示每个类别的文件路径
                    if categorized_items:
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
                
                # 如果启用了分类，显示每个类别的论文数量汇总
                if categorized_items:
                    logger.info("=" * 60)
                    logger.info("各分类论文数量统计:")
                    logger.info("-" * 60)
                    # 按类别名称排序输出
                    for category in sorted(categorized_items.keys()):
                        count = len(categorized_items[category])
                        logger.info(f"  {category}: {count} 篇")
                    logger.info("-" * 60)
                    total_categorized = sum(len(items) for items in categorized_items.values())
                    logger.info(f"  总计: {total_categorized} 篇（可能有重复分类）")
                    logger.info("=" * 60)
                
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

    # 初始化分类器（使用基于过滤器的 category_mapping）
    keyword_classifier = None
    category_folders: Dict[str, str] = {}

    category_mapping_cfg = custom_config.get('category_mapping', {})
    if category_mapping_cfg:
        category_classifier = CategoryRuleClassifier.from_config(category_mapping_cfg)
        keyword_classifier = category_classifier  # 作为 BaseOrgExporter 的分类器传入
        # 从配置中提取类别文件夹映射
        for name, cfg in category_mapping_cfg.items():
            folder = name
            if isinstance(cfg, dict):
                folder = cfg.get("folder", name)
            category_folders[name] = folder
        logger.info(f"已启用基于过滤器的分类，类别数: {len(category_folders)}")

    # 向后兼容：旧的 category_folders 配置仍然生效（可覆盖上面的 folder）
    legacy_category_folders = custom_config.get('category_folders', {})
    if legacy_category_folders:
        category_folders.update(legacy_category_folders)
        logger.info(f"已应用自定义类别文件夹映射: {category_folders}")

    # 读取存储配置
    storage_config = global_config.get('storage', {})

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

    # 创建翻译器（从配置中读取）
    translator_config = custom_config.get('translator', {})
    translator_enabled = translator_config.get('enabled', False)
    translator_source_lang = translator_config.get('source_lang', 'en')
    translator_target_lang = translator_config.get('target_lang', 'zh')
    translator_access_key_id = translator_config.get('access_key_id')
    translator_access_key_secret = translator_config.get('access_key_secret')
    
    translator = None
    if translator_enabled:
        translator = Translator(
            enabled=translator_enabled,
            source_lang=translator_source_lang,
            target_lang=translator_target_lang,
            access_key_id=translator_access_key_id,
            access_key_secret=translator_access_key_secret
        )
        if translator.enabled:
            logger.info(f"翻译器已启用（{translator_source_lang} -> {translator_target_lang}）")
        else:
            logger.warning("翻译器配置已启用但初始化失败，翻译功能将被禁用")
    else:
        logger.info("翻译器未启用")

    # 创建爬虫（使用 CrawlerManager 自动选择）
    crawler = CrawlerManager.get_crawler(site_config, translator=translator)
    logger.info(f"使用爬虫: {crawler.__class__.__name__}")

    # 构建过滤器链：全局 filters + 站点 filters
    global_filters_cfg = global_config.get("filters", [])
    rule_filters_cfg = custom_config.get("filters", [])
    filter_configs = []
    if isinstance(global_filters_cfg, list):
        filter_configs.extend(global_filters_cfg)
    if isinstance(rule_filters_cfg, list):
        filter_configs.extend(rule_filters_cfg)

    filters = FilterManager.create_filters(filter_configs)
    if filters:
        crawler.set_filters(filters)
        logger.info(f"已配置 {len(filters)} 个过滤器")
    else:
        logger.info("未配置过滤器，将使用默认关键词过滤（如有）")

    return (
        site_config,
        custom_config,
        storage_config,
        path_manager,
        org_exporter,
        index_manager,
        crawler,
    )


def run_once():
    """
    只运行一次的函数：执行所有规则文件后退出，不进入循环
    """
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
    logger.info("Org Crawler 启动（单次运行模式）")
    logger.info("=" * 60)
    
    # 初始化组件（与全局配置相关的，只需初始化一次）
    storage_config = global_config.get('storage', {})
    file_manager = FileManager(
        base_path=storage_config.get('base_path', 'data'),
        date_format=storage_config.get('date_format', '%Y-%m-%d')
    )

    # 检查规则文件列表
    if not RULE_FILES:
        logger.error("RULE_FILES 为空，没有可运行的规则文件")
        return

    # 依次执行每个规则文件
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

            # 执行爬取
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
        except Exception as e:
            logger.error(f"处理规则文件 {rule_file} 时发生错误: {e}", exc_info=True)
            continue

    logger.info("=" * 60)
    logger.info("单次运行完成")
    logger.info("=" * 60)


def run_continuous():
    """主函数（持续运行模式）"""
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
    logger.info("Org Crawler 启动（持续运行模式）")
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
                    if waited % 3600 == 0:  # 每1小时打印一次剩余时间
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

def main(continuous: bool = True, repair: bool = False):
    if continuous:
        if repair:
            run_once()
        run_continuous()
    else:
        run_once()

if __name__ == "__main__":
    main(continuous=args.continuous, repair=args.repair)

