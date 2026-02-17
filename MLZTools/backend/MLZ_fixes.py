"""
═════════════════════════════════════════════════════════════
  MLZ on Top
  
  Developer: MLZ Community
  Discord: https://discord.gg/plr
  © 2026 MLZ Community - All Rights Reserved
═════════════════════════════════════════════════════════════
"""

import os
import json
import threading
import zipfile
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional
import PluginUtils
from MLZ_steam import get_game_install_path

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None
    HTTPX_AVAILABLE = False

logger = PluginUtils.Logger()

# حالات الإصلاح
FIX_DOWNLOAD_STATE: Dict[int, Dict[str, Any]] = {}
FIX_DOWNLOAD_LOCK = threading.Lock()
UNFIX_STATE: Dict[int, Dict[str, Any]] = {}
UNFIX_LOCK = threading.Lock()

# ═══════════════════════════════════════════════════════════
#              نظام ملفات التفعيل (Activation Files)
# ═══════════════════════════════════════════════════════════

# GitHub Token للوصول للمستودع الخاص
ACTIVATION_GITHUB_TOKEN = "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"

# رابط GitHub لملفات التفعيل (مستودع خاص - استخدام API للتحميل)
ACTIVATION_GITHUB_API_URL = "https://api.github.com/repos/MDQI1/MLZActivations/contents/{appid}.zip"
ACTIVATION_GITHUB_RAW_URL = "https://raw.githubusercontent.com/MDQI1/MLZActivations/main/{appid}.zip"

# قائمة الألعاب التي لديها ملفات تفعيل
def is_denuvo_game(appid: int, denuvo_flag: bool = False, denuvo_title: str = "") -> bool:
    """تحقق إذا كانت اللعبة محمية Denuvo"""
    return denuvo_flag or ("denuvo" in denuvo_title.lower())

def get_activation_status_for_game(appid: int, denuvo_flag: bool = False, denuvo_title: str = "") -> dict:
    """إرجاع حالة التفعيل للعبة Denuvo"""
    is_denuvo = is_denuvo_game(appid, denuvo_flag, denuvo_title)
    is_available = appid in ACTIVATION_APPIDS
    if is_denuvo:
        if is_available:
            return {
                "status": "available",
                "message": "تم اكتشاف حماية Denuvo، التفعيل متوفر لهذه اللعبة."
            }
        else:
            return {
                "status": "not_available",
                "message": "اللعبة محمية Denuvo، التفعيل غير متوفر لهذه اللعبة حالياً."
            }
    else:
        return {
            "status": "not_denuvo",
            "message": "اللعبة غير محمية Denuvo."
        }
ACTIVATION_APPIDS = {
    # Steam Games
    2358720,   # Black Myth Wukong
    703080,    # Planet Zoo
    3489700,   # Stellar Blade
    2486820,   # Sonic Racing: CrossWorlds
    2680010,   # The First Berserker: Khazan
    2928600,   # Demon Slayer -Kimetsu no Yaiba- The Hinokami Chronicles 2
    2958130,   # Jurassic World Evolution 3
    2050650,   # Resident Evil 4 Remake
    1941540,   # Mafia: The Old Country
    # Ubisoft Games
    3159330,   # Assassin's Creed Shadows
    3035570,   # Assassin's Creed Mirage
    2840770,   # Avatar Frontiers of Pandora
    2842040,   # Star Wars Outlaws
}

# ألعاب تحتاج معالجة خاصة للمسار (Unreal Engine games)
# المفتاح = AppID، القيمة = المسار الفرعي الذي يجب البحث عنه
SPECIAL_PATH_GAMES = {
    1941540: {  # Mafia: The Old Country
        "search_path": "Engine\\Binaries\\ThirdParty\\Steamworks\\Steamv157\\Win64",
        "go_back_to": "Engine",  # ارجع للمجلد الرئيسي قبل هذا المسار
        "game_folder": "Mafia The Old Country",  # اسم مجلد اللعبة للبحث في الأقراص
    }
}


def _find_game_in_all_drives(game_folder_name: str, search_subpath: str, exclude_paths: list = None) -> str:
    """
    البحث عن مجلد اللعبة في جميع الأقراص
    مع استثناء مسارات معينة مثل SteamLibrary
    """
    if exclude_paths is None:
        exclude_paths = ["SteamLibrary"]
    
    drives = ["C:\\", "D:\\", "E:\\", "F:\\", "G:\\", "H:\\"]
    
    for drive in drives:
        if not os.path.exists(drive):
            continue
        
        try:
            # البحث في المجلدات الرئيسية للقرص
            for root, dirs, files in os.walk(drive):
                # استثناء المسارات المحددة
                skip = False
                for exclude in exclude_paths:
                    if exclude.lower() in root.lower():
                        skip = True
                        break
                
                if skip:
                    # تجاهل الدخول في المجلدات المستثناة
                    dirs[:] = []
                    continue
                
                # فحص إذا كان المجلد الحالي هو مجلد اللعبة
                if game_folder_name.lower() in os.path.basename(root).lower():
                    # فحص إذا كان المسار الفرعي موجود
                    full_search_path = os.path.join(root, search_subpath)
                    if os.path.exists(full_search_path):
                        logger.log(f"MLZCommunity: Found game at {root}")
                        return root
                
                # الحد من البحث العميق جداً
                if root.count(os.sep) > 10:
                    dirs[:] = []
                    continue
                    
        except PermissionError:
            continue
        except Exception as e:
            logger.warn(f"MLZCommunity: Error searching in {drive}: {e}")
            continue
    
    return None


# حالة تحميل ملفات التفعيل
ACTIVATION_DOWNLOAD_STATE: Dict[int, Dict[str, Any]] = {}
ACTIVATION_DOWNLOAD_LOCK = threading.Lock()


def _set_activation_state(appid: int, update: dict) -> None:
    with ACTIVATION_DOWNLOAD_LOCK:
        state = ACTIVATION_DOWNLOAD_STATE.get(appid) or {}
        state.update(update)
        ACTIVATION_DOWNLOAD_STATE[appid] = state


def _get_activation_state(appid: int) -> dict:
    with ACTIVATION_DOWNLOAD_LOCK:
        return ACTIVATION_DOWNLOAD_STATE.get(appid, {}).copy()


def _set_fix_download_state(appid: int, update: dict) -> None:
    with FIX_DOWNLOAD_LOCK:
        state = FIX_DOWNLOAD_STATE.get(appid) or {}
        state.update(update)
        FIX_DOWNLOAD_STATE[appid] = state


def _get_fix_download_state(appid: int) -> dict:
    with FIX_DOWNLOAD_LOCK:
        return FIX_DOWNLOAD_STATE.get(appid, {}).copy()


def _set_unfix_state(appid: int, update: dict) -> None:
    with UNFIX_LOCK:
        state = UNFIX_STATE.get(appid) or {}
        state.update(update)
        UNFIX_STATE[appid] = state


def _get_unfix_state(appid: int) -> dict:
    with UNFIX_LOCK:
        return UNFIX_STATE.get(appid, {}).copy()


def _ensure_http_client():
    """إنشاء HTTP client"""
    if not HTTPX_AVAILABLE:
        return None
    return httpx.Client(timeout=30.0, follow_redirects=True)


def check_available_fixes(appid: int) -> Dict[str, Any]:
    """فحص الإصلاحات المتوفرة للعبة من Generic Fix"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    result = {
        "success": True,
        "appid": appid,
        "gameName": f"Game {appid}",
        "genericFix": {"status": 0, "available": False},
    }

    client = _ensure_http_client()
    if not client:
        return {"success": False, "error": "HTTP client not available"}

    try:
        # فحص Generic Fix API
        try:
            generic_url = f"https://files.MLZtools.work/GameBypasses/{appid}.zip"
            resp = client.head(generic_url, follow_redirects=True, timeout=10)
            result["genericFix"]["status"] = resp.status_code
            result["genericFix"]["available"] = resp.status_code == 200
            if resp.status_code == 200:
                result["genericFix"]["url"] = generic_url
            logger.log(f"MLZCommunity: Generic fix check for {appid} -> {resp.status_code}")
        except Exception as exc:
            logger.warn(f"MLZCommunity: Generic fix check failed for {appid}: {exc}")

    finally:
        client.close()

    return result


def _download_and_extract_fix(appid: int, download_url: str, install_path: str, fix_type: str, game_name: str = ""):
    """تحميل واستخراج الإصلاح"""
    client = _ensure_http_client()
    if not client:
        _set_fix_download_state(appid, {"status": "failed", "error": "HTTP client not available"})
        return

    try:
        dest_root = tempfile.gettempdir()
        dest_zip = os.path.join(dest_root, f"MLZ_fix_{appid}.zip")
        _set_fix_download_state(appid, {"status": "downloading", "bytesRead": 0, "totalBytes": 0, "error": None})

        logger.log(f"MLZCommunity: Downloading {fix_type} from {download_url}")

        with client.stream("GET", download_url, follow_redirects=True, timeout=120) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", "0") or "0")
            _set_fix_download_state(appid, {"totalBytes": total})

            with open(dest_zip, "wb") as output:
                for chunk in resp.iter_bytes():
                    if not chunk:
                        continue
                    state = _get_fix_download_state(appid)
                    if state.get("status") == "cancelled":
                        logger.log(f"MLZCommunity: Fix download cancelled for {appid}")
                        raise RuntimeError("cancelled")
                    output.write(chunk)
                    read = int(state.get("bytesRead", 0)) + len(chunk)
                    _set_fix_download_state(appid, {"bytesRead": read})

        logger.log(f"MLZCommunity: Download complete, extracting to {install_path}")
        _set_fix_download_state(appid, {"status": "extracting"})

        extracted_files = []
        with zipfile.ZipFile(dest_zip, "r") as archive:
            all_names = archive.namelist()
            appid_folder = f"{appid}/"

            # فحص هيكل الملف المضغوط
            top_level_entries = set()
            for name in all_names:
                parts = name.split("/")
                if parts[0]:
                    top_level_entries.add(parts[0])

            if state.get("status") == "cancelled":
                raise RuntimeError("cancelled")

            # إذا كان الملف المضغوط يحتوي على مجلد بنفس اسم الـ appid
            if len(top_level_entries) == 1 and appid_folder.rstrip("/") in top_level_entries:
                logger.log(f"MLZCommunity: Found single folder {appid} in zip, extracting contents")
                for member in archive.namelist():
                    if member.startswith(appid_folder) and member != appid_folder:
                        target_path = member[len(appid_folder):]
                        if not target_path:
                            continue
                        source = archive.open(member)
                        target = os.path.join(install_path, target_path)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        if not member.endswith("/"):
                            with open(target, "wb") as output:
                                output.write(source.read())
                            extracted_files.append(target_path.replace("\\", "/"))
                        source.close()
            else:
                logger.log(f"MLZCommunity: Extracting all zip contents to {install_path}")
                for member in archive.namelist():
                    if member.endswith("/"):
                        continue
                    archive.extract(member, install_path)
                    extracted_files.append(member.replace("\\", "/"))

        # سجل الإصلاح (تم تعطيله للنسخة النهائية)
        # log_file_path = os.path.join(install_path, f"MLZ-fix-log-{appid}.log")

        logger.log(f"MLZCommunity: {fix_type} applied successfully to {install_path}")
        _set_fix_download_state(appid, {"status": "done", "success": True})

        # تنظيف
        try:
            os.remove(dest_zip)
        except:
            pass

    except Exception as exc:
        if str(exc) == "cancelled":
            try:
                if os.path.exists(dest_zip):
                    os.remove(dest_zip)
            except:
                pass
            _set_fix_download_state(appid, {"status": "cancelled", "success": False, "error": "Cancelled by user"})
            return
        logger.warn(f"MLZCommunity: Failed to apply fix: {exc}")
        _set_fix_download_state(appid, {"status": "failed", "error": str(exc)})
    finally:
        client.close()


def apply_game_fix(appid: int, downloadUrl: str, installPath: str, fixType: str = "", gameName: str = "") -> Dict[str, Any]:
    """تطبيق إصلاح على اللعبة"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    if not downloadUrl or not installPath:
        return {"success": False, "error": "Missing download URL or install path"}

    if not os.path.exists(installPath):
        return {"success": False, "error": "Install path does not exist"}

    logger.log(f"MLZCommunity: ApplyGameFix appid={appid}, fixType={fixType}")

    _set_fix_download_state(appid, {"status": "queued", "bytesRead": 0, "totalBytes": 0, "error": None})
    thread = threading.Thread(
        target=_download_and_extract_fix,
        args=(appid, downloadUrl, installPath, fixType, gameName),
        daemon=True
    )
    thread.start()

    return {"success": True}


def get_fix_status(appid: int) -> Dict[str, Any]:
    """الحصول على حالة تحميل الإصلاح"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    state = _get_fix_download_state(appid)
    return {"success": True, "state": state}


def cancel_fix(appid: int) -> Dict[str, Any]:
    """إلغاء تحميل الإصلاح"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    state = _get_fix_download_state(appid)
    if not state or state.get("status") in {"done", "failed"}:
        return {"success": True, "message": "Nothing to cancel"}

    _set_fix_download_state(appid, {"status": "cancelled", "success": False, "error": "Cancelled by user"})
    logger.log(f"MLZCommunity: CancelFix requested for appid={appid}")
    return {"success": True}


def _unfix_game_worker(appid: int, install_path: str, fix_date: str = None):
    """إزالة الإصلاح من اللعبة"""
    try:
        logger.log(f"MLZCommunity: Starting un-fix for appid {appid}")
        log_file_path = os.path.join(install_path, f"MLZ-fix-log-{appid}.log")

        if not os.path.exists(log_file_path):
            _set_unfix_state(appid, {"status": "failed", "error": "No fix log found. Cannot un-fix."})
            return

        _set_unfix_state(appid, {"status": "removing", "progress": "Reading log file..."})

        files_to_delete = set()
        remaining_fixes = []

        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                log_content = f.read()

            if "[FIX]" in log_content:
                fix_blocks = log_content.split("[FIX]")
                for block in fix_blocks:
                    if not block.strip():
                        continue

                    lines = block.split("\n")
                    in_files_section = False
                    block_date = None
                    block_lines = []

                    for line in lines:
                        line_stripped = line.strip()
                        if line_stripped == "[/FIX]" or line_stripped == "---":
                            break
                        if line_stripped.startswith("Date:"):
                            block_date = line_stripped.replace("Date:", "").strip()

                        block_lines.append(line)

                        if line_stripped == "Files:":
                            in_files_section = True
                        elif in_files_section and line_stripped:
                            if fix_date is None or (block_date and block_date == fix_date):
                                files_to_delete.add(line_stripped)

                    if fix_date is not None and block_date and block_date != fix_date:
                        remaining_fixes.append("[FIX]\n" + "\n".join(block_lines) + "\n[/FIX]")
            else:
                lines = log_content.split("\n")
                in_files_section = False
                for line in lines:
                    line = line.strip()
                    if line == "Files:":
                        in_files_section = True
                    elif in_files_section and line:
                        files_to_delete.add(line)

            logger.log(f"MLZCommunity: Found {len(files_to_delete)} files to remove")
        except Exception as e:
            logger.warn(f"MLZCommunity: Failed to read log file: {e}")
            _set_unfix_state(appid, {"status": "failed", "error": f"Failed to read log file: {str(e)}"})
            return

        _set_unfix_state(appid, {"status": "removing", "progress": f"Removing {len(files_to_delete)} files..."})
        deleted_count = 0
        for file_path in files_to_delete:
            try:
                full_path = os.path.join(install_path, file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    deleted_count += 1
                    logger.log(f"MLZCommunity: Deleted {file_path}")
            except Exception as e:
                logger.warn(f"MLZCommunity: Failed to delete {file_path}: {e}")

        logger.log(f"MLZCommunity: Deleted {deleted_count}/{len(files_to_delete)} files")

        if remaining_fixes:
            try:
                with open(log_file_path, "w", encoding="utf-8") as f:
                    f.write("\n\n---\n\n".join(remaining_fixes))
                logger.log(f"MLZCommunity: Updated log file, {len(remaining_fixes)} fixes remaining")
            except Exception as e:
                logger.warn(f"MLZCommunity: Failed to update log file: {e}")
        else:
            try:
                os.remove(log_file_path)
                logger.log(f"MLZCommunity: Deleted log file {log_file_path}")
            except Exception as e:
                logger.warn(f"MLZCommunity: Failed to delete log file: {e}")

        _set_unfix_state(appid, {"status": "done", "success": True, "filesRemoved": deleted_count})

    except Exception as e:
        logger.warn(f"MLZCommunity: Un-fix failed: {e}")
        _set_unfix_state(appid, {"status": "failed", "error": str(e)})


def unfix_game(appid: int, installPath: str = "", fixDate: str = "") -> Dict[str, Any]:
    """إزالة الإصلاح واستعادة الملفات الأصلية"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    resolved_path = installPath
    if not resolved_path:
        try:
            result = get_game_install_path(appid)
            if not result.get("success") or not result.get("installPath"):
                return {"success": False, "error": "Could not find game install path"}
            resolved_path = result["installPath"]
        except Exception as e:
            return {"success": False, "error": f"Failed to get install path: {str(e)}"}

    if not os.path.exists(resolved_path):
        return {"success": False, "error": "Install path does not exist"}

    logger.log(f"MLZCommunity: UnFixGame appid={appid}, path={resolved_path}")

    _set_unfix_state(appid, {"status": "queued", "progress": "", "error": None})
    thread = threading.Thread(
        target=_unfix_game_worker,
        args=(appid, resolved_path, fixDate or None),
        daemon=True
    )
    thread.start()

    return {"success": True}


def get_unfix_status(appid: int) -> Dict[str, Any]:
    """الحصول على حالة إزالة الإصلاح"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    state = _get_unfix_state(appid)
    return {"success": True, "state": state}


def open_game_folder(path: str) -> Dict[str, Any]:
    """فتح مجلد اللعبة"""
    try:
        if path and os.path.exists(path):
            os.startfile(path)
            return {"success": True, "path": path}
        else:
            return {"success": False, "error": "المسار غير موجود"}
    except Exception as e:
        logger.error(f"MLZCommunity: Error opening folder: {e}")
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
#              دوال ملفات التفعيل (Activation Files API)
# ═══════════════════════════════════════════════════════════

def check_activation_files(appid: int) -> Dict[str, Any]:
    """فحص توفر ملفات التفعيل للعبة"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    # فحص إذا كانت اللعبة في قائمة الألعاب المدعومة
    if appid not in ACTIVATION_APPIDS:
        return {
            "success": True,
            "appid": appid,
            "available": False,
            "reason": "Game not in activation list"
        }

    # فحص توفر الملف على GitHub
    client = _ensure_http_client()
    if not client:
        return {"success": False, "error": "HTTP client not available"}

    try:
        download_url = ACTIVATION_GITHUB_RAW_URL.format(appid=appid)
        
        # إضافة التوكن للوصول للمستودع الخاص
        headers = {
            "Authorization": f"token {ACTIVATION_GITHUB_TOKEN}",
            "Accept": "application/octet-stream"
        }
        
        resp = client.head(download_url, headers=headers, follow_redirects=True, timeout=10)
        
        available = resp.status_code == 200
        
        logger.log(f"MLZCommunity: Activation files check for {appid} -> {resp.status_code}")
        
        return {
            "success": True,
            "appid": appid,
            "available": available,
            "url": download_url if available else None,
            "status_code": resp.status_code
        }
    except Exception as e:
        logger.warn(f"MLZCommunity: Activation files check failed for {appid}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        client.close()


def _download_activation_files_worker(appid: int, install_path: str):
    """تحميل واستخراج ملفات التفعيل"""
    client = _ensure_http_client()
    if not client:
        _set_activation_state(appid, {"status": "failed", "error": "HTTP client not available"})
        return

    try:
        download_url = ACTIVATION_GITHUB_RAW_URL.format(appid=appid)
        dest_zip = os.path.join(tempfile.gettempdir(), f"MLZ_activation_{appid}.zip")
        
        _set_activation_state(appid, {
            "status": "downloading",
            "bytesRead": 0,
            "totalBytes": 0,
            "error": None
        })

        logger.log(f"MLZCommunity: Downloading activation files from {download_url}")

        # إضافة التوكن للوصول للمستودع الخاص
        headers = {
            "Authorization": f"token {ACTIVATION_GITHUB_TOKEN}",
            "Accept": "application/octet-stream"
        }

        # تحديد مسار الاستخراج النهائي - معالجة خاصة لبعض الألعاب
        final_install_path = install_path
        if appid in SPECIAL_PATH_GAMES:
            special_config = SPECIAL_PATH_GAMES[appid]
            search_path = special_config.get("search_path", "")
            go_back_to = special_config.get("go_back_to", "")
            game_folder = special_config.get("game_folder", "")
            
            # أولاً: محاولة البحث في مجلد اللعبة المعطى
            found_special_path = None
            for root, dirs, files in os.walk(install_path):
                if search_path in root.replace("/", "\\"):
                    found_special_path = root
                    break
            
            # ثانياً: إذا لم يوجد، البحث في جميع الأقراص (ماعدا SteamLibrary)
            if not found_special_path and game_folder:
                logger.log(f"MLZCommunity: Path not found in install_path, searching all drives for '{game_folder}'...")
                _set_activation_state(appid, {"status": "searching", "message": "Searching for game in all drives..."})
                
                found_game_path = _find_game_in_all_drives(game_folder, search_path, exclude_paths=["SteamLibrary"])
                if found_game_path:
                    install_path = found_game_path
                    # البحث مرة أخرى في المسار الجديد
                    for root, dirs, files in os.walk(install_path):
                        if search_path in root.replace("/", "\\"):
                            found_special_path = root
                            break
            
            if found_special_path and go_back_to:
                # الرجوع للمجلد الرئيسي قبل go_back_to
                path_parts = found_special_path.replace("/", "\\").split("\\")
                if go_back_to in path_parts:
                    idx = path_parts.index(go_back_to)
                    final_install_path = "\\".join(path_parts[:idx])
                    logger.log(f"MLZCommunity: Special path game detected. Installing to: {final_install_path}")
                else:
                    logger.log(f"MLZCommunity: Could not find '{go_back_to}' in path, using original: {install_path}")
            else:
                logger.log(f"MLZCommunity: Special search path not found, using original: {install_path}")

        with client.stream("GET", download_url, headers=headers, follow_redirects=True, timeout=120) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", "0") or "0")
            _set_activation_state(appid, {"totalBytes": total})

            with open(dest_zip, "wb") as output:
                downloaded = 0
                for chunk in resp.iter_bytes():
                    if not chunk:
                        continue
                    
                    state = _get_activation_state(appid)
                    if state.get("status") == "cancelled":
                        logger.log(f"MLZCommunity: Activation download cancelled for {appid}")
                        raise RuntimeError("cancelled")
                    
                    output.write(chunk)
                    downloaded += len(chunk)
                    _set_activation_state(appid, {"bytesRead": downloaded})

        logger.log(f"MLZCommunity: Download complete, extracting to {final_install_path}")
        _set_activation_state(appid, {"status": "extracting"})

        # استخراج الملفات
        extracted_files = []
        with zipfile.ZipFile(dest_zip, "r") as archive:
            all_names = archive.namelist()
            
            # فحص هيكل الملف المضغوط
            top_level_entries = set()
            for name in all_names:
                parts = name.split("/")
                if parts[0]:
                    top_level_entries.add(parts[0])

            # إذا كان هناك مجلد رئيسي واحد باسم الـ appid
            appid_folder = f"{appid}/"
            if len(top_level_entries) == 1 and appid_folder.rstrip("/") in top_level_entries:
                logger.log(f"MLZCommunity: Found folder {appid} in zip, extracting contents")
                for member in archive.namelist():
                    if member.startswith(appid_folder) and member != appid_folder:
                        target_path = member[len(appid_folder):]
                        if not target_path:
                            continue
                        source = archive.open(member)
                        target = os.path.join(final_install_path, target_path)
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        if not member.endswith("/"):
                            with open(target, "wb") as output:
                                output.write(source.read())
                            extracted_files.append(target_path.replace("\\", "/"))
                        source.close()
            else:
                # استخراج مباشر
                logger.log(f"MLZCommunity: Extracting all contents to {final_install_path}")
                for member in archive.namelist():
                    if member.endswith("/"):
                        continue
                    archive.extract(member, final_install_path)
                    extracted_files.append(member.replace("\\", "/"))

        # سجل التفعيل (تم تعطيله للنسخة النهائية)
        # log_file_path = os.path.join(final_install_path, f"MLZ-activation-log-{appid}.log")

        logger.log(f"MLZCommunity: Activation files applied successfully to {final_install_path}")
        _set_activation_state(appid, {
            "status": "done",
            "success": True,
            "filesExtracted": len(extracted_files)
        })

        # تنظيف
        try:
            os.remove(dest_zip)
        except:
            pass

    except Exception as exc:
        if str(exc) == "cancelled":
            try:
                if os.path.exists(dest_zip):
                    os.remove(dest_zip)
            except:
                pass
            _set_activation_state(appid, {"status": "cancelled", "success": False, "error": "Cancelled by user"})
            return
        logger.warn(f"MLZCommunity: Failed to download activation files: {exc}")
        _set_activation_state(appid, {"status": "failed", "error": str(exc)})
    finally:
        client.close()


def download_activation_files(appid: int, installPath: str) -> Dict[str, Any]:
    """بدء تحميل ملفات التفعيل"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    if appid not in ACTIVATION_APPIDS:
        return {"success": False, "error": "Game not in activation list"}

    if not installPath or not os.path.exists(installPath):
        return {"success": False, "error": "Install path does not exist"}

    logger.log(f"MLZCommunity: Starting activation download for appid={appid}")

    _set_activation_state(appid, {"status": "queued", "bytesRead": 0, "totalBytes": 0, "error": None})
    
    thread = threading.Thread(
        target=_download_activation_files_worker,
        args=(appid, installPath),
        daemon=True
    )
    thread.start()

    return {"success": True}


def get_activation_status(appid: int) -> Dict[str, Any]:
    """الحصول على حالة تحميل ملفات التفعيل"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    state = _get_activation_state(appid)
    return {"success": True, "state": state}


def cancel_activation_download(appid: int) -> Dict[str, Any]:
    """إلغاء تحميل ملفات التفعيل"""
    try:
        appid = int(appid)
    except Exception:
        return {"success": False, "error": "Invalid appid"}

    state = _get_activation_state(appid)
    if not state or state.get("status") in {"done", "failed"}:
        return {"success": True, "message": "Nothing to cancel"}

    _set_activation_state(appid, {"status": "cancelled", "success": False, "error": "Cancelled by user"})
    logger.log(f"MLZCommunity: Activation download cancelled for appid={appid}")
    return {"success": True}
