// Configuração
const UPDATE_INTERVAL = 10000; // 10 segundos
let chartInstance = null;

// Funções utilitárias
function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
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
}

// Inicializa dashboard
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard carregado');
    
    // Primeira atualização imediata
    updateDashboard();
    
    // Atualiza periodicamente
    setInterval(updateDashboard, UPDATE_INTERVAL);
    
    // Log de estado
    console.log(`Atualizações automáticas a cada ${UPDATE_INTERVAL / 1000}s`);
});

// Graceful error handling
window.addEventListener('error', (event) => {
    console.error('Erro global:', event.error);
});
