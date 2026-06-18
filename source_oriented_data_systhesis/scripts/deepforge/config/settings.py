"""Configuration management for DeepForge

This module provides centralized configuration management using dataclasses.
All hardcoded values from the original codebase have been moved here.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Load environment variables from .env file
# Try multiple locations: project root, parent directories
try:
    from dotenv import load_dotenv

    # Try to find .env file in project root or parent directories
    current_dir = Path(__file__).resolve()
    for parent in [current_dir.parent] + list(current_dir.parents):
        env_path = parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            break
    else:
        # Fallback: try to load from current working directory
        load_dotenv()
except ImportError:
    # If python-dotenv is not installed, silently continue
    pass


@dataclass
class APIConfig:
    """API endpoint and authentication configuration"""

    # 统一 LLM API 配置
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_base_url: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL"))

    # 各阶段模型配置 (从环境变量读取)
    entry_point_model: str = field(default_factory=lambda: os.getenv("ENTRY_POINT_MODEL", "deepseek-chat"))
    exploration_model: str = field(default_factory=lambda: os.getenv("EXPLORATION_MODEL", "deepseek-chat"))
    qa_generation_model: str = field(default_factory=lambda: os.getenv("QA_GENERATION_MODEL", "deepseek-chat"))
    difficulty_enhancement_model: str = field(default_factory=lambda: os.getenv("DIFFICULTY_ENHANCEMENT_MODEL", "deepseek-chat"))

    # 兼容旧配置 (使用 exploration_model 作为默认值)
    gemini_model: str = field(default_factory=lambda: os.getenv("EXPLORATION_MODEL", "deepseek-chat"))

    # 其他模型配置 (保留兼容性)
    serper_model: str = "api_serper_serper"
    qwen_model: str = "qwen3-235b-a22b-instruct"
    deepseek_model: str = "deepseek-chat"

    # Local model server (for vLLM)
    local_model_ip: str = "29.81.244.91"
    local_model_port: int = 8010

    # External API keys (from environment variables)
    serper_api_key: Optional[str] = field(default_factory=lambda: os.getenv("SERPER_API_KEY"))
    deepseek_api_key: Optional[str] = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY"))
    jina_api_key: Optional[str] = field(default_factory=lambda: os.getenv("JINA_API_KEY"))

    # API endpoints (from environment variables)
    deepseek_base_url: Optional[str] = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL"))

    def get_serper_key(self) -> str:
        """Get Serper API key, raise error if not configured"""
        if not self.serper_api_key:
            raise ValueError(
                "SERPER_API_KEY not configured. Please set it in .env file."
            )
        return self.serper_api_key

    def get_openai_base_url(self) -> str:
        """Get OpenAI base URL, raise error if not configured"""
        if not self.openai_base_url:
            raise ValueError(
                "OPENAI_BASE_URL not configured. Please set it in .env file."
            )
        return self.openai_base_url

    def get_gemini_base_url(self) -> str:
        """Get Gemini base URL (uses OpenAI-compatible endpoint)"""
        return self.get_openai_base_url()  # Gemini uses same endpoint


@dataclass
class PathConfig:
    """Path configuration for input/output files"""

    # Root directories
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    data_dir: Path = field(init=False)
    tmp_dir: Path = field(init=False)

    # Input/output paths
    urls_path: Path = field(init=False)
    clean_urls_path: Path = field(init=False)
    raw_entities_path: Path = field(init=False)
    seed_entities_path: Path = field(init=False)
    seed_graph_path: Path = field(init=False)
    qa_pairs_all_path: Path = field(init=False)

    def __post_init__(self):
        self.data_dir = self.project_root / "data"
        self.tmp_dir = self.project_root / "tmp"
        self.urls_path = self.data_dir / "urls.jsonl"
        self.clean_urls_path = self.data_dir / "clean_urls.jsonl"
        self.raw_entities_path = self.data_dir / "raw_entities.jsonl"
        self.seed_entities_path = self.tmp_dir / "seed_entities.json"  # JSON format for generate_qa.py
        self.seed_entities_jsonl_path = self.data_dir / "seed_entities.jsonl"  # JSONL format
        self.seed_graph_path = self.tmp_dir / "seed_entities_graph.jsonl"
        self.qa_pairs_all_path = self.data_dir / "qa_pairs_all.jsonl"

    def ensure_directories(self):
        """Create all required directories if they don't exist"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class ConcurrencyConfig:
    """Concurrency settings for different pipeline stages"""

    url_generation_workers: int = 64
    entity_extraction_workers: int = 80
    qa_generation_workers: int = 64
    difficulty_enhancement_workers: int = 16
    quality_filter_workers: int = 32
    post_enhancement_workers: int = 512


@dataclass
class GenerationConfig:
    """QA generation parameters"""

    random_seed: int = 42
    min_date_cutoff: str = "2024-01-01"  # For URL filtering
    max_qa_generation_tries: int = 8

    # Depth distribution for entity exploration (weights for depths 1,2,3,4)
    depth_weights: list = field(default_factory=lambda: [10, 40, 40, 10])

    # Content limits
    max_url_content_length: int = 100000

    # Exploration timeout
    exploration_timeout: int = 1200


@dataclass
class Settings:
    """Main settings container that aggregates all configuration sections"""

    api: APIConfig = field(default_factory=APIConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)

    @classmethod
    def from_yaml(cls, config_path: str = "config.yaml") -> "Settings":
        """Load settings from YAML file

        Note: This requires PyYAML to be installed.
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required to load config from YAML. Install with: pip install pyyaml")

        config_file_path = Path(config_path)
        if not config_file_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file_path, "r") as f:
            config_dict = yaml.safe_load(f)

        # Create nested config objects from dict
        return cls(
            api=APIConfig(**config_dict.get("api", {})),
            paths=PathConfig(**config_dict.get("paths", {})),
            concurrency=ConcurrencyConfig(**config_dict.get("concurrency", {})),
            generation=GenerationConfig(**config_dict.get("generation", {})),
        )

    def to_yaml(self, config_path: str = "config.yaml"):
        """Save settings to YAML file

        Note: This requires PyYAML to be installed.
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required to save config to YAML. Install with: pip install pyyaml")

        from dataclasses import asdict

        config_dict = {
            "api": asdict(self.api),
            "paths": {
                "data_dir": str(self.paths.data_dir),
                "tmp_dir": str(self.paths.tmp_dir),
            },
            "concurrency": asdict(self.concurrency),
            "generation": asdict(self.generation),
        }

        with open(config_path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False)


# Global settings instance
settings = Settings()
