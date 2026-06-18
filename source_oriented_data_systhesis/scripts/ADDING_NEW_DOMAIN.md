# Unified Pipeline Framework - 添加新领域指南

## 概述

统一管道框架支持轻松添加新领域。每个新领域只需：
1. 定义扩展池子 (可选)
2. 实现领域特定的策略
3. 注册到工厂类

## 快速开始

### 步骤1: 创建扩展池子文件

创建 `scripts/expanded_{domain}_pools.py`:

```python
#!/usr/bin/env python3
"""
Expanded {Domain} Data Pools
"""

from typing import List, Dict
import random

class Expanded{Domain}Pools:
    """
    大规模{Domain}数据池
    """

    # 定义分类
    WIKIPEDIA_CATEGORIES = {
        # 按子类别组织
        "subcategory1": [
            "Category:{Subcategory1}",
            "Category:{Subcategory2}",
            # ...
        ],
        "subcategory2": [
            # ...
        ]
    }

    # 定义关键词/实体池
    POOLS = {
        "type1": ["item1", "item2", "item3"],
        "type2": ["item1", "item2", "item3"],
        # ...
    }

    @classmethod
    def get_all_categories(cls) -> List[str]:
        """获取所有分类"""
        all_cats = []
        for category_list in cls.WIKIPEDIA_CATEGORIES.values():
            all_cats.extend(category_list)
        return all_cats

    @classmethod
    def generate_search_queries(cls) -> List[str]:
        """生成搜索查询组合"""
        queries = []

        # 添加你的组合逻辑
        query = "{type1} {type2}"
        queries.append(query)

        return queries
```

### 步骤2: 更新管道文件

更新领域特定的管道文件，使用扩展池子：

```python
# 在 {domain}_random_pipeline.py 中

class {Domain}EntryPointGenerator:
    def __init__(self):
        # 导入扩展池子
        from expanded_{domain}_pools import Expanded{Domain}Pools
        self.expanded_pools = Expanded{Domain}Pools()

        self.strategies = {
            'strategy1': self.strategy1_method,
            'strategy2': self.strategy2_method,
            # ...
        }

        # 使用扩展分类
        self.CATEGORIES = self.expanded_pools.get_all_categories()
```

### 步骤3: 在统一框架中注册

编辑 `scripts/unified_pipeline.py`:

```python
# 1. 添加导入
class {Domain}RandomPipeline(BaseRandomPipeline):
    """{Domain}类随机管道"""

    def __init__(self):
        super().__init__()

    def _initialize_strategies(self):
        """初始化{Domain}类策略"""
        from {domain}_random_pipeline import {Domain}EntryPointGenerator
        gen = {Domain}EntryPointGenerator()
        self.strategies = gen.strategies

    def _initialize_pools(self):
        """初始化{Domain}类数据池"""
        from expanded_{domain}_pools import Expanded{Domain}Pools
        self.pools = Expanded{Domain}Pools()

    @property
    def domain_name(self) -> str:
        return "{domain_lower}"

# 2. 在PipelineFactory中注册
class PipelineFactory:
    PIPELINES = {
        "historical": HistoricalRandomPipeline,
        "geographical": GeographicalRandomPipeline,
        "{domain_lower}": {Domain}RandomPipeline,  # 新增
    }
```

### 步骤4: 更新CLI帮助信息

在 `epilog` 字符串中添加新领域描述：

```python
epilog="""
Supported Domains:
  historical    - Historical data (6 strategies)
  geographical  - Geographical data (4 strategies)
  {domain_lower}    - {Domain} data (N strategies)

Examples:
  # Run {domain} pipeline
  python scripts/unified_pipeline.py --domain {domain_lower}
"""
```

## 领域模板

### 科学类 (Scientific) 模板

```python
class ExpandedScientificPools:
    WIKIPEDIA_CATEGORIES = {
        "disciplines": [
            "Category:Physics", "Category:Chemistry", "Category:Biology",
            "Category:Astronomy", "Category:Geology", "Category:Mathematics"
        ],
        "concepts": [
            "Category:Scientific_discoveries", "Category:Scientific_theories",
            "Category:Laboratory_equipment", "Category:Scientific_method"
        ]
    }

    POOLS = {
        "disciplines": ["physics", "chemistry", "biology", "astronomy"],
        "entities": ["atom", "molecule", "cell", "planet", "star"],
        "actions": ["discovery", "invention", "experiment", "research"]
    }
```

### 文学类 (Literary) 模板

```python
class ExpandedLiteraryPools:
    WIKIPEDIA_CATEGORIES = {
        "by_genre": [
            "Category:Novels", "Category:Poetry", "Category:Drama",
            "Category:Science_fiction", "Category:Fantasy", "Category:Mystery"
        ],
        "by_period": [
            "Category:Ancient_literature", "Category:Medieval_literature",
            "Category:Renaissance_literature", "Category:Modern_literature"
        ],
        "by_region": [
            "Category:Literature_by_country", "Category:American_literature",
            "Category:European_literature", "Category:Asian_literature"
        ]
    }

    POOLS = {
        "genres": ["novel", "poetry", "drama", "essay", "short story"],
        "elements": ["plot", "character", "theme", "symbolism", "metaphor"],
        "roles": ["author", "poet", "playwright", "novelist"]
    }
```

### 艺术类 (Art) 模板

```python
class ExpandedArtPools:
    WIKIPEDIA_CATEGORIES = {
        "by_medium": [
            "Category:Painting", "Category:Sculpture", "Category:Architecture",
            "Category:Photography", "Category:Digital_art", "Category:Performance_art"
        ],
        "by_movement": [
            "Category:Renaissance_art", "Category:Baroque_art",
            "Category:Impressionism", "Category:Cubism", "Category:Surrealism"
        ],
        "by_region": [
            "Category:European_art", "Category:Asian_art",
            "Category:African_art", "Category:American_art"
        ]
    }

    POOLS = {
        "media": ["painting", "sculpture", "photograph", "installation"],
        "styles": ["realism", "abstract", "impressionist", "surrealist"],
        "elements": ["color", "composition", "technique", "brushwork"]
    }
```

## 策略模式参考

### 标准策略组合

大多数领域可以采用以下策略：

1. **LLM生成概念** - `llm_generate_{domain}_concept`
   - 使用LLM随机生成该领域概念

2. **Wikipedia角度提取** - `wikipedia_{domain}_angle`
   - 随机Wikipedia页面 → 提取该领域角度

3. **Wikipedia分类随机** - `wikipedia_{domain}_category`
   - 从该领域分类中随机选择页面

4. **关键词搜索** - `random_{domain}_keyword_search`
   - 使用该领域关键词组合搜索

### 可选策略

- **DBpedia查询** - 如果有对应的DBpedia属性
- **特定API** - 如果该领域有专用API
- **时间/地域组合** - 时间段+地区随机组合

## 数据池设计原则

1. **全球覆盖** - 避免地域偏置
2. **时间跨度** - 覆盖不同时代
3. **类型多样** - 涵盖该领域的主要类型
4. **层次结构** - 按子类别组织
5. **可扩展性** - 易于添加新条目

## 示例对比

| 领域 | 策略数 | 分类数 | 关键词类型 |
|------|--------|--------|-----------|
| 历史 | 6 | 112 | 时代、地区、角色、事件 |
| 地理 | 4 | 100 | 地貌、气候、生物群落 |
| 科学 | 4-5 | ~50 | 学科、概念、实体 |
| 文学 | 4-5 | ~40 | 体裁、时期、地区 |
| 艺术 | 4-5 | ~60 | 媒介、运动、风格 |

## 测试新领域

```bash
# 测试管道初始化
python scripts/unified_pipeline.py --domain {domain_lower} --num-iterations 1

# 完整运行
python scripts/unified_pipeline.py --domain {domain_lower} --num-iterations 10
```
