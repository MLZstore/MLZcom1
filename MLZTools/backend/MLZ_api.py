"""
═════════════════════════════════════════════════════════════
  MLZ on Top
  
  Developer: MLZ Community
  Discord: https://discord.gg/plr
  © 2026 MLZ Community - All Rights Reserved
═════════════════════════════════════════════════════════════
"""

from typing import Optional
import PluginUtils

logger = PluginUtils.Logger()

class APIManager:
    def __init__(self, backend_path: str):
        self.backend_path = backend_path

    def get_download_endpoints(self) -> list:
        return ['unified']
