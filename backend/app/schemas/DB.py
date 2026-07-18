"""
数据库相关 Schema

DatabaseType 与 DatabaseConfig 已迁移到 app.schemas.config，
此处仅为向后兼容重新导出，避免已有导入路径失效。
"""
from app.schemas.config import DatabaseType, DatabaseConfig

# 兼容旧名：db_manager / initDB 历史上使用 DBConnection
DBConnection = DatabaseConfig

__all__ = ["DatabaseType", "DatabaseConfig", "DBConnection"]
