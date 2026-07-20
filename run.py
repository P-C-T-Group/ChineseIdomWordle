# -- coding: utf-8 --
'''
run.py
统一程序入口 - 同时支持后端API模式和全栈（前端静态文件+后端API）模式
(c) 2026 P.C.T.G. MIT License.
CODEOWNERS: @GZYZhy
'''

# import os
import sys
import hashlib
import subprocess
import re
import argparse
from pathlib import Path

# 将 backend 目录加入 Python 路径（run.py 现在在项目根目录）
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def get_token_sha256(raw_token: str) -> str:
    """计算 token 的 SHA256 摘要"""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def is_initialized() -> bool:
    """检查是否已完成初始化"""
    init_marker = BACKEND_DIR / ".initialized"
    if not init_marker.exists():
        return False
    # 读取标记中的配置指纹，若配置变更则需要重新初始化
    try:
        from app.core.config import get_settings
        settings = get_settings()
        current_fingerprint = f"{settings.frontend.front_mode.value}:{settings.frontend.listen_host}:{settings.frontend.front_token}"
        with open(init_marker, "r", encoding="utf-8") as f:
            saved_fingerprint = f.read().strip()
        return saved_fingerprint == current_fingerprint
    except Exception:
        return False


def mark_initialized():
    """标记初始化完成"""
    from app.core.config import get_settings
    settings = get_settings()
    current_fingerprint = f"{settings.frontend.front_mode.value}:{settings.frontend.listen_host}:{settings.frontend.front_token}"
    init_marker = BACKEND_DIR / ".initialized"
    with open(init_marker, "w", encoding="utf-8") as f:
        f.write(current_fingerprint)


def clear_initialized_marker():
    """清除初始化标记（强制重新初始化，不影响数据库数据）"""
    init_marker = BACKEND_DIR / ".initialized"
    if init_marker.exists():
        init_marker.unlink()
        print("[初始化] 已清除初始化标记，下次启动将重新初始化前端配置")


def restore_js_from_backup(file_path: Path) -> bool:
    """从.backup文件恢复原始JS，返回是否成功恢复"""
    backup_path = file_path.with_suffix(file_path.suffix + ".backup")
    if backup_path.exists():
        try:
            import shutil
            shutil.copy2(backup_path, file_path)
            return True
        except Exception:
            return False
    return False


def process_single_js(file_path: Path, base_url: str, token: str, restore_first: bool = False) -> tuple[bool, int]:
    """处理单个JS文件：替换URL和Token，返回(是否变更, 替换Token数量)

    Args:
        restore_first: 是否先从.backup恢复原始文件（重新初始化时需要）
    """
    if not file_path.exists():
        print(f"  ⚠️  找不到文件: {file_path.name}")
        return False, 0

    # 如果需要恢复且有备份，先恢复原始JS
    if restore_first:
        restored = restore_js_from_backup(file_path)
        if restored:
            print(f"  ↳ 已从备份恢复原始文件: {file_path.name}.backup")

    with open(file_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    original_code = js_code

    # 1. 替换 API Base URL
    # 匹配模式：//host:port 或 http://host:port 或 https://host:port
    default_base_pattern = r"(?:https?:)?//127\.0\.0\.1(?::\d+)?"
    if base_url:
        new_base = f"//{base_url}"
        js_code = re.sub(default_base_pattern, new_base, js_code)
    else:
        # default 模式同域部署，使用相对路径
        js_code = re.sub(default_base_pattern, "", js_code)

    # 2. 替换 Bearer Token
    token_pattern = r"'Bearer ([^']+)'"
    matches = re.findall(token_pattern, js_code)
    js_code = re.sub(token_pattern, f"'Bearer {token}'", js_code)
    token_count = len(matches)

    changed = js_code != original_code
    if changed:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(js_code)

    return changed, token_count


def obfuscate_single_js(file_path: Path, tool_dir: Path, obfuscator_path: Path) -> bool:
    """混淆单个JS文件"""
    import json
    if not obfuscator_path.exists():
        return False

    try:
        obf_config = {
            "compact": True,
            "simplify": True,
            "identifierNamesGenerator": "hexadecimal",
            "renameGlobals": False,
            "selfDefending": True,
            "debugProtection": False,
            "debugProtectionInterval": 0,
            "disableConsoleOutput": True,
            "controlFlowFlattening": False,
            "deadCodeInjection": False,
            "stringArray": True,
            "stringArrayEncoding": [],
            "stringArrayWrappersCount": 1,
            "stringArrayThreshold": 0.3,
            "target": "browser"
        }
        config_path = tool_dir / "obf_config_temp.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(obf_config, f)

        result = subprocess.run(
            [str(obfuscator_path), str(file_path), "--config",
             str(config_path), "--output", str(file_path)],
            capture_output=True,
            text=True,
            cwd=str(tool_dir)
        )

        config_path.unlink(missing_ok=True)
        return result.returncode == 0
    except Exception:
        return False


def obfuscate_frontend_js(base_url: str, token: str, restore_first: bool = False):
    """
    混淆前端 JS：替换 API Base URL 和 Token
    处理所有前端JS文件（包括排行榜等）

    Args:
        restore_first: 是否先从.backup文件恢复原始JS（重新初始化时用）
    """
    if restore_first:
        print("\n[初始化] 重新初始化模式：从备份恢复原始JS文件...")
    print("\n[初始化] 正在处理前端 JS 文件...")

    client_js_dir = PROJECT_ROOT / "client" / "js"

    # 需要处理的JS文件列表
    js_files = [
        client_js_dir / "indexScript.js",
        client_js_dir / "top.js",
        client_js_dir / "dialog.js",
        client_js_dir / "help.js",
    ]

    tool_dir = PROJECT_ROOT / "tool"
    obfuscator_path = tool_dir / "node_modules" / ".bin" / "javascript-obfuscator"
    has_obfuscator = obfuscator_path.exists()

    total_token_replacements = 0
    changed_files = 0
    restored_count = 0

    for js_file in js_files:
        rel_name = js_file.name
        changed, token_count = process_single_js(
            js_file, base_url, token, restore_first=restore_first)
        backup_exists = js_file.with_suffix(
            js_file.suffix + ".backup").exists()
        if restore_first and backup_exists:
            restored_count += 1
        total_token_replacements += token_count
        if changed:
            changed_files += 1
            print(f"  → {rel_name}: 已更新 (替换 {token_count} 处Token)")
        else:
            print(f"  → {rel_name}: 无需更新")

        # 混淆处理 - 安装了混淆器就重新混淆
        if has_obfuscator:
            obfuscate_ok = obfuscate_single_js(
                js_file, tool_dir, obfuscator_path)
            if obfuscate_ok:
                print("    ↳ 已混淆")

    if restore_first:
        print(f"\n  ℹ️  已从备份恢复 {restored_count} 个原始JS文件")
    if not has_obfuscator:
        print("\n  ℹ️  未安装 javascript-obfuscator，跳过混淆（仅替换 URL/Token）")
        print(f"    如需代码混淆，请在 {tool_dir}/ 目录执行 npm install")
    else:
        print("\n  ✅ 代码混淆完成")

    print(
        f"\n  汇总: 更新了 {changed_files}/{len(js_files)} 个文件，共替换 {total_token_replacements} 处Token配置")
    print("  💡 原始文件备份在同目录下，后缀为 .backup")
    return True


def add_front_token_to_db(token: str):
    """将前端 Token 添加到数据库合法 token 列表"""
    print("\n[初始化] 正在添加前端 Token 到数据库...")

    # 确保数据库已初始化
    from app.database.initDB import initDB
    initDB()

    from app.database import db_manager
    from app.core.config import get_settings

    settings = get_settings()
    token_hash = get_token_sha256(token)

    # 检查是否为管理员 Token
    admin_hash = settings.auth.admin_token_hash
    if admin_hash and token_hash == admin_hash:
        print("  → 前端 Token 与管理员 Token 相同，无需添加到数据库")
        return

    try:
        # 添加 token（永不过期，IP 不限制）
        db_manager.add_token(token_hash, creator_ip="system_init",
                             valid_until=None, whitelist_ips=None)
        print(f"  → Token 添加成功（SHA256: {token_hash[:16]}...）")
    except ValueError as e:
        if "管理员 Token 禁止写入数据库" in str(e):
            print("  → Token 已是管理员 Token，跳过")
        else:
            print(f"  → 添加失败: {e}")
    except Exception as e:
        print(f"  → 添加过程出错（非致命）: {e}")


def run_initialization(force: bool = False):
    """执行一次性初始化

    Args:
        force: 强制重新初始化（清除.initialized标记，从备份恢复原始JS后重新替换和混淆，不影响数据库数据）
    """
    if force:
        clear_initialized_marker()

    print("=" * 60)
    print("ChineseIdomWordle 统一入口 - " + ("重新初始化" if force else "初始化"))
    print("=" * 60)

    from app.core.config import get_settings
    settings = get_settings()

    frontend_cfg = settings.frontend
    print(f"\n[配置] 启动模式: {frontend_cfg.front_mode.value}")
    print(f"[配置] 监听地址: {frontend_cfg.host}:{frontend_cfg.port}")

    if frontend_cfg.front_mode.value == "default":
        # default 模式：同域部署，使用相对路径
        obfuscate_frontend_js(
            "", frontend_cfg.front_token, restore_first=force)
        # 添加 token 到数据库
        add_front_token_to_db(frontend_cfg.front_token)
    else:
        # backend 模式：API 独立部署，使用配置的地址
        print("\n[初始化] backend 模式：更新前端 JS API 地址...")
        obfuscate_frontend_js(frontend_cfg.api_base_url,
                              frontend_cfg.front_token, restore_first=force)
        # backend 模式也添加 token（方便前端直接连接）
        add_front_token_to_db(frontend_cfg.front_token)

    mark_initialized()
    print("\n[初始化] 完成 ✓")
    print("\nℹ️  提示: 如需重新初始化前端配置（不影响数据库数据），请运行:")
    print("   python run.py --reinit")
    print("\n📋 排行榜数据重置方法请见 config.toml 中 [leaderboard] 节的说明")


def create_app():
    """根据配置创建 FastAPI 应用"""
    from app.core.config import get_settings
    settings = get_settings()

    if settings.frontend.front_mode.value == "default":
        return create_fullstack_app(settings)
    else:
        # backend 模式直接使用 main.py 中的 app
        from app.main import app as backend_app
        return backend_app


def create_fullstack_app(settings):
    """创建全栈模式应用：静态文件 + API 同域部署"""
    from fastapi import Request
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from app.schemas.game import ErrorResponse

    # 直接导入已在 main.py 中完成所有初始化的 backend_app
    from app.main import app as full_app

    client_dir = PROJECT_ROOT / "client"
    well_known_dir = client_dir / ".well-known"

    # 安全拦截：禁止访问所有.backup备份文件
    @full_app.middleware("http")
    async def block_backup_files(request: Request, call_next):
        if request.url.path.endswith(".backup") or ".backup/" in request.url.path:
            return JSONResponse(
                status_code=403,
                content=ErrorResponse(
                    code=403, status="fail", message="Forbidden").model_dump()
            )
        return await call_next(request)

    if client_dir.exists():
        # 挂载静态资源目录
        full_app.mount(
            "/css", StaticFiles(directory=str(client_dir / "css")), name="css")
        full_app.mount(
            "/js", StaticFiles(directory=str(client_dir / "js")), name="js")
        full_app.mount(
            "/icons", StaticFiles(directory=str(client_dir / "icons")), name="icons")
        full_app.mount(
            "/help", StaticFiles(directory=str(client_dir / "help"), html=True), name="help")
        full_app.mount(
            "/top", StaticFiles(directory=str(client_dir / "top"), html=True), name="top")

        # 挂载.well-known目录（用于域名验证、SSL证书申请等，放在client目录下）
        if well_known_dir.exists() and well_known_dir.is_dir():
            full_app.mount(
                "/.well-known", StaticFiles(directory=str(well_known_dir)), name="well-known")

        # 根路由
        @full_app.get("/")
        async def root_page():
            return FileResponse(str(client_dir / "index.html"))

        # 静态文件兜底
        @full_app.get("/{file_path:path}")
        async def static_fallback(file_path: str, request: Request):
            from fastapi.responses import RedirectResponse

            # 再次检查禁止访问.backup文件
            if file_path.endswith(".backup"):
                return JSONResponse(
                    status_code=403,
                    content=ErrorResponse(
                        code=403, status="fail", message="Forbidden").model_dump()
                )

            file_fs_path = client_dir / file_path

            # 情况1: 如果是目录，返回目录下的index.html，或者重定向到带斜杠的路径
            if file_fs_path.is_dir():
                index_file = file_fs_path / "index.html"
                if index_file.is_file():
                    # 目录存在且有index.html
                    if not request.url.path.endswith('/'):
                        # 不带斜杠的目录访问，重定向到带斜杠
                        return RedirectResponse(url=f"/{file_path}/", status_code=301)
                    return FileResponse(str(index_file))

            # 情况2: 路径对应的文件存在，直接返回
            if file_fs_path.is_file():
                return FileResponse(str(file_fs_path))

            # 情况3: 尝试加.html后缀（支持不带后缀的路由）
            html_file = client_dir / f"{file_path}.html"
            if html_file.is_file():
                return FileResponse(str(html_file))

            # 404
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    code=404, status="fail", message="Not Found").model_dump()
            )

    return full_app


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="ChineseIdomWordle 统一启动入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py              # 正常启动（首次运行自动初始化）
  python run.py --reinit     # 重新初始化前端配置（不影响数据库数据）
  python run.py --help       # 显示帮助
        """
    )
    parser.add_argument(
        "--reinit",
        action="store_true",
        help="强制重新初始化前端配置（替换URL/Token，不清理数据库数据）"
    )
    args = parser.parse_args()

    # 初始化检查
    if args.reinit:
        run_initialization(force=True)
    elif not is_initialized():
        run_initialization()
    else:
        from app.core.config import get_settings
        settings = get_settings()
        print(
            f"[启动] 模式: {settings.frontend.front_mode.value}, 地址: {settings.frontend.host}:{settings.frontend.port}")

    # 创建应用
    app = create_app()

    # 获取监听配置
    from app.core.config import get_settings
    settings = get_settings()
    host = settings.frontend.host
    port = settings.frontend.port

    print(f"\n{'=' * 60}")
    print("服务启动中...")
    print(
        f"  模式: {'全栈模式（前端+后端）' if settings.frontend.front_mode.value == 'default' else '纯后端模式'}")
    print(f"  地址: http://{host}:{port}")
    if settings.frontend.front_mode.value == "default":
        print(f"  主页:  http://{host}:{port}/")
        print(f"  排行榜: http://{host}:{port}/top/")
        print(f"  帮助:  http://{host}:{port}/help/")
        print(f"  API:  http://{host}:{port}/api")
    else:
        print(f"  API:  http://{host}:{port}/")
        print(f"  文档: http://{host}:{port}/docs")
    print(f"{'=' * 60}\n")

    # 启动 uvicorn
    import uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_config=str(BACKEND_DIR / "uvicorn_config.json"),
        forwarded_allow_ips="*",
        server_header=False,
    )


if __name__ == "__main__":
    main()
