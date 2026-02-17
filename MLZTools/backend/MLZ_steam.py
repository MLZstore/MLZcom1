"""
═════════════════════════════════════════════════════════════
  MLZ on Top
  
  Developer: MLZ Community
  Discord: https://discord.gg/MLZ
  © 2026 MLZ Community - All Rights Reserved
═════════════════════════════════════════════════════════════
"""

import os
import sys
from typing import Optional
import Millennium
import PluginUtils

logger = PluginUtils.Logger()

if sys.platform.startswith('win'):
    try:
        import winreg
    except Exception:
        winreg = None

_steam_install_path: Optional[str] = None
_stplug_in_path_cache: Optional[str] = None

def detect_steam_install_path() -> str:
    global _steam_install_path

    if _steam_install_path:
        return _steam_install_path

    path = None

    if sys.platform.startswith('win') and winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                path, _ = winreg.QueryValueEx(key, 'SteamPath')
        except Exception:
            path = None

    if not path:
        try:
            path = Millennium.steam_path()
        except Exception:
            path = None

    _steam_install_path = path
    return _steam_install_path or ''

def get_steam_config_path() -> str:
    steam_path = detect_steam_install_path()
    if not steam_path:
        raise RuntimeError("Steam installation path not found")
    return os.path.join(steam_path, 'config')

def get_stplug_in_path() -> str:
    global _stplug_in_path_cache

    if _stplug_in_path_cache:
        return _stplug_in_path_cache

    config_path = get_steam_config_path()
    stplug_path = os.path.join(config_path, 'stplug-in')
    os.makedirs(stplug_path, exist_ok=True)
    _stplug_in_path_cache = stplug_path
    return stplug_path

def has_MLZ_for_app(appid: int) -> bool:
    try:
        base_path = detect_steam_install_path()
        if not base_path:
            return False

        stplug_path = os.path.join(base_path, 'config', 'stplug-in')
        lua_file = os.path.join(stplug_path, f'{appid}.lua')
        disabled_file = os.path.join(stplug_path, f'{appid}.lua.disabled')

        exists = os.path.exists(lua_file) or os.path.exists(disabled_file)
        return exists

    except Exception as e:
        logger.error(f'MLZCommunity (steam_utils): Error checking Lua scripts for app {appid}: {e}')
        return False

def list_MLZ_apps() -> list:
    try:
        base_path = detect_steam_install_path()
        if not base_path:
            return []

        stplug_path = os.path.join(base_path, 'config', 'stplug-in')
        if not os.path.exists(stplug_path):
            return []

        apps_mtime = {}
        for filename in os.listdir(stplug_path):
            if filename.endswith('.lua') or filename.endswith('.lua.disabled'):
                name = filename.split('.')[0]
                if not name.isdigit():
                    continue
                appid = int(name)
                path = os.path.join(stplug_path, filename)
                try:
                    mtime = os.path.getmtime(path)
                    apps_mtime[appid] = mtime
                except Exception:
                    continue

        return sorted(apps_mtime.keys(), key=lambda a: apps_mtime[a], reverse=True)

    except Exception as e:
        logger.error(f'MLZCommunity (steam_utils): list_lua_apps failed: {e}')
        return []


# ==================== Token Configuration Functions ====================

def _parse_vdf_simple(content: str) -> dict:
    """Simple VDF parser for Steam config files."""
    result = {}
    stack = [result]
    lines = content.replace('\r\n', '\n').split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        
        if line == '{':
            continue
        elif line == '}':
            if len(stack) > 1:
                stack.pop()
            continue
        
        # Parse key-value pairs
        parts = []
        in_quote = False
        current = ''
        for char in line:
            if char == '"':
                if in_quote:
                    parts.append(current)
                    current = ''
                in_quote = not in_quote
            elif in_quote:
                current += char
        
        if len(parts) >= 2:
            key, value = parts[0], parts[1]
            stack[-1][key] = value
        elif len(parts) == 1:
            key = parts[0]
            new_dict = {}
            stack[-1][key] = new_dict
            stack.append(new_dict)
    
    return result


def get_game_install_path(appid: int) -> dict:
    """Find the game installation path for a given appid."""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}
    
    steam_path = detect_steam_install_path()
    if not steam_path:
        return {"success": False, "error": "Could not find Steam installation path"}
    
    library_vdf_path = os.path.join(steam_path, "config", "libraryfolders.vdf")
    if not os.path.exists(library_vdf_path):
        return {"success": False, "error": "Could not find libraryfolders.vdf"}
    
    try:
        with open(library_vdf_path, "r", encoding="utf-8") as handle:
            vdf_content = handle.read()
        library_data = _parse_vdf_simple(vdf_content)
    except Exception as exc:
        return {"success": False, "error": f"Failed to parse libraryfolders.vdf: {exc}"}
    
    library_folders = library_data.get("libraryfolders", {})
    library_path = None
    appid_str = str(appid)
    all_library_paths = []
    
    for folder_data in library_folders.values():
        if isinstance(folder_data, dict):
            folder_path = folder_data.get("path", "")
            if folder_path:
                folder_path = folder_path.replace("\\\\", "\\")
                all_library_paths.append(folder_path)
            
            apps = folder_data.get("apps", {})
            if isinstance(apps, dict) and appid_str in apps:
                library_path = folder_path
                break
    
    # Search all libraries for appmanifest
    appmanifest_path = None
    if not library_path:
        for lib_path in all_library_paths:
            candidate_path = os.path.join(lib_path, "steamapps", f"appmanifest_{appid}.acf")
            if os.path.exists(candidate_path):
                library_path = lib_path
                appmanifest_path = candidate_path
                break
    else:
        appmanifest_path = os.path.join(library_path, "steamapps", f"appmanifest_{appid}.acf")
    
    if not library_path or not appmanifest_path or not os.path.exists(appmanifest_path):
        return {"success": False, "error": "اللعبة غير مثبتة"}
    
    try:
        with open(appmanifest_path, "r", encoding="utf-8") as handle:
            manifest_content = handle.read()
        manifest_data = _parse_vdf_simple(manifest_content)
    except Exception as exc:
        return {"success": False, "error": f"Failed to parse appmanifest: {exc}"}
    
    app_state = manifest_data.get("AppState", {})
    install_dir = app_state.get("installdir", "")
    if not install_dir:
        return {"success": False, "error": "Install directory not found"}
    
    full_install_path = os.path.join(library_path, "steamapps", "common", install_dir)
    if not os.path.exists(full_install_path):
        return {"success": False, "error": "Game directory not found"}
    
    return {
        "success": True,
        "installPath": full_install_path,
        "installDir": install_dir,
        "libraryPath": library_path
    }


def search_config_file(game_path: str, filename: str = "configs.user.ini") -> dict:
    """Search for a config file in all subdirectories of the game path."""
    found_files = []
    
    try:
        for root, dirs, files in os.walk(game_path):
            if filename in files:
                full_path = os.path.join(root, filename)
                found_files.append(full_path)
        
        if found_files:
            return {
                "success": True,
                "files": found_files,
                "count": len(found_files)
            }
        else:
            return {
                "success": False,
                "error": f"File '{filename}' not found in game directory",
                "files": []
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "files": []
        }


def update_config_token(file_path: str, new_token: str) -> dict:
    """Update the token value in a config.user.ini file."""
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        
        # Read the file
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Find and update the token line
        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("token="):
                new_lines.append(f"token={new_token}\n")
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            return {"success": False, "error": "Token line not found in file"}
        
        # Write back the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        
        return {"success": True, "message": "Token updated successfully", "filePath": file_path}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_xinput_dll() -> dict:
    """Check if xinput1_4.dll exists in Steam directory"""
    try:
        steam_path = detect_steam_install_path()
        if not steam_path:
            return {"exists": False, "error": "Steam path not found"}
        
        xinput_path = os.path.join(steam_path, "xinput1_4.dll")
        exists = os.path.exists(xinput_path)
        
        return {
            "exists": exists,
            "steamPath": steam_path,
            "xinputPath": xinput_path
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


def install_xinput_dll(dll_content_base64: str) -> dict:
    """Install xinput1_4.dll to Steam directory from base64 content"""
    try:
        import base64
        
        steam_path = detect_steam_install_path()
        if not steam_path:
            return {"success": False, "error": "Steam path not found"}
        
        xinput_path = os.path.join(steam_path, "xinput1_4.dll")
        
        # Decode base64 content
        dll_content = base64.b64decode(dll_content_base64)
        
        # Write the file
        with open(xinput_path, "wb") as f:
            f.write(dll_content)
        
        return {
            "success": True,
            "message": "xinput1_4.dll installed successfully",
            "path": xinput_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def install_xinput_from_zip(zip_content_base64: str) -> dict:
    """Extract and install xinput1_4.dll from ZIP file to Steam directory"""
    try:
        import base64
        import zipfile
        import io
        import tempfile
        
        steam_path = detect_steam_install_path()
        if not steam_path:
            return {"success": False, "error": "Steam path not found"}
        
        # Decode base64 content
        zip_content = base64.b64decode(zip_content_base64)
        
        # Create a BytesIO object from the zip content
        zip_buffer = io.BytesIO(zip_content)
        
        # Open the zip file
        with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
            # Look for xinput1_4.dll in the zip
            xinput_found = False
            for file_info in zip_ref.infolist():
                if file_info.filename.lower().endswith('xinput1_4.dll'):
                    # Extract xinput1_4.dll to Steam directory
                    xinput_content = zip_ref.read(file_info.filename)
                    xinput_path = os.path.join(steam_path, "xinput1_4.dll")
                    
                    with open(xinput_path, "wb") as f:
                        f.write(xinput_content)
                    
                    xinput_found = True
                    break
            
            if not xinput_found:
                return {"success": False, "error": "xinput1_4.dll not found in ZIP file"}
        
        return {
            "success": True,
            "message": "xinput1_4.dll installed successfully from ZIP",
            "path": os.path.join(steam_path, "xinput1_4.dll")
        }
    except zipfile.BadZipFile:
        return {"success": False, "error": "Invalid ZIP file"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def download_and_install_xinput() -> dict:
    """Download xinput1_4.dll from GitHub and install to Steam directory"""
    try:
        import urllib.request
        import ssl
        
        steam_path = detect_steam_install_path()
        if not steam_path:
            return {"success": False, "error": "Steam path not found"}
        
        # GitHub URL for the DLL file (raw download)
        dll_url = "https://github.com/MDQI1/MLZTools/raw/main/xinput1_4.dll"
        
        # Create SSL context that doesn't verify certificates (for compatibility)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Download the DLL file
        request = urllib.request.Request(dll_url, headers={'User-Agent': 'MLZTools/1.0'})
        with urllib.request.urlopen(request, context=ssl_context, timeout=30) as response:
            dll_content = response.read()
        
        # Write the DLL to Steam directory
        xinput_path = os.path.join(steam_path, "xinput1_4.dll")
        with open(xinput_path, "wb") as f:
            f.write(dll_content)
        
        return {
            "success": True,
            "message": "xinput1_4.dll installed successfully",
            "path": xinput_path
        }
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Download failed: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
