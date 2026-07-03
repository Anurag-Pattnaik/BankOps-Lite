// =============================================================================
// FILE: dashboard/static/js/charts.js
//
// PURPOSE:
//   Fetches data from the Flask API routes and renders all 6 Chart.js charts.
//   This file demonstrates how a BI visualization tool (like Tableau or PowerBI)
//   works under the hood: it fetches JSON data and maps it to visual encodings
//   (bar heights, pie slices, colors) to communicate insights to stakeholders.
//
// INTERVIEW ANSWER — "How is this similar to Tableau/PowerBI?":
//   "Both Tableau and PowerBI connect to a data source (SQL query), pull
//    metrics as JSON/records, and map those numbers to visual channels like
//    length, color, and angle. Chart.js does the same thing programmatically.
//    Understanding this helps me configure data sources and calculated fields
//    in Tableau — the logic is identical, just a different UI layer."
// =============================================================================

'use strict';

// ── Chart.js Global Defaults ──────────────────────────────────────────────────
// Set a consistent font and color palette across all charts
Chart.defaults.font.family  = "'Outfit', sans-serif";
Chart.defaults.color         = '#7c8db0';
Chart.defaults.borderColor   = 'rgba(255,255,255,0.06)';

// ── Color Palette ─────────────────────────────────────────────────────────────
const COLORS = {
    blue:    'rgba(59,  130, 246, 0.85)',
    blueFill:'rgba(59,  130, 246, 0.15)',
    violet:  'rgba(124,  58, 237, 0.85)',
    green:   'rgba(16,  185, 129, 0.85)',
    amber:   'rgba(245, 158,  11, 0.85)',
    red:     'rgba(239,  68,  68, 0.85)',
    teal:    'rgba(13,  148, 136, 0.85)',
    borders: [
        'rgba(59,130,246,1)',
        'rgba(124,58,237,1)',
        'rgba(16,185,129,1)',
        'rgba(245,158,11,1)',
        'rgba(239,68,68,1)',
        'rgba(13,148,136,1)',
    ],
    fills: [
        'rgba(59,130,246,0.8)',
        'rgba(124,58,237,0.8)',
        'rgba(16,185,129,0.8)',
        'rgba(245,158,11,0.8)',
        'rgba(239,68,68,0.8)',
        'rgba(13,148,136,0.8)',
    ]
};

// ── Helper: Fetch JSON from Flask API route ───────────────────────────────────
async function fetchJSON(url) {
    const res  = await fetch(url);
    const data = await res.json();
    return data;
}

// ── Helper: Format large INR amounts (e.g., 12500000 → ₹1.25 Cr) ─────────────
function fmtINR(val) {
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)}Cr`;
    if (val >= 100000)   return `₹${(val / 100000).toFixed(2)}L`;
    return `₹${Math.round(val).toLocaleString()}`;
}

// =============================================================================
// LOAD ALL DATA AND RENDER DASHBOARD
// =============================================================================
async function loadDashboard() {
    // Fetch all API endpoints in parallel (faster than sequential)
    const [govData, monthlyData, acctData, branchData, fraudTypeData, creditData, fraudStats] =
        await Promise.all([
            fetchJSON('/api/governance'),
            fetchJSON('/api/monthly_volume'),
            fetchJSON('/api/account_distribution'),
            fetchJSON('/api/top_branches'),
            fetchJSON('/api/fraud_by_type'),
            fetchJSON('/api/credit_distribution'),
            fetchJSON('/api/fraud_stats'),
        ]);

    // ── Populate KPI Cards ──────────────────────────────────────────────────
    document.getElementById('kpi-raw-tx').textContent         = govData.raw_transactions?.toLocaleString()   ?? '–';
    document.getElementById('kpi-clean-tx').textContent       = govData.clean_transactions?.toLocaleString() ?? '–';
    document.getElementById('kpi-tx-pass').textContent        = govData.tx_pass_rate ? `${govData.tx_pass_rate}%` : '–';
    document.getElementById('kpi-actual-fraud').textContent   = fraudStats.actual_fraud?.toLocaleString()    ?? '–';
    document.getElementById('kpi-predicted-fraud').textContent= fraudStats.predicted_fraud?.toLocaleString() ?? '–';
    document.getElementById('kpi-fraud-rate').textContent     = fraudStats.fraud_rate_pct ? `${fraudStats.fraud_rate_pct}%` : '–';
    document.getElementById('run-timestamp').textContent      = `Last run: ${govData.run_timestamp ?? 'Unknown'}`;

    // ── Chart 1: Monthly Transaction Volume (Grouped Bar) ──────────────────
    new Chart(document.getElementById('chart-monthly'), {
        type: 'bar',
        data: {
            labels: monthlyData.map(r => r.month_label),
            datasets: [
                {
                    label: 'Total Deposits (₹)',
                    data: monthlyData.map(r => r.deposits),
                    backgroundColor: COLORS.blue,
                    borderRadius: 4,
                },
                {
                    label: 'Total Withdrawals (₹)',
                    data: monthlyData.map(r => r.withdrawals),
                    backgroundColor: COLORS.violet,
                    borderRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        // Format tooltip values as INR amounts for readability
                        label: ctx => ` ${ctx.dataset.label}: ${fmtINR(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.04)' } },
                y: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { callback: v => fmtINR(v) }
                }
            }
        }
    });

    // ── Chart 2: Account Type Distribution (Doughnut) ──────────────────────
    new Chart(document.getElementById('chart-acct-type'), {
        type: 'doughnut',
        data: {
            labels: acctData.map(r => r.account_type),
            datasets: [{
                data: acctData.map(r => r.count),
                backgroundColor: COLORS.fills,
                borderColor: 'rgba(0,0,0,0.3)',
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} customers`
                    }
                }
            }
        }
    });

    // ── Chart 3: Credit Score Bands (Horizontal Bar) ────────────────────────
    new Chart(document.getElementById('chart-credit'), {
        type: 'bar',
        data: {
            labels: creditData.map(r => r.score_band),
            datasets: [{
                label: 'Number of Customers',
                data: creditData.map(r => r.customer_count),
                backgroundColor: [COLORS.red, COLORS.amber, COLORS.blue, COLORS.green],
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',   // Horizontal bar
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.04)' } },
                y: { grid: { display: false } }
            }
        }
    });

    // ── Chart 4: Top Branches by Volume (Horizontal Bar) ───────────────────
    new Chart(document.getElementById('chart-branches'), {
        type: 'bar',
        data: {
            labels: branchData.map(r => r.branch_id),
            datasets: [{
                label: 'Total Volume (₹)',
                data: branchData.map(r => r.total_volume),
                backgroundColor: COLORS.teal,
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',   // Horizontal bar
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => ` ${fmtINR(ctx.parsed.x)}` } }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { callback: v => fmtINR(v) }
                },
                y: { grid: { display: false } }
            }
        }
    });

    // ── Chart 5: Fraud by Transaction Type (Pie) ────────────────────────────
    new Chart(document.getElementById('chart-fraud-type'), {
        type: 'pie',
        data: {
            labels: fraudTypeData.map(r => r.transaction_type),
            datasets: [{
                data: fraudTypeData.map(r => r.predicted_fraud),
                backgroundColor: COLORS.fills,
                borderColor: 'rgba(0,0,0,0.3)',
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} flagged transactions`
                    }
                }
            }
        }
    });

    // ── Chart 6: Governance Quality Score (Doughnut Gauge) ─────────────────
    const passRate   = govData.tx_pass_rate  ?? 0;
    const rejectRate = parseFloat((100 - passRate).toFixed(1));

    new Chart(document.getElementById('chart-governance'), {
        type: 'doughnut',
        data: {
            labels: ['Passed Governance ✅', 'Rejected / Dirty ❌'],
            datasets: [{
                data: [passRate, rejectRate],
                backgroundColor: [COLORS.green, COLORS.red],
                borderColor: 'rgba(0,0,0,0.3)',
                borderWidth: 2,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',   // Makes it look like a gauge
            plugins: {
                legend: { position: 'bottom' },
                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed.toFixed(1)}%` } }
            }
        }
    });
}

// ── Initialize ─────────────────────────────────────────────────────────────────
loadDashboard().catch(err => {
    console.error("Dashboard failed to load. Is the pipeline complete?", err);
    document.querySelector('.shell').innerHTML +=
        `<div style="padding:2rem;color:#ef4444;text-align:center">
            <h3>⚠️ Database not found</h3>
            <p>Please run all 3 pipeline scripts first, then reload this page.</p>
            <code style="font-size:0.8rem">python pipeline/1_generate_legacy_data.py<br>
            python pipeline/2_governance_engine.py<br>
            python pipeline/3_fraud_detector.py</code>
        </div>`;
});
