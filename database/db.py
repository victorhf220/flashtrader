import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import os

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "sentinel.db")

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Retorna conexão SQLite"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Inicializa banco de dados com schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabela de operações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                termo TEXT NOT NULL,
                direction TEXT NOT NULL,
                score REAL,
                lucro REAL DEFAULT 0.0,
                status TEXT,
                detalhes TEXT,
                tx_hash TEXT
            )
        ''')
        
        # Tabela de métricas agregadas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                lucro_dia REAL DEFAULT 0.0,
                lucro_semana REAL DEFAULT 0.0,
                lucro_mes REAL DEFAULT 0.0,
                lucro_total REAL DEFAULT 0.0,
                ops_dia INTEGER DEFAULT 0,
                ops_semana INTEGER DEFAULT 0,
                ops_mes INTEGER DEFAULT 0,
                ops_total INTEGER DEFAULT 0
            )
        ''')
        
        # Tabela de configurações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Índices para performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_termo ON operations(termo)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status)')
        
        conn.commit()
        conn.close()
        logger.info(f"Database inicializado: {self.db_path}")
    
    def save_operation(
        self,
        termo: str,
        direction: str,
        score: float,
        lucro: float,
        status: str,
        detalhes: str = "",
        tx_hash: str = None
    ) -> int:
        """Salva uma operação no banco"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO operations
            (termo, direction, score, lucro, status, detalhes, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (termo, direction, score, lucro, status, detalhes, tx_hash))
        
        operation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Operação salva (ID: {operation_id}): {termo} {direction} Lucro: ${lucro:.2f}")
        return operation_id
    
    def get_operations(self, limit: int = 50, status: str = None) -> List[Dict]:
        """Retorna últimas operações"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT * FROM operations
                WHERE status = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT * FROM operations
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_operations_by_date(self, days: int = 1) -> List[Dict]:
        """Retorna operações dos últimos N dias"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT * FROM operations
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
        ''', (cutoff_date.isoformat(),))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_metrics(
        self,
        lucro_dia: float,
        lucro_semana: float,
        lucro_mes: float,
        lucro_total: float,
        ops_dia: int,
        ops_semana: int,
        ops_mes: int,
        ops_total: int
    ):
        """Atualiza métricas agregadas"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO metrics
            (lucro_dia, lucro_semana, lucro_mes, lucro_total, ops_dia, ops_semana, ops_mes, ops_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (lucro_dia, lucro_semana, lucro_mes, lucro_total, ops_dia, ops_semana, ops_mes, ops_total))
        
        conn.commit()
        conn.close()
    
    def get_latest_metrics(self) -> Dict:
        """Retorna últimas métricas agregadas"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM metrics
            ORDER BY timestamp DESC
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else {}
    
    def calculate_metrics(self) -> Dict:
        """Calcula métricas a partir das operações"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now()
        one_day_ago = now - timedelta(days=1)
        one_week_ago = now - timedelta(days=7)
        one_month_ago = now - timedelta(days=30)
        
        # Lucro e contagem do dia
        cursor.execute('''
            SELECT SUM(lucro) as total_lucro, COUNT(*) as total_ops
            FROM operations
            WHERE timestamp >= ? AND status = 'SUCCESS'
        ''', (one_day_ago.isoformat(),))
        
        day_result = cursor.fetchone()
        lucro_dia = day_result['total_lucro'] or 0.0
        ops_dia = day_result['total_ops'] or 0
        
        # Lucro e contagem da semana
        cursor.execute('''
            SELECT SUM(lucro) as total_lucro, COUNT(*) as total_ops
            FROM operations
            WHERE timestamp >= ? AND status = 'SUCCESS'
        ''', (one_week_ago.isoformat(),))
        
        week_result = cursor.fetchone()
        lucro_semana = week_result['total_lucro'] or 0.0
        ops_semana = week_result['total_ops'] or 0
        
        # Lucro e contagem do mês
        cursor.execute('''
            SELECT SUM(lucro) as total_lucro, COUNT(*) as total_ops
            FROM operations
            WHERE timestamp >= ? AND status = 'SUCCESS'
        ''', (one_month_ago.isoformat(),))
        
        month_result = cursor.fetchone()
        lucro_mes = month_result['total_lucro'] or 0.0
        ops_mes = month_result['total_ops'] or 0
        
        # Lucro e contagem total
        cursor.execute('''
            SELECT SUM(lucro) as total_lucro, COUNT(*) as total_ops
            FROM operations
            WHERE status = 'SUCCESS'
        ''')
        
        total_result = cursor.fetchone()
        lucro_total = total_result['total_lucro'] or 0.0
        ops_total = total_result['total_ops'] or 0
        
        conn.close()
        
        return {
            "lucro_dia": float(lucro_dia),
            "lucro_semana": float(lucro_semana),
            "lucro_mes": float(lucro_mes),
            "lucro_total": float(lucro_total),
            "ops_dia": int(ops_dia),
            "ops_semana": int(ops_semana),
            "ops_mes": int(ops_mes),
            "ops_total": int(ops_total),
        }
    
    def get_chart_data(self, days: int = 30) -> List[Dict]:
        """Retorna dados para gráfico de lucro acumulado"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT 
                DATE(timestamp) as data,
                SUM(lucro) as lucro_diario
            FROM operations
            WHERE timestamp >= ? AND status = 'SUCCESS'
            GROUP BY DATE(timestamp)
            ORDER BY data ASC
        ''', (cutoff_date.isoformat(),))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Converte para formato esperado pelo frontend
        data = []
        accumulated = 0.0
        
        for row in rows:
            accumulated += row['lucro_diario'] or 0.0
            data.append({
                "data": row['data'],
                "lucro_diario": float(row['lucro_diario'] or 0.0),
                "lucro_acumulado": float(accumulated)
            })
        
        return data
    
    def set_config(self, key: str, value: str):
        """Salva configuração"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO config (key, value)
            VALUES (?, ?)
        ''', (key, value))
        
        conn.commit()
        conn.close()
    
    def get_config(self, key: str) -> str:
        """Retorna configuração"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        
        return row['value'] if row else None
    
    def clear_old_data(self, days: int = 90):
        """Limpa dados antigos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            DELETE FROM operations
            WHERE timestamp < ?
        ''', (cutoff_date.isoformat(),))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Limpeza de banco: {deleted} operações antigas deletadas")

# Instância global
db = Database()

# Funções convenientes
def save_operation(termo, direction, score, lucro, status, detalhes="", tx_hash=None):
    return db.save_operation(termo, direction, score, lucro, status, detalhes, tx_hash)

def get_operations(limit=50, status=None):
    return db.get_operations(limit, status)

def get_latest_metrics():
    return db.get_latest_metrics()

def calculate_metrics():
    return db.calculate_metrics()

def get_chart_data(days=30):
    return db.get_chart_data(days)
