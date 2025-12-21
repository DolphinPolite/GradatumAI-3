import os
import sys
import yaml


class ConfigWrapper:
    def __init__(self, data: dict):
        self._data = data

    def get(self, dotted: str, default=None):
        parts = dotted.split('.') if dotted else []
        cur = self._data
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return default
        return cur


def load_config(path: str):
    """Load a YAML config file and return a ConfigWrapper.

    Args:
        path: Path to YAML file (relative or absolute).

    Returns:
        ConfigWrapper wrapping the parsed YAML dict.
    """
    # try direct path first
    if not os.path.isabs(path) and not os.path.exists(path):
        # search in sys.path entries (helps when tests run from a different cwd)
        found = None
        for p in sys.path:
            candidate = os.path.join(p, path)
            if os.path.exists(candidate):
                found = candidate
                break
        if found:
            path = found
        else:
            # also try relative to this package directory (common when package is imported)
            pkg_dir = os.path.dirname(__file__)
            # try basename in package dir
            base = os.path.basename(path)
            candidate = os.path.join(pkg_dir, base)
            if os.path.exists(candidate):
                path = candidate
            else:
                # try one level up (repo root might contain config/)
                candidate2 = os.path.join(os.path.dirname(pkg_dir), path)
                if os.path.exists(candidate2):
                    path = candidate2
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return ConfigWrapper(data)
