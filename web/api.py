import os
import sys
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_cors import CORS

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import (
    get_operations,
    calculate_metrics,
    get_chart_data,
)
from bot.executor import ContractExecutor
from bot.config import DRY_RUN

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== FLASK APP =====
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/static'
)
CORS(app)

executor = ContractExecutor()

@app.route('/')
def index():
    """Renderiza dashboard"""
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    """Retorna status do bot e métricas agregadas"""
    try:
        metrics = calculate_metrics()
        contract_stats = executor.get_contract_stats()
        
        return jsonify({
            "status": "online" if executor.is_connected() else "offline",
            "timestamp": datetime.now().isoformat(),
            "dry_run": DRY_RUN,
            "metrics": {
                "lucro_dia": metrics.get('lucro_dia', 0),
                "lucro_semana": metrics.get('lucro_semana', 0),
                "lucro_mes": metrics.get('lucro_mes', 0),
                "lucro_total": metrics.get('lucro_total', 0),
                "ops_dia": metrics.get('ops_dia', 0),
                "ops_semana": metrics.get('ops_semana', 0),
                "ops_mes": metrics.get('ops_mes', 0),
                "ops_total": metrics.get('ops_total', 0),
                "media_lucro": (
                    metrics.get('lucro_total', 0) / metrics.get('ops_total', 1)
                    if metrics.get('ops_total', 0) > 0 else 0
                )
            },
            "contract": contract_stats
        })
    except Exception as e:
        logger.error(f"Erro ao retornar status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/operations')
def api_operations():
    """Retorna últimas operações em JSON"""
    try:
        limit = request.args.get('limit', 20, type=int)
        status = request.args.get('status', None)
        
        operations = get_operations(limit=limit, status=status)
        
        return jsonify({
            "count": len(operations),
            "operations": [
                {
                    "id": op['id'],
                    "timestamp": op['timestamp'],
                    "termo": op['termo'],
                    "direction": op['direction'],
                    "score": op['score'],
                    "lucro": op['lucro'],
                    "status": op['status'],
                    "detalhes": op['detalhes'],
                    "tx_hash": op['tx_hash']
                }
                for op in operations
            ]
        })
    except Exception as e:
        logger.error(f"Erro ao retornar operações: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/chart')
def api_chart():
    """Retorna dados para gráfico de lucro acumulado"""
    try:
        days = request.args.get('days', 30, type=int)
        data = get_chart_data(days=days)
        
        return jsonify({
            "days": days,
            "data": data
        })
    except Exception as e:
        logger.error(f"Erro ao retornar dados do gráfico: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def api_health():
    """Healthcheck simples"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    logger.info("Iniciando servidor Flask...")
    app.run(host='0.0.0.0', port=5000, debug=False)
