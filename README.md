# Org Crawler - 持续运行的网络爬虫系统

## 项目概述

这是一个设计用于在服务器上不间断运行的网络爬虫系统。系统可以根据配置的规则自动从网络上爬取信息，并通过 GitHub 实现本地同步。

## 核心功能

- ✅ 支持 RSS 源自动爬取（简单规则）
- ✅ 支持自定义爬取规则（复杂网站）
- ✅ 可配置更新频率（如每 2 小时更新一次）
- ✅ 可配置结果存储路径
- ✅ 每个网站可设置独立存储文件夹
- ✅ **结果以 org-mode 格式输出**（便于 Emacs 等工具使用）
- ✅ **支持翻译 API 调用**（可自动翻译内容）
- ✅ **支持 LLM 调用**（可进行内容摘要、分析等）
- ✅ 通过 GitHub 实现数据同步

## 项目架构

### 目录结构

```
org_crawler/
├── README.md                 # 项目说明文档
├── requirements.txt          # Python 依赖包
├── .gitignore               # Git 忽略文件
├── config/                  # 全局配置文件
│   └── global_config.yaml   # 全局设置（存储路径、日志级别等）
├── rules/                   # 爬取规则配置文件夹
│   ├── arxiv_rss.yaml       # ArXiv RSS 爬取规则示例
│   └── custom_*.yaml        # 其他自定义爬取规则
├── src/                     # 源代码目录
│   ├── __init__.py
│   ├── main.py              # 主程序入口
│   ├── scheduler.py         # 任务调度器（管理更新频率）
│   ├── crawler/             # 爬虫模块
│   │   ├── __init__.py
│   │   ├── base.py          # 基础爬虫类
│   │   ├── rss_crawler.py   # RSS 爬虫实现
│   │   └── custom_crawler.py # 自定义爬虫实现
│   ├── models/              # 数据模型
│   │   ├── __init__.py
│   │   ├── site_config.py   # 网站配置数据类
│   │   └── crawl_result.py  # 爬取结果数据类
│   ├── storage/             # 存储模块
│   │   ├── __init__.py
│   │   ├── file_manager.py  # 文件存储管理
│   │   └── org_exporter.py  # Org-mode 格式导出器
│   ├── tools/               # 工具模块（翻译、LLM等）
│   │   ├── __init__.py
│   │   ├── translator.py    # 翻译 API 工具我
│   │   └── llm_client.py    # LLM 调用工具
│   └── utils/               # 工具函数
│       ├── __init__.py
│       ├── logger.py        # 日志工具
│       └── config_loader.py # 配置加载器
├── data/                    # 爬取结果存储目录（Git 管理）
│   ├── arxiv/               # ArXiv 爬取结果
│   │   ├── metadata.json    # 元数据（最后更新时间等）
│   │   └── items/           # 具体爬取内容
│   │       └── YYYY-MM-DD/  # 按日期组织
│   │           ├── items.json    # JSON 格式原始数据
│   │           └── items.org     # Org-mode 格式输出
│   └── {site_name}/         # 其他网站数据
└── logs/                    # 日志文件目录（Git 忽略）
    └── crawler.log
```

## 核心组件设计

### 1. 数据模型 (models/)

#### SiteConfig - 网站配置类
存储单个网站的完整配置信息：

```python
@dataclass
class SiteConfig:
    name: str                    # 网站名称（用于文件夹命名）
    url: str                     # 网站地址或 RSS 链接
    crawl_type: str             # 爬取类型：'rss' 或 'custom'
    update_frequency: int       # 更新频率（分钟）
    storage_path: str           # 存储路径（相对于 data/）
    enabled: bool               # 是否启用
    keywords: List[str]          # 关键词列表（用于过滤）
    custom_config: dict         # 自定义配置（爬取函数、选择器等）
    last_crawl_time: Optional[datetime]  # 最后爬取时间
```

#### CrawlRule - 爬取规则类
从 YAML 配置文件加载的规则：

```python
@dataclass
class CrawlRule:
    site_config: SiteConfig
    rule_file: str              # 规则文件路径
    created_at: datetime
```

#### CrawlResult - 爬取结果类
存储单次爬取的结果：

```python
@dataclass
class CrawlResult:
    site_name: str
    crawl_time: datetime
    items_count: int
    items: List[dict]           # 爬取到的条目列表
    success: bool
    error_message: Optional[str]
```

### 2. 爬虫模块 (crawler/)

#### BaseCrawler - 基础爬虫类
所有爬虫的基类，定义统一接口：

```python
class BaseCrawler:
    def __init__(self, site_config: SiteConfig)
    def crawl(self) -> CrawlResult
    def filter_by_keywords(self, items: List[dict]) -> List[dict]
    def save_results(self, result: CrawlResult) -> bool
```

#### RSSCrawler - RSS 爬虫
处理 RSS/Atom 源的爬取：

- 解析 RSS/Atom XML
- 支持关键词过滤
- 自动去重（基于 URL 或 ID）
- 增量更新（只保存新条目）

#### CustomCrawler - 自定义爬虫
处理需要自定义规则的网站：

- 支持 CSS 选择器
- 支持 XPath
- 支持自定义 Python 函数
- 可配置请求头、Cookie 等
- **可直接调用翻译工具**：`self.translator.translate(text, target_lang='zh')`
- **可直接调用 LLM 工具**：`self.llm.summarize(text)` 或 `self.llm.analyze(text, prompt)`

### 3. 调度器 (scheduler.py)

任务调度器，负责：

- 读取所有启用的规则
- 根据 `update_frequency` 安排爬取任务
- 使用线程池或异步任务执行爬取
- 记录执行日志
- 错误处理和重试机制

### 4. 存储模块 (storage/)

#### FileManager - 文件管理器
负责数据的持久化存储：

- 按网站名称创建文件夹
- 按日期组织数据文件
- 保存 JSON 格式的爬取结果（原始数据）
- **保存 Org-mode 格式文件**（主要输出格式）
- 维护元数据文件（最后更新时间、条目统计等）
- 支持增量更新（避免重复保存）

#### OrgExporter - Org-mode 导出器
负责将爬取结果转换为 org-mode 格式：

- 生成标准的 org-mode 文件
- 支持多级标题结构
- 支持元数据（标题、链接、日期、标签等）
- 支持内容翻译后的双语输出
- 支持 LLM 生成的摘要和分析

### 5. 工具模块 (tools/)

#### Translator - 翻译工具
提供翻译 API 调用功能：

```python
class Translator:
    def __init__(self, api_key: str, provider: str = "openai")
    def translate(self, text: str, target_lang: str = "zh", source_lang: str = "auto") -> str
    def translate_batch(self, texts: List[str], target_lang: str = "zh") -> List[str]
```

支持的翻译服务：
- OpenAI API（使用 GPT 模型）
- Google Translate API
- DeepL API
- 其他可扩展的翻译服务

#### LLMClient - LLM 调用工具
提供大语言模型调用功能：

```python
class LLMClient:
    def __init__(self, api_key: str, provider: str = "openai", model: str = "gpt-4")
    def summarize(self, text: str, max_length: int = 200) -> str
    def analyze(self, text: str, prompt: str) -> str
    def extract_keywords(self, text: str) -> List[str]
    def generate_tags(self, title: str, content: str) -> List[str]
```

支持的 LLM 服务：
- OpenAI API（GPT-3.5, GPT-4 等）
- Anthropic API（Claude）
- 本地模型（通过 API 兼容接口）
- 其他可扩展的 LLM 服务

### 6. 配置系统

#### 全局配置 (config/global_config.yaml)
```yaml
storage:
  base_path: "data"
  date_format: "%Y-%m-%d"
  output_format: "org"  # 输出格式：'org' 或 'json' 或 'both'
  
logging:
  level: "INFO"
  file: "logs/crawler.log"
  max_size_mb: 10
  
scheduler:
  check_interval: 60  # 检查任务间隔（秒）
  max_workers: 5      # 最大并发数

# 工具配置
tools:
  translator:
    enabled: true
    provider: "openai"  # 或 "google", "deepl"
    api_key: "${TRANSLATOR_API_KEY}"  # 从环境变量读取
    default_target_lang: "zh"
    cache_enabled: true  # 启用翻译缓存
  
  llm:
    enabled: true
    provider: "openai"  # 或 "anthropic", "local"
    api_key: "${LLM_API_KEY}"  # 从环境变量读取
    model: "gpt-4"
    temperature: 0.7
    max_tokens: 1000
```

#### 规则配置 (rules/*.yaml)
每个网站的爬取规则：

```yaml
# RSS 类型示例（arxiv_rss.yaml）
name: "arxiv"
url: "https://arxiv.org/rss/cs.AI"  # RSS 链接
crawl_type: "rss"
update_frequency: 120  # 2小时（分钟）
storage_path: "arxiv"
enabled: true
keywords:
  - "machine learning"
  - "deep learning"
  - "neural network"
custom_config:
  # RSS 爬虫的额外配置
  max_items: 100
  include_abstract: true
```

```yaml
# 自定义类型示例
name: "example_site"
url: "https://example.com/articles"
crawl_type: "custom"
update_frequency: 240  # 4小时
storage_path: "example_site"
enabled: true
keywords:
  - "python"
  - "web scraping"
custom_config:
  # 自定义爬虫配置
  method: "css_selector"  # 或 "xpath" 或 "custom_function"
  selectors:
    title: "h1.article-title"
    content: "div.article-content"
    link: "a.article-link::attr(href)"
  headers:
    User-Agent: "Mozilla/5.0..."
  pagination:
    enabled: true
    max_pages: 5
  
  # 工具使用配置
  use_translator: true
  translate_fields: ["title", "content"]  # 需要翻译的字段
  translate_to: "zh"  # 目标语言
  
  use_llm: true
  llm_tasks:
    - type: "summarize"  # 生成摘要
      field: "content"
      max_length: 200
    - type: "extract_keywords"  # 提取关键词
      fields: ["title", "content"]
    - type: "custom"  # 自定义任务
      prompt: "分析这篇文章的主要观点"
      field: "content"
```

## 工作流程

1. **初始化阶段**
   - 加载全局配置
   - 扫描 `rules/` 目录，加载所有规则文件
   - 初始化日志系统
   - 创建必要的目录结构

2. **调度阶段**
   - 调度器定期检查所有启用的规则
   - 根据 `last_crawl_time` 和 `update_frequency` 判断是否需要爬取
   - 将需要执行的任务加入队列

3. **爬取阶段**
   - 根据 `crawl_type` 选择对应的爬虫（RSS 或 Custom）
   - 执行爬取操作
   - 使用关键词过滤结果
   - 去重处理（避免重复保存）

4. **处理阶段**（可选）
   - 如果配置了翻译工具，对指定字段进行翻译
   - 如果配置了 LLM 工具，执行摘要、分析等任务
   - 将处理结果添加到条目数据中

5. **存储阶段**
   - 将原始结果保存为 JSON 格式（可选）
   - **将结果转换为 org-mode 格式并保存**
   - 更新元数据文件
   - 记录爬取日志

6. **同步阶段**
   - 通过 Git 提交更改
   - 推送到 GitHub 仓库
   - 本地可以 pull 获取最新数据

## ArXiv RSS 爬取示例

### 规则配置 (rules/arxiv_rss.yaml)

```yaml
name: "arxiv"
url: "https://arxiv.org/rss/cs.AI"  # 计算机科学-人工智能分类
crawl_type: "rss"
update_frequency: 120  # 每2小时更新一次
storage_path: "arxiv"
enabled: true
keywords:
  - "machine learning"
  - "deep learning"
  - "transformer"
  - "neural network"
custom_config:
  max_items: 50
  include_abstract: true
  categories:  # 可以配置多个 RSS 源
    - "cs.AI"
    - "cs.LG"
    - "cs.CV"
```

### 数据存储结构

```
data/arxiv/
├── metadata.json
└── items/
    ├── 2024-01-15/
    │   ├── items.json        # JSON 格式原始数据（可选）
    │   └── items.org         # Org-mode 格式输出（主要文件）
    ├── 2024-01-16/
    │   ├── items.json
    │   └── items.org
    └── ...
```

### Org-mode 输出格式示例

生成的 `items.org` 文件格式：

```org
#+TITLE: ArXiv 爬取结果 - 2024-01-15
#+DATE: 2024-01-15
#+AUTHOR: Org Crawler

* 条目 1: [2024-01-15 10:30]
:PROPERTIES:
:URL: https://arxiv.org/abs/2401.12345
:ID: arxiv:2401.12345
:KEYWORDS: machine learning, deep learning
:TRANSLATED: true
:END:

** 标题
Deep Learning for Natural Language Processing

** 标题（中文）
深度学习在自然语言处理中的应用

** 摘要
This paper presents a novel approach to...

** 摘要（中文）
本文提出了一种新颖的方法...

** LLM 摘要
[由 LLM 生成的简短摘要]

** 关键词
machine learning, NLP, transformer

** 元数据
- 发布时间: 2024-01-14
- 作者: John Doe, Jane Smith
- 分类: cs.AI
- 爬取时间: 2024-01-15 10:30:00

---

* 条目 2: [2024-01-15 11:00]
...
```

### metadata.json 示例

```json
{
  "site_name": "arxiv",
  "last_crawl_time": "2024-01-15T14:30:00",
  "total_items": 1250,
  "last_update_date": "2024-01-15",
  "enabled": true
}
```

## 环境变量配置

### 阿里云翻译 API 配置

项目支持通过环境变量配置阿里云翻译 API 的 AccessKey，这是**推荐的安全方式**。

#### 方式1：使用 .env 文件（推荐）

1. 复制示例文件：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的实际密钥：
```bash
# 阿里云 AccessKey ID
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id_here

# 阿里云 AccessKey Secret
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret_here
```

3. 项目会自动加载 `.env` 文件中的环境变量（通过 `python-dotenv`）

#### 方式2：系统环境变量

在系统环境变量中设置：
```bash
# Linux/macOS
export ALIBABA_CLOUD_ACCESS_KEY_ID="your_access_key_id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_access_key_secret"

# Windows (PowerShell)
$env:ALIBABA_CLOUD_ACCESS_KEY_ID="your_access_key_id"
$env:ALIBABA_CLOUD_ACCESS_KEY_SECRET="your_access_key_secret"
```

#### 方式3：在配置文件中设置（不推荐）

也可以在 `rules/*.yaml` 配置文件中直接设置，但**不推荐**，因为密钥会暴露在配置文件中：

```yaml
translator:
  enabled: true
  access_key_id: "your_access_key_id"
  access_key_secret: "your_access_key_secret"
```

**优先级**：配置文件中的值 > 环境变量 > 默认值（None）

**注意**：
- `.env` 文件已被 `.gitignore` 忽略，不会被提交到 Git
- 请妥善保管你的 AccessKey，不要泄露给他人
- 如果 AccessKey 泄露，请及时在阿里云控制台重置

## 部署和运行

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（如果使用 .env 文件，确保已创建并填写）
# cp .env.example .env
# 编辑 .env 文件

# 运行爬虫
python src/main.py
```

### 服务器部署

```bash
# 使用 systemd 或 supervisor 管理进程
# 确保程序持续运行

# 配置 Git 自动提交和推送
# 可以设置 cron 任务定期执行 git push
```

### GitHub 同步

1. 初始化 Git 仓库
2. 配置 `.gitignore`（忽略 logs/ 和临时文件）
3. 设置自动提交脚本
4. 配置 GitHub Actions 或 cron 任务自动推送

## CustomCrawler 中使用工具示例

在自定义爬虫中，可以直接调用翻译和 LLM 工具：

```python
from src.crawler.custom_crawler import CustomCrawler
from src.models.site_config import SiteConfig

class MyCustomCrawler(CustomCrawler):
    def process_item(self, item: dict) -> dict:
        """处理单个爬取条目"""
        # 1. 翻译标题和内容
        if self.site_config.custom_config.get('use_translator'):
            item['title_zh'] = self.translator.translate(
                item['title'], 
                target_lang='zh'
            )
            item['content_zh'] = self.translator.translate(
                item['content'],
                target_lang='zh'
            )
        
        # 2. 使用 LLM 生成摘要
        if self.site_config.custom_config.get('use_llm'):
            item['llm_summary'] = self.llm.summarize(
                item['content'],
                max_length=200
            )
            
            # 3. 提取关键词
            item['keywords'] = self.llm.extract_keywords(
                f"{item['title']}\n{item['content']}"
            )
            
            # 4. 自定义分析
            analysis_prompt = "分析这篇文章的技术亮点"
            item['technical_highlights'] = self.llm.analyze(
                item['content'],
                prompt=analysis_prompt
            )
        
        return item
```

工具在 `CustomCrawler` 初始化时自动加载，可通过 `self.translator` 和 `self.llm` 访问。

## 扩展性设计

- **插件化架构**：新的爬虫类型可以通过继承 `BaseCrawler` 轻松添加
- **工具扩展**：新的翻译或 LLM 服务可以通过实现统一接口添加
- **规则热加载**：支持运行时添加/修改规则（需要重启或热重载机制）
- **多数据源**：支持数据库、API 等多种存储方式
- **通知机制**：可以集成邮件、Webhook 等通知新内容
- **分布式支持**：未来可以扩展为分布式爬虫系统

## 技术栈建议

- **Python 3.8+**
- **依赖包**：
  - `feedparser` - RSS/Atom 解析
  - `requests` - HTTP 请求
  - `beautifulsoup4` / `lxml` - HTML 解析
  - `pyyaml` - YAML 配置解析
  - `schedule` 或 `APScheduler` - 任务调度
  - `python-dateutil` - 日期处理
  - `openai` - OpenAI API（翻译和 LLM）
  - `anthropic` - Anthropic API（Claude）
  - `googletrans` 或 `deep-translator` - 翻译服务（可选）
  - `python-dotenv` - 环境变量管理

## 下一步实现计划

1. ✅ 框架设计和文档（当前步骤）
2. ⏳ 实现基础数据模型
3. ⏳ 实现 RSS 爬虫（ArXiv 示例）
4. ⏳ 实现调度器
5. ⏳ 实现存储模块
6. ⏳ 实现配置加载器
7. ⏳ 实现主程序入口
8. ⏳ 添加日志和错误处理
9. ⏳ 实现 Git 自动同步
10. ⏳ 测试和优化

## 注意事项

- 遵守网站的 robots.txt 协议
- 设置合理的请求间隔，避免对服务器造成压力
- 处理网络异常和超时情况
- 定期清理旧数据，避免存储空间无限增长
- **保护敏感信息**：API Key、Cookie 等通过环境变量管理，不要提交到 Git
- **API 成本控制**：翻译和 LLM 调用会产生费用，建议：
  - 启用缓存机制，避免重复翻译相同内容
  - 设置合理的调用频率限制
  - 对长文本进行截断或分块处理
  - 监控 API 使用量
- **Org-mode 兼容性**：确保生成的 org 文件符合标准格式，可在 Emacs 等工具中正常使用

