# -- coding: utf-8 --
'''
run.py
统一程序入口 - 同时支持后端API模式和全栈（前端静态文件+后端API）模式
(c) 2026 P.C.T.G. MIT License.
CODEOWNERS: @GZYZhy
'''

import os
import sys
import hashlib
import subprocess
import re
from pathlib import Path

# 将 backend 目录加入 Python 路径
BACKEND_DIR = Path(__file__).resolve().parent
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


def obfuscate_frontend_js(base_url: str, token: str):
    """
    混淆前端 JS：替换 API Base URL 和 Token
    复用 tool/obfuscate.js 的逻辑，通过 Python 直接处理避免交互式输入
    """
    print("\n[初始化] 正在处理前端 JS 文件...")

    # 目标 JS 文件路径
    target_file = BACKEND_DIR.parent / "client" / "js" / "indexScript.js"
    if not target_file.exists():
        print(f"[警告] 找不到前端 JS 文件: {target_file}")
        return False

    with open(target_file, "r", encoding="utf-8") as f:
        js_code = f.read()

    original_code = js_code

    # 1. 替换 API Base URL
    # 匹配模式：//host:port 或 //host（协议相对URL）
    default_base_pattern = r"//127\.0\.0\.1(?::\d+)?"
    if base_url:
        new_base = f"//{base_url}"
        js_code = re.sub(default_base_pattern, new_base, js_code)
        print(f"  → API Base URL: {new_base}")
    else:
        # default 模式同域部署，使用相对路径
        js_code = re.sub(default_base_pattern, "", js_code)
        print(f"  → API Base URL: (相对路径，同域部署)")

    # 2. 替换 Bearer Token
    token_pattern = r"'Bearer ([^']+)'"
    matches = re.findall(token_pattern, js_code)
    js_code = re.sub(token_pattern, f"'Bearer {token}'", js_code)
    print(f"  → Token: Bearer {token} (替换 {len(matches)} 处)")

    if js_code == original_code:
        print("  → JS 内容无需变更")
    else:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(js_code)
        print("  → JS 文件已更新")

    # 3. 尝试运行 javascript-obfuscator 进行混淆（如果已安装）
    tool_dir = BACKEND_DIR.parent / "tool"
    obfuscator_path = tool_dir / "node_modules" / ".bin" / "javascript-obfuscator"

    if obfuscator_path.exists():
        print("  → 检测到 javascript-obfuscator，执行代码混淆...")
        try:
            # 创建临时混淆配置
            import json
            obf_config = {
                "compact": True,
                "simplify": True,
                "identifierNamesGenerator": "hexadecimal",
                "renameGlobals": False,
                "selfDefending": True,
                "debugProtection": True,  # 简化：关闭以提升性能
                "disableConsoleOutput": True,
                "controlFlowFlattening": False,
                "deadCodeInjection": False,
                "stringArray": True,
                "stringArrayEncoding": [],
                "stringArrayWrappersCount": 1,
            }
            config_path = tool_dir / "obf_config_temp.json"
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(obf_config, f)

            result = subprocess.run(
                [str(obfuscator_path), str(target_file), "--config",
                 str(config_path), "--output", str(target_file)],
                capture_output=True,
                text=True,
                cwd=str(tool_dir)
            )
            if result.returncode == 0:
                print("  → 代码混淆完成 ✓")
            else:
                print(f"  → 混淆失败（非致命）: {result.stderr[:200]}")

            # 清理临时配置
            config_path.unlink(missing_ok=True)
        except Exception as e:
            print(f"  → 混淆过程出错（非致命）: {e}")
    else:
        print("  → 未安装 javascript-obfuscator，跳过混淆（仅替换 URL/Token）")
        print("    （如需混淆，请在 tool/ 目录执行 npm install）")

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


def run_initialization():
    """执行一次性初始化"""
    print("=" * 60)
    print("ChineseIdomWordle 统一入口 - 首次初始化")
    print("=" * 60)

    from app.core.config import get_settings
    settings = get_settings()

    frontend_cfg = settings.frontend
    print(f"\n[配置] 启动模式: {frontend_cfg.front_mode.value}")
    print(f"[配置] 监听地址: {frontend_cfg.host}:{frontend_cfg.port}")

    if frontend_cfg.front_mode.value == "default":
        # default 模式：同域部署，使用相对路径
        obfuscate_frontend_js("", frontend_cfg.front_token)
        # 添加 token 到数据库
        add_front_token_to_db(frontend_cfg.front_token)
    else:
        # backend 模式：API 独立部署，使用配置的地址
        print("\n[初始化] backend 模式：更新前端 JS API 地址...")
        obfuscate_frontend_js(frontend_cfg.api_base_url,
                              frontend_cfg.front_token)
        # backend 模式也添加 token（方便前端直接连接）
        add_front_token_to_db(frontend_cfg.front_token)

    mark_initialized()
    print("\n[初始化] 完成 ✓")


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
    """创建全栈模式应用：静态文件 + API 同域部署

    直接复用 main.py 中已完全初始化的 backend_app（其路由已带 /api 前缀），
    在其上添加静态文件服务和 SPA 兜底路由。
    """
    from fastapi import Request
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from app.schemas.game import ErrorResponse

    # 直接导入已在 main.py 中完成所有初始化的 backend_app
    # （包含完整的中间件、异常处理器、后台清理任务、/api/* 路由等）
    from app.main import app as full_app

    client_dir = BACKEND_DIR.parent / "client"
    if client_dir.exists():
        # 挂载静态资源目录（文件类资源，不含 html）
        full_app.mount(
            "/css", StaticFiles(directory=str(client_dir / "css")), name="css")
        full_app.mount(
            "/js", StaticFiles(directory=str(client_dir / "js")), name="js")
        full_app.mount(
            "/icons", StaticFiles(directory=str(client_dir / "icons")), name="icons")

        # SPA 兜底路由：处理所有页面路由和文件（包括 /help、/top 等子页面）
        @full_app.get("/{full_path:path}")
        async def spa_fallback(full_path: str, request: Request):
            file_path = client_dir / full_path

            # 1. 如果是文件，直接返回（包括 .html、.css、.js、wav、图片等）
            if file_path.is_file():
                return FileResponse(str(file_path))

            # 2. 如果是目录，尝试返回目录下的 index.html（处理 /help、/help/、/top 等情况）
            if file_path.is_dir():
                dir_index = file_path / "index.html"
                if dir_index.is_file():
                    return FileResponse(str(dir_index))

            # 3. 尝试路径加 .html 后缀
            html_file = client_dir / f"{full_path}.html"
            if html_file.is_file():
                return FileResponse(str(html_file))

            # 4. 否则返回根目录 index.html（SPA 路由）
            index_file = client_dir / "index.html"
            if index_file.exists():
                return FileResponse(str(index_file))

            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    code=404, status="fail", message="Not Found").model_dump()
            )

    return full_app


def main():
    """主入口"""
    # 首次初始化检查
    if not is_initialized():
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
    print(f"服务启动中...")
    print(
        f"  模式: {'全栈模式（前端+后端）' if settings.frontend.front_mode.value == 'default' else '纯后端模式'}")
    print(f"  地址: http://{host}:{port}")
    if settings.frontend.front_mode.value == "default":
        print(f"  前端: http://{host}:{port}/")
        print(f"  API:  http://{host}:{port}/api")
        print(f"  文档: http://{host}:{port}/api/docs")
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
