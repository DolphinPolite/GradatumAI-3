"""
Configuration loader module for GradatumAI
Loads and parses YAML configuration files
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file
    
    Args:
        config_path: Path to YAML config file. If None, uses default main_config.yaml
        
    Returns:
        Dictionary containing configuration
    """
    if config_path is None:
        # Use default config path
        config_path = Path(__file__).parent / "main_config.yaml"
    else:
        config_path = Path(config_path)
    
    # If config file doesn't exist, return default config
    if not config_path.exists():
        return get_default_config()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        return config
    except Exception as e:
        print(f"Error loading config from {config_path}: {e}")
        return get_default_config()


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration when YAML file is not available
    """
    return {
        'video': {
            'frame_skip': 1,
            'resize_width': 1280,
            'resize_height': 720,
        },
        'detection': {
            'confidence_threshold': 0.5,
            'nms_threshold': 0.4,
        },
        'tracking': {
            'max_age': 30,
            'min_hits': 3,
        },
        'ball': {
            'radius_range': [5, 20],
            'color_lower': [0, 0, 0],
            'color_upper': [179, 255, 50],
        },
        'output': {
            'output_dir': 'results',
            'save_video': True,
            'save_stats': True,
        }
    }


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge override config into base config
    
    Args:
        base: Base configuration
        override: Configuration overrides
        
    Returns:
        Merged configuration
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


if __name__ == '__main__':
    # Test the config loader
    config = load_config()
    print("Loaded configuration:")
    print(yaml.dump(config, default_flow_style=False))
