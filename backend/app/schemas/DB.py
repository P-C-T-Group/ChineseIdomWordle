class DBConnection:
    enabled: bool = False
    type: str = 'mysql'
    host: str
    port: int = 3306
    user: str
    password: str
    db: str
    charset: str = 'utf8mb4'
