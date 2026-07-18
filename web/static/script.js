// Configuração
const UPDATE_INTERVAL = 10000; // 10 segundos
const DEX_SCAN_INTERVAL = 15000; // 15 segundos - mais frequente, é só leitura on-chain
let chartInstance = null;

// Funções utilitárias
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
}

function formatPercent(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 3
    }).format(value);
}

function shortenAddress(addr) {
    if (!addr) return '-';
    return addr.slice(0, 6) + '...' + addr.slice(-4);
}

function formatDate(dateString) {
    if (!dateString) return '--:--:--';
    const date = new Date(dateString);
    return date.toLocaleTimeString('pt-BR');
}

function getStatusBadge(status) {
    const badges = {
        'SUCCESS': 'badge-success',
        'FAILED': 'badge-error',
        'PENDING': 'badge-pending',
        'DRY_RUN': 'badge-warning',
        'ERROR': 'badge-error'
    };
    const badgeClass = badges[status] || 'badge-warning';
    return `<span class="badge ${badgeClass}">${status}</span>`;
}

function checklistItem(label, ok, okText = 'OK', failText = 'Pendente') {
    const icon = ok ? '✅' : '⚠️';
    const badgeClass = ok ? 'badge-success' : 'badge-warning';
    const text = ok ? okText : failText;
    return `
        <div class="text-center p-3 rounded-lg bg-black/20">
            <div class="text-2xl mb-1">${icon}</div>
            <p class="text-xs text-gray-400 mb-1">${label}</p>
            <span class="badge ${badgeClass}">${text}</span>
        </div>
    `;
}

// Atualiza o checklist de configuração
async function updateConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();

        if (data.error) {
            console.error('Erro ao buscar config:', data.error);
            return;
        }

        const c = data.checklist;
        document.getElementById('config-checklist').innerHTML = [
            checklistItem('RPC Polygon', c.rpc_conectado, 'Conectado', 'Offline'),
            checklistItem('Carteira', c.carteira_configurada, 'Configurada', 'Sem PRIVATE_KEY'),
            checklistItem('Contrato DEX', c.contrato_dex_deployado, 'Deployado', 'Não deployado'),
            checklistItem('DRY RUN', !c.dry_run, 'Desligado (LIVE)', 'Ligado (simulação)'),
            checklistItem('FastLane', c.fastlane_ativo, 'Ativo', 'Desativado'),
        ].join('');

        const prodBadge = document.getElementById('producao-badge');
        if (data.pronto_para_producao) {
            prodBadge.textContent = '🟢 Pronto para produção';
            prodBadge.className = 'badge badge-success';
        } else if (c.dry_run) {
            prodBadge.textContent = '🧪 Modo simulação (DRY RUN)';
            prodBadge.className = 'badge badge-pending';
        } else {
            prodBadge.textContent = '⚠️ Configuração incompleta';
            prodBadge.className = 'badge badge-warning';
        }

        document.getElementById('config-wallet').textContent = shortenAddress(data.wallet_address);
        document.getElementById('config-balance').textContent =
            data.wallet_matic_balance !== null && data.wallet_matic_balance !== undefined
                ? `${data.wallet_matic_balance.toFixed(4)} MATIC/POL`
                : 'Indisponível';
        document.getElementById('config-contract').textContent = shortenAddress(data.dex_contract_address);
    } catch (error) {
        console.error('Erro ao atualizar config:', error);
    }
}

// Atualiza o card de oportunidade DEX ao vivo
async function updateDexScan() {
    const el = document.getElementById('dex-scan-content');
    try {
        const response = await fetch('/api/dex-scan');
        const data = await response.json();

        if (data.error) {
            el.innerHTML = `<p class="text-red-400 text-center py-4">Erro ao consultar: ${data.error}</p>`;
            return;
        }

        const spreadPct = formatPercent(data.gross_spread ?? 0);
        const minimoPct = formatPercent(data.spread_minimo);

        if (data.found) {
            el.innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-center">
                    <div class="md:col-span-1 text-center">
                        <p class="text-3xl font-bold text-green-400">${spreadPct}</p>
                        <p class="text-xs text-gray-400">spread bruto encontrado</p>
                    </div>
                    <div class="md:col-span-2 text-sm text-gray-300">
                        <p>Compra em <span class="font-mono">${shortenAddress(data.router_buy)}</span> → vende em <span class="font-mono">${shortenAddress(data.router_sell)}</span></p>
                        <p class="text-gray-400 mt-1">Capital simulado: ${formatCurrency(data.capital_usdc)} · Lucro bruto estimado: <span class="text-green-400 font-bold">${formatCurrency(data.lucro_bruto_estimado_usdc)}</span></p>
                    </div>
                    <div class="md:col-span-1 text-right">
                        <span class="badge badge-success">Acima do mínimo (${minimoPct})</span>
                    </div>
                </div>
            `;
        } else {
            el.innerHTML = `
                <div class="text-center py-4">
                    <p class="text-gray-400">Nenhum spread lucrativo no momento</p>
                    <p class="text-xs text-gray-500 mt-1">Mínimo configurado: ${minimoPct} · Última checagem: ${formatDate(data.timestamp)}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Erro ao atualizar scan DEX:', error);
        el.innerHTML = `<p class="text-red-400 text-center py-4">Erro ao consultar oportunidade DEX</p>`;
    }
}

// Atualiza status do bot
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        // Status indicator
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        
        if (data.status === 'online') {
            statusIndicator.classList.remove('status-offline');
            statusIndicator.classList.add('status-online');
            statusText.textContent = 'Online';
            statusText.classList.remove('text-red-400');
            statusText.classList.add('text-green-400');
        } else {
            statusIndicator.classList.remove('status-online');
            statusIndicator.classList.add('status-offline');
            statusText.textContent = 'Offline';
            statusText.classList.remove('text-green-400');
            statusText.classList.add('text-red-400');
        }
        
        // Metrics
        document.getElementById('lucro-total').textContent = 
            formatCurrency(data.metrics.lucro_total);
        document.getElementById('lucro-dia').textContent = 
            formatCurrency(data.metrics.lucro_dia);
        document.getElementById('ops-dia').textContent = 
            data.metrics.ops_dia;
        document.getElementById('media-lucro').textContent = 
            formatCurrency(data.metrics.media_lucro);
        
        // Last update time
        document.getElementById('last-update').textContent = 
            formatDate(data.timestamp);
    } catch (error) {
        console.error('Erro ao atualizar status:', error);
    }
}

// Atualiza tabela de operações
async function updateOperations() {
    try {
        const response = await fetch('/api/operations?limit=15');
        const data = await response.json();
        
        const tbody = document.getElementById('operations-table');
        
        if (data.operations.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-8 text-gray-400">
                        Nenhuma operação registrada
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = data.operations.map(op => `
            <tr>
                <td class="font-mono text-sm">${formatDate(op.timestamp)}</td>
                <td class="font-mono">${op.termo}</td>
                <td>
                    <span class="badge ${op.direction === 'YES' ? 'badge-success' : 'badge-error'}">
                        ${op.direction}
                    </span>
                </td>
                <td class="font-mono text-sm">${op.score ? op.score.toFixed(3) : '-'}</td>
                <td class="font-mono text-green-400 font-bold">${formatCurrency(op.lucro)}</td>
                <td>${getStatusBadge(op.status)}</td>
                <td class="text-xs text-gray-400 max-w-xs truncate">${op.detalhes || '-'}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Erro ao atualizar operações:', error);
    }
}

// Atualiza gráfico de lucro acumulado
async function updateChart() {
    try {
        const response = await fetch('/api/chart?days=30');
        const data = await response.json();
        
        if (!data.data || data.data.length === 0) {
            return;
        }
        
        const labels = data.data.map(d => {
            const date = new Date(d.data);
            return date.toLocaleDateString('pt-BR', { month: 'short', day: 'numeric' });
        });
        
        const accumulatedProfits = data.data.map(d => d.lucro_acumulado);
        
        const ctx = document.getElementById('profit-chart');
        
        if (chartInstance) {
            chartInstance.data.labels = labels;
            chartInstance.data.datasets[0].data = accumulatedProfits;
            chartInstance.update();
        } else {
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Lucro Acumulado (USD)',
                        data: accumulatedProfits,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#10b981',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 5,
                        pointHoverRadius: 7,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            labels: {
                                color: '#e0e0e0',
                                font: { size: 12 }
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(148, 163, 184, 0.1)',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#9ca3af',
                                callback: function(value) {
                                    return '$' + value.toFixed(0);
                                }
                            }
                        },
                        x: {
                            grid: {
                                display: false,
                                drawBorder: false
                            },
                            ticks: {
                                color: '#9ca3af'
                            }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Erro ao atualizar gráfico:', error);
    }
}

// Função principal de atualização
async function updateDashboard() {
    console.log(`[${new Date().toLocaleTimeString()}] Atualizando dashboard...`);
    
    await updateStatus();
    await updateOperations();
    await updateChart();
    await updateConfig();
}

// Inicializa dashboard
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard carregado');
    
    // Primeira atualização imediata
    updateDashboard();
    updateDexScan();
    
    // Atualiza periodicamente
    setInterval(updateDashboard, UPDATE_INTERVAL);
    setInterval(updateDexScan, DEX_SCAN_INTERVAL);
    
    // Log de estado
    console.log(`Atualizações automáticas a cada ${UPDATE_INTERVAL / 1000}s (dashboard) e ${DEX_SCAN_INTERVAL / 1000}s (scan DEX)`);
});

// Graceful error handling
window.addEventListener('error', (event) => {
    console.error('Erro global:', event.error);
});
