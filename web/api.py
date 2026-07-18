import os
import sys
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bot'))

from database.db import (
    get_operations,
    calculate_metrics,
    get_chart_data,
)
from bot.executor import ContractExecutor
from bot.dex_executor import DexArbitrageExecutor
from bot.config import (
    DRY_RUN,
    USE_FASTLANE,
    PRIVATE_KEY,
    DEX_ARBITRAGE_CONTRACT_ADDRESS,
    DEX_SPREAD_MINIMO,
    CAPITAL_POR_OP,
    POLYGON_RPC,
    QUICKSWAP_ROUTER,
    SUSHISWAP_ROUTER,
)

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
dex_executor = DexArbitrageExecutor(executor)

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

@app.route('/api/config')
def api_config():
    """
    Retorna um checklist de configuração do bot — NUNCA valores secretos,
    só booleanos de "configurado ou não" e endereços públicos (que são
    seguros de expor, já que endereço de contrato/carteira é público na
    blockchain de qualquer forma).
    """
    try:
        wallet_address = executor.account.address if executor.account else None
        wallet_matic_balance = None
        rpc_connected = False
        try:
            rpc_connected = executor.is_connected()
            if wallet_address and rpc_connected:
                balance_wei = executor.w3.eth.get_balance(wallet_address)
                wallet_matic_balance = balance_wei / 1e18
        except Exception as e:
            logger.warning(f"Não foi possível checar saldo/conexão: {e}")

        checklist = {
            "rpc_conectado": rpc_connected,
            "carteira_configurada": wallet_address is not None,
            "contrato_dex_deployado": bool(DEX_ARBITRAGE_CONTRACT_ADDRESS),
            "dry_run": DRY_RUN,
            "fastlane_ativo": USE_FASTLANE,
        }

        # Pronto para operar de verdade = tudo configurado E dry_run desligado
        pronto_para_producao = (
            checklist["rpc_conectado"]
            and checklist["carteira_configurada"]
            and checklist["contrato_dex_deployado"]
            and not checklist["dry_run"]
        )

        return jsonify({
            "checklist": checklist,
            "pronto_para_producao": pronto_para_producao,
            "wallet_address": wallet_address,
            "wallet_matic_balance": wallet_matic_balance,
            "dex_contract_address": DEX_ARBITRAGE_CONTRACT_ADDRESS or None,
            "quickswap_router": QUICKSWAP_ROUTER,
            "sushiswap_router": SUSHISWAP_ROUTER,
            "dex_spread_minimo": DEX_SPREAD_MINIMO,
            "capital_por_op": CAPITAL_POR_OP,
            "rpc_url_host": POLYGON_RPC.split("//")[-1].split("/")[0] if POLYGON_RPC else None,
        })
    except Exception as e:
        logger.error(f"Erro ao retornar config: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/dex-scan')
def api_dex_scan():
    """
    Dispara uma consulta AO VIVO (getAmountsOut, view — não custa gas nem
    envia transação) para ver o spread atual entre QuickSwap e SushiSwap,
    independente de estar acima do mínimo configurado. Útil pro front
    mostrar "o que o bot está vendo agora" mesmo sem executar nada.
    """
    try:
        capital = request.args.get('capital', CAPITAL_POR_OP, type=float)
        opportunity = dex_executor.scan_opportunity(capital_usdc=capital)

        if opportunity:
            return jsonify({
                "found": True,
                "acima_do_minimo": True,
                "gross_spread": opportunity["gross_spread"],
                "spread_minimo": DEX_SPREAD_MINIMO,
                "router_buy": opportunity["router_buy"],
                "router_sell": opportunity["router_sell"],
                "capital_usdc": capital,
                "lucro_bruto_estimado_usdc": (
                    opportunity["usdc_back"] - opportunity["amount_in"]
                ) / 1e6,
                "timestamp": datetime.now().isoformat(),
            })
        else:
            return jsonify({
                "found": False,
                "acima_do_minimo": False,
                "spread_minimo": DEX_SPREAD_MINIMO,
                "capital_usdc": capital,
                "mensagem": "Sem spread lucrativo acima do mínimo no momento (ou RPC indisponível)",
                "timestamp": datetime.now().isoformat(),
            })
    except Exception as e:
        logger.error(f"Erro ao escanear oportunidade DEX: {e}")
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
