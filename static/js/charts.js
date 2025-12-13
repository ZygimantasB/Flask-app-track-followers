/**
 * Analytics charts for GitHub Followers Tracker
 * Uses Chart.js for visualization
 */

let followerChart = null;
let activityChart = null;

/**
 * Initialize Chart.js (load from CDN if not available)
 * @returns {Promise<void>}
 */
export async function initCharts() {
    if (typeof Chart === 'undefined') {
        await loadChartJs();
    }
}

/**
 * Load Chart.js from CDN
 * @returns {Promise<void>}
 */
function loadChartJs() {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

/**
 * Create or update the follower growth chart
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} snapshots - Snapshot data
 */
export function renderFollowerChart(canvas, snapshots) {
    if (!snapshots || snapshots.length === 0) {
        canvas.parentElement.innerHTML = '<p class="chart-placeholder">No data available</p>';
        return;
    }

    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (followerChart) {
        followerChart.destroy();
    }

    const labels = snapshots.map(s => {
        const date = new Date(s.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const followerData = snapshots.map(s => s.followers);
    const followingData = snapshots.map(s => s.following);

    const isDark = !document.body.classList.contains('light-theme');
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const textColor = isDark ? '#e0e0e0' : '#333';

    followerChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Followers',
                    data: followerData,
                    borderColor: '#e94560',
                    backgroundColor: 'rgba(233, 69, 96, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Following',
                    data: followingData,
                    borderColor: '#4ade80',
                    backgroundColor: 'rgba(74, 222, 128, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: textColor,
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    backgroundColor: isDark ? '#16213e' : '#fff',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: gridColor,
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true
                }
            },
            scales: {
                x: {
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor
                    }
                },
                y: {
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor
                    },
                    beginAtZero: false
                }
            }
        }
    });
}

/**
 * Create or update the activity chart (gained/lost)
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array} snapshots - Snapshot data
 */
export function renderActivityChart(canvas, snapshots) {
    if (!snapshots || snapshots.length === 0) {
        canvas.parentElement.innerHTML = '<p class="chart-placeholder">No data available</p>';
        return;
    }

    const ctx = canvas.getContext('2d');

    // Destroy existing chart
    if (activityChart) {
        activityChart.destroy();
    }

    const labels = snapshots.map(s => {
        const date = new Date(s.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const gainedData = snapshots.map(s => s.new_followers || 0);
    const lostData = snapshots.map(s => -(s.lost_followers || 0));

    const isDark = !document.body.classList.contains('light-theme');
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const textColor = isDark ? '#e0e0e0' : '#333';

    activityChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Gained',
                    data: gainedData,
                    backgroundColor: 'rgba(74, 222, 128, 0.8)',
                    borderColor: '#4ade80',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Lost',
                    data: lostData,
                    backgroundColor: 'rgba(233, 69, 96, 0.8)',
                    borderColor: '#e94560',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: textColor,
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    backgroundColor: isDark ? '#16213e' : '#fff',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: gridColor,
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const value = Math.abs(context.raw);
                            return `${context.dataset.label}: ${value}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor
                    }
                },
                y: {
                    stacked: true,
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor,
                        callback: function(value) {
                            return Math.abs(value);
                        }
                    }
                }
            }
        }
    });
}

/**
 * Create a simple sparkline chart
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {Array<number>} data - Data points
 * @param {string} color - Line color
 */
export function renderSparkline(canvas, data, color = '#e94560') {
    if (!data || data.length === 0) return;

    const ctx = canvas.getContext('2d');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map((_, i) => i),
            datasets: [{
                data,
                borderColor: color,
                borderWidth: 2,
                fill: false,
                tension: 0.3,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                x: { display: false },
                y: { display: false }
            }
        }
    });
}

/**
 * Render a simple bar chart without Chart.js (fallback)
 * @param {HTMLElement} container - Container element
 * @param {Array} snapshots - Snapshot data
 */
export function renderSimpleChart(container, snapshots) {
    container.innerHTML = '';

    if (!snapshots || snapshots.length === 0) {
        container.innerHTML = '<p class="chart-placeholder">No data available</p>';
        return;
    }

    const maxFollowers = Math.max(...snapshots.map(s => s.followers));
    const minFollowers = Math.min(...snapshots.map(s => s.followers));
    const range = maxFollowers - minFollowers || 1;

    const chartDiv = document.createElement('div');
    chartDiv.className = 'simple-chart';

    snapshots.forEach((snapshot, index) => {
        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        const height = ((snapshot.followers - minFollowers) / range) * 100;
        bar.style.height = `${Math.max(5, height)}%`;
        bar.title = `${snapshot.date.split('T')[0]}: ${snapshot.followers} followers`;

        if (index === snapshots.length - 1) {
            bar.classList.add('chart-bar-latest');
        }

        chartDiv.appendChild(bar);
    });

    container.appendChild(chartDiv);
}

/**
 * Update chart colors when theme changes
 */
export function updateChartTheme() {
    // Charts will be re-rendered with new theme on next data load
    if (followerChart) {
        const canvas = followerChart.canvas;
        const data = followerChart.data;
        followerChart.destroy();
        // Re-render will happen on next analytics load
    }
}
