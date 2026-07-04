import React, { useState, useEffect, useRef } from 'react';
import { Chart, registerables } from 'chart.js';
import { jsPDF } from 'jspdf';

// Register Chart.js components
Chart.register(...registerables);

const API = 'http://localhost:8000';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [userEmail, setUserEmail] = useState(localStorage.getItem('user_email') || '');
  const [userId, setUserId] = useState(localStorage.getItem('user_id') || '');
  const [authState, setAuthState] = useState('login'); // 'login' or 'register'
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');

  const [activeTab, setActiveTab] = useState('dashboard');
  const [trades, setTrades] = useState([]);
  const [isConnected, setIsConnected] = useState(true);

  // Form State
  const [formMode, setFormMode] = useState('add'); // 'add' or 'edit'
  const [editId, setEditId] = useState('');
  const [fDirection, setFDirection] = useState('BUY');
  const [fStatus, setFStatus] = useState('OPEN');
  const [fEntry, setFEntry] = useState('');
  const [fSl, setFSl] = useState('');
  const [fTp, setFTp] = useState('');
  const [fExit, setFExit] = useState('');
  const [fSession, setFSession] = useState('');
  const [fTimeframe, setFTimeframe] = useState('');
  const [fTechnique, setFTechnique] = useState('');
  const [fFailure, setFFailure] = useState('');
  const [fConfirmations, setFConfirmations] = useState('');

  // Filters State
  const [filterDirection, setFilterDirection] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSession, setFilterSession] = useState('');

  // Analysis State
  const [directiveReport, setDirectiveReport] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Toast State
  const [toastMsg, setToastMsg] = useState('');
  const [toastType, setToastType] = useState('success');
  const [showToast, setShowToast] = useState(false);

  // Chart Canvas Refs
  const equityCanvasRef = useRef(null);
  const winlossCanvasRef = useRef(null);
  const sessionCanvasRef = useRef(null);
  const rtradesCanvasRef = useRef(null);

  // Chart Instance Refs
  const chartRefs = useRef({});

  // Show toast notification
  const triggerToast = (msg, type = 'success') => {
    setToastMsg(msg);
    setToastType(type);
    setShowToast(true);
    setTimeout(() => setShowToast(false), 3000);
  };

  // Base API fetcher
  const apiFetch = async (path, opts = {}) => {
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    try {
      const res = await fetch(API + path, {
        ...opts,
        headers: { ...headers, ...(opts.headers || {}) }
      });
      
      if (res.status === 401 && token) {
        handleLogout();
        throw new Error('Session expired. Please log in again.');
      }
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${res.status}`);
      }
      
      return await res.json();
    } catch (err) {
      console.error('API Fetch error:', err);
      triggerToast(err.message, 'error');
      return null;
    }
  };

  // Load trades from backend
  const loadTrades = async () => {
    if (!token) return;
    const data = await apiFetch('/trades');
    if (data && data.status === 'success') {
      setTrades(data.trades || []);
      setIsConnected(true);
    } else {
      setIsConnected(false);
    }
  };

  // Trigger load when authenticated
  useEffect(() => {
    if (token) {
      loadTrades();
      const interval = setInterval(loadTrades, 30000);
      return () => clearInterval(interval);
    }
  }, [token]);

  // Redraw charts when trades or tab changes
  useEffect(() => {
    if (activeTab === 'dashboard' && token && trades.length > 0) {
      renderDashboardCharts();
    }
  }, [activeTab, trades, token]);

  // Auth Handlers
  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    const path = authState === 'login' ? '/login' : '/register';
    const payload = { email: authEmail, password: authPassword };
    
    try {
      const res = await fetch(API + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }
      
      if (authState === 'login') {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user_email', data.email);
        localStorage.setItem('user_id', data.user_id);
        setToken(data.access_token);
        setUserEmail(data.email);
        setUserId(data.user_id);
        triggerToast('Welcome to Au Quant!', 'success');
        setAuthPassword('');
      } else {
        triggerToast('Registration successful! You can now log in.', 'success');
        setAuthState('login');
        setAuthPassword('');
      }
    } catch (err) {
      triggerToast(err.message, 'error');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_id');
    setToken('');
    setUserEmail('');
    setUserId('');
    setTrades([]);
    triggerToast('Logged out successfully', 'success');
  };

  // Trade Form Handlers
  const openEditMode = (trade) => {
    setFormMode('edit');
    setEditId(trade.trade_id);
    setFDirection(trade.direction || 'BUY');
    setFStatus(trade.status || 'OPEN');
    setFEntry(trade.entry_price || '');
    setFSl(trade.sl || '');
    setFTp(trade.tp || '');
    setFExit(trade.exit_price || '');
    setFSession(trade.session || '');
    setFTimeframe(trade.timeframe || '');
    setFTechnique(trade.technique || '');
    setFFailure(trade.failure_cause || '');
    setFConfirmations(trade.confirmations || '');
    setActiveTab('add');
  };

  const resetForm = () => {
    setFormMode('add');
    setEditId('');
    setFDirection('BUY');
    setFStatus('OPEN');
    setFEntry('');
    setFSl('');
    setFTp('');
    setFExit('');
    setFSession('');
    setFTimeframe('');
    setFTechnique('');
    setFFailure('');
    setFConfirmations('');
  };

  const handleTradeSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      pair: 'XAUUSD',
      direction: fDirection,
      entry_price: parseFloat(fEntry),
      sl: parseFloat(fSl),
      tp: parseFloat(fTp) || null,
      exit_price: fStatus !== 'OPEN' ? (parseFloat(fExit) || null) : null,
      status: fStatus,
      session: fSession || null,
      timeframe: fTimeframe || null,
      technique: fTechnique || null,
      confirmations: fConfirmations || null,
      failure_cause: fStatus === 'LOST' ? (fFailure || null) : null
    };

    let data;
    if (formMode === 'edit') {
      data = await apiFetch(`/trades/${editId}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
    } else {
      if (payload.status === 'OPEN') {
        data = await apiFetch('/trades/open', {
          method: 'POST',
          body: JSON.stringify({ ...payload, user_id: userId })
        });
      } else {
        data = await apiFetch('/trades/log', {
          method: 'POST',
          body: JSON.stringify({ ...payload, user_id: userId })
        });
      }
    }

    if (data && data.status === 'success') {
      triggerToast(formMode === 'edit' ? 'Trade updated!' : 'Trade logged!', 'success');
      resetForm();
      await loadTrades();
      setActiveTab('journal');
    }
  };

  const handleDeleteTrade = async (tradeId) => {
    if (!window.confirm('Delete this trade permanently? This action cannot be undone.')) return;
    const data = await apiFetch(`/trades/${tradeId}`, { method: 'DELETE' });
    if (data && data.status === 'success') {
      triggerToast('Trade deleted successfully', 'success');
      await loadTrades();
    }
  };

  // Directives report generator
  const runDirectiveAnalysis = async () => {
    setIsAnalyzing(true);
    const data = await apiFetch('/directive');
    if (data && data.status === 'success') {
      setDirectiveReport(data.directive);
      triggerToast('Directive analysis updated!', 'success');
    }
    setIsAnalyzing(false);
  };

  // Backups and Exports
  const exportToCSV = () => {
    if (trades.length === 0) {
      triggerToast('No data to export', 'error');
      return;
    }
    const headers = ["Trade ID", "Timestamp", "Pair", "Direction", "Entry Price", "SL", "TP", "Exit Price", "Status", "R-Multiple", "Session", "Timeframe", "Confirmations", "Pips Gained", "Risk Free"];
    const rows = trades.map(t => [
      t.trade_id,
      t.timestamp,
      t.pair,
      t.direction,
      t.entry_price,
      t.sl,
      t.tp,
      t.exit_price || '',
      t.status,
      t.pnl_r || '0',
      t.session || '',
      t.timeframe || '',
      t.confirmations || '',
      t.pips_gained || '0',
      t.is_risk_free ? 'Yes' : 'No'
    ]);

    const csvContent = [headers.join(','), ...rows.map(e => e.map(val => `"${val}"`).join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `au_quant_trades_${userEmail.split('@')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    triggerToast('Backup CSV downloaded!', 'success');
  };

  const exportToPDF = () => {
    if (trades.length === 0) {
      triggerToast('No trade history to generate report', 'error');
      return;
    }

    const doc = new jsPDF();
    const closed = trades.filter(t => t.status === 'WON' || t.status === 'LOST');
    const wins = trades.filter(t => t.status === 'WON');
    const losses = trades.filter(t => t.status === 'LOST');
    const winRate = closed.length > 0 ? (wins.length / closed.length * 100).toFixed(1) : '0';
    const totalR = closed.reduce((sum, t) => sum + (parseFloat(t.pnl_r) || 0), 0).toFixed(2);
    
    // Title & Header
    doc.setFont("Helvetica", "bold");
    doc.setFontSize(22);
    doc.setTextColor(234, 179, 8); // Gold Color
    doc.text("Au Quant — Strategy Performance Autopsy", 14, 20);
    
    doc.setFont("Helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(113, 113, 122);
    doc.text(`User Account: ${userEmail}`, 14, 28);
    doc.text(`Report Generation Date: ${new Date().toLocaleDateString()}`, 14, 34);
    
    doc.setDrawColor(255, 255, 255, 0.1);
    doc.line(14, 38, 196, 38);
    
    // Core Metrics
    doc.setFont("Helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(228, 228, 231);
    doc.text("Key Metrics Summary", 14, 48);
    
    doc.setFont("Helvetica", "normal");
    doc.setFontSize(11);
    doc.text(`Total Logged Trades: ${trades.length}`, 14, 56);
    doc.text(`Closed Trades: ${closed.length} (${wins.length} Won / ${losses.length} Lost)`, 14, 62);
    doc.text(`Win Rate: ${winRate}%`, 14, 68);
    doc.text(`Net R-Multiple: ${totalR}R`, 14, 74);
    
    // Directives
    doc.setFont("Helvetica", "bold");
    doc.setFontSize(14);
    doc.text("Actionable Directives", 14, 88);
    
    doc.setFont("Helvetica", "normal");
    doc.setFontSize(10);
    
    let y = 96;
    if (directiveReport) {
      const splitDirectives = doc.splitTextToSize(directiveReport.replace(/#/g, '').replace(/\*/g, ''), 180);
      splitDirectives.forEach(line => {
        if (y > 275) {
          doc.addPage();
          y = 20;
        }
        doc.text(line, 14, y);
        y += 6;
      });
    } else {
      doc.text("Generate dynamic directives on the Analysis tab before exporting to include detailed insights.", 14, y);
    }
    
    doc.save(`au_quant_performance_report.pdf`);
    triggerToast('PDF Performance Report generated!', 'success');
  };

  // Rendering Charts using standard Chart.js
  const renderDashboardCharts = () => {
    const closed = trades.filter(t => t.status === 'WON' || t.status === 'LOST' || t.status === 'BE');
    const wins = trades.filter(t => t.status === 'WON');
    const losses = trades.filter(t => t.status === 'LOST');

    // Destroy previous chart instances to avoid canvas reuse errors
    Object.keys(chartRefs.current).forEach(key => {
      if (chartRefs.current[key]) {
        chartRefs.current[key].destroy();
      }
    });

    const chartOpts = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } }
    };

    // 1. Equity Line Chart
    if (equityCanvasRef.current) {
      let cumR = 0;
      const equityData = closed.map(t => {
        cumR += (parseFloat(t.pnl_r) || 0);
        return cumR;
      });
      chartRefs.current.equity = new Chart(equityCanvasRef.current, {
        type: 'line',
        data: {
          labels: equityData.map((_, i) => i + 1),
          datasets: [{
            data: equityData,
            borderColor: '#eab308',
            borderWidth: 2,
            fill: true,
            backgroundColor: 'rgba(234, 179, 8, 0.04)',
            pointRadius: 3,
            pointBackgroundColor: '#eab308',
            tension: 0.3
          }]
        },
        options: {
          ...chartOpts,
          scales: {
            x: { display: true, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#52525b', font: { size: 10 } } },
            y: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#52525b', font: { size: 10 }, callback: v => v.toFixed(1) + 'R' } }
          }
        }
      });
    }

    // 2. Win / Loss Doughnut
    if (winlossCanvasRef.current) {
      chartRefs.current.winloss = new Chart(winlossCanvasRef.current, {
        type: 'doughnut',
        data: {
          labels: ['Wins', 'Losses', 'Break Even'],
          datasets: [{
            data: [wins.length, losses.length, closed.filter(t => t.status === 'BE').length],
            backgroundColor: ['#22c55e', '#ef4444', '#3b82f6'],
            borderWidth: 0
          }]
        },
        options: {
          ...chartOpts,
          cutout: '65%',
          plugins: {
            legend: {
              display: true,
              position: 'bottom',
              labels: { color: '#71717a', font: { size: 11 }, padding: 16 }
            }
          }
        }
      });
    }

    // 3. Session Performance
    if (sessionCanvasRef.current) {
      const sessionCounts = {};
      closed.forEach(t => {
        const s = t.session || 'Unknown';
        if (!sessionCounts[s]) sessionCounts[s] = { wins: 0, losses: 0 };
        if (t.status === 'WON') sessionCounts[s].wins++;
        else if (t.status === 'LOST') sessionCounts[s].losses++;
      });

      chartRefs.current.session = new Chart(sessionCanvasRef.current, {
        type: 'bar',
        data: {
          labels: Object.keys(sessionCounts),
          datasets: [
            { label: 'Wins', data: Object.values(sessionCounts).map(s => s.wins), backgroundColor: 'rgba(34, 197, 94, 0.7)', borderRadius: 4 },
            { label: 'Losses', data: Object.values(sessionCounts).map(s => s.losses), backgroundColor: 'rgba(239, 68, 68, 0.7)', borderRadius: 4 }
          ]
        },
        options: {
          ...chartOpts,
          scales: {
            x: { grid: { display: false }, ticks: { color: '#71717a', font: { size: 11 } } },
            y: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#52525b', font: { size: 10 } } }
          },
          plugins: {
            legend: {
              display: true,
              position: 'top',
              labels: { color: '#71717a', font: { size: 11 } }
            }
          }
        }
      });
    }

    // 4. R Gained Per Trade Bar
    if (rtradesCanvasRef.current) {
      const rData = closed.map(t => parseFloat(t.pnl_r) || 0);
      chartRefs.current.rtrades = new Chart(rtradesCanvasRef.current, {
        type: 'bar',
        data: {
          labels: rData.map((_, i) => '#' + (i + 1)),
          datasets: [{
            data: rData,
            backgroundColor: rData.map(v => v >= 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)'),
            borderRadius: 3
          }]
        },
        options: {
          ...chartOpts,
          scales: {
            x: { grid: { display: false }, ticks: { color: '#52525b', font: { size: 10 } } },
            y: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#52525b', font: { size: 10 }, callback: v => v + 'R' } }
          }
        }
      });
    }
  };

  // Math Calculations for Dashboard Stats
  const closedTrades = trades.filter(t => t.status === 'WON' || t.status === 'LOST' || t.status === 'BE');
  const openCount = trades.filter(t => t.status === 'OPEN').length;
  const winCount = trades.filter(t => t.status === 'WON').length;
  const lossCount = trades.filter(t => t.status === 'LOST').length;

  const winRate = closedTrades.length > 0 ? (winCount / closedTrades.length * 100).toFixed(1) : '0.0';
  const totalWinR = trades.filter(t => t.status === 'WON').reduce((s, t) => s + (parseFloat(t.pnl_r) || 0), 0);
  const totalLossR = Math.abs(trades.filter(t => t.status === 'LOST').reduce((s, t) => s + (parseFloat(t.pnl_r) || 0), 0));
  const profitFactor = totalLossR > 0 ? (totalWinR / totalLossR).toFixed(2) : totalWinR > 0 ? '∞' : '0.00';
  const netR = trades.reduce((sum, t) => sum + (parseFloat(t.pnl_r) || 0), 0);
  const expectancy = closedTrades.length > 0 ? (netR / closedTrades.length).toFixed(2) : '0.00';

  // Streak Calculator
  let currentStreak = 0;
  let streakType = '';
  for (let i = 0; i < closedTrades.length; i++) {
    if (i === 0) {
      streakType = closedTrades[i].status;
      currentStreak = 1;
    } else if (closedTrades[i].status === streakType) {
      currentStreak++;
    } else {
      break;
    }
  }

  // Filtered Journal list
  const filteredTrades = trades.filter(t => {
    if (filterDirection && t.direction !== filterDirection) return false;
    if (filterStatus && t.status !== filterStatus) return false;
    if (filterSession && t.session !== filterSession) return false;
    return true;
  });

  return (
    <div>
      {/* ── NOT AUTHENTICATED OVERLAY ── */}
      {!token && (
        <div className="modal-overlay">
          <div className="modal" style={{ maxWidth: '380px', padding: '32px', background: 'rgba(18, 19, 26, 0.95)' }}>
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
              <div className="nav-brand" style={{ justifyContent: 'center', fontSize: '24px', marginBottom: '8px' }}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
                <span>Au</span>Quant
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-dim)' }}>
                {authState === 'login' ? 'Log in to manage your trading journal' : 'Create an account to start journaling'}
              </p>
            </div>
            <form onSubmit={handleAuthSubmit}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="form-group">
                  <label>Email Address</label>
                  <input
                    type="email"
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                    required
                    placeholder="you@example.com"
                  />
                </div>
                <div className="form-group">
                  <label>Password</label>
                  <input
                    type="password"
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                  />
                </div>
                <button type="submit" className="btn btn-primary" style={{ padding: '12px', width: '100%', marginTop: '8px', justifyContent: 'center' }}>
                  {authState === 'login' ? 'Log In' : 'Sign Up'}
                </button>
              </div>
            </form>
            <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: 'var(--text-dim)' }}>
              <span>{authState === 'login' ? "Don't have an account?" : 'Already have an account?'}</span>
              <a
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  setAuthState(authState === 'login' ? 'register' : 'login');
                }}
                style={{ color: 'var(--gold)', fontWeight: 600, marginLeft: '4px', textDecoration: 'none' }}
              >
                {authState === 'login' ? 'Sign Up' : 'Log In'}
              </a>
            </div>
          </div>
        </div>
      )}

      {/* ── MAIN SAAS LAYOUT ── */}
      {token && (
        <>
          <nav className="nav">
            <div className="nav-brand">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2.5" strokeLinecap="round">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
              <span>Au</span>Quant
            </div>
            <div className="nav-tabs">
              <button className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('dashboard')}>
                Dashboard
              </button>
              <button className={`nav-tab ${activeTab === 'journal' ? 'active' : ''}`} onClick={() => setActiveTab('journal')}>
                Journal
              </button>
              <button className={`nav-tab ${activeTab === 'add' ? 'active' : ''}`} onClick={() => { resetForm(); setActiveTab('add'); }}>
                + Log Trade
              </button>
              <button className={`nav-tab ${activeTab === 'analysis' ? 'active' : ''}`} onClick={() => setActiveTab('analysis')}>
                Analysis
              </button>
            </div>
            <div className="nav-right">
              <div className="nav-status">
                <div className="dot" style={{ background: isConnected ? 'var(--green)' : 'var(--red)' }}></div>
                <span>{isConnected ? 'Connected' : 'Offline'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-dim)' }} title={userId}>{userEmail}</span>
                <button className="btn btn-secondary" onClick={handleLogout} style={{ padding: '6px 12px', fontSize: '11px', borderRadius: '6px' }}>
                  Logout
                </button>
              </div>
            </div>
          </nav>

          <div className="main">
            {/* ═══ DASHBOARD TAB ═══ */}
            {activeTab === 'dashboard' && (
              <div className="page">
                <div className="page-header-row">
                  <h2 className="page-title">Performance Overview</h2>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <button className="btn btn-secondary" onClick={exportToCSV}>
                      Export CSV (Backup)
                    </button>
                    <button className="btn btn-primary" onClick={exportToPDF}>
                      Generate Report (PDF)
                    </button>
                  </div>
                </div>

                <div className="stats-grid">
                  <div className="stat-card">
                    <div className="label">Total Trades</div>
                    <div className="value">{trades.length}</div>
                    <div className="sub">{openCount} open positions</div>
                  </div>
                  <div className="stat-card">
                    <div className="label">Win Rate</div>
                    <div className="value gold">{winRate}%</div>
                    <div className="sub">{winCount}W / {lossCount}L</div>
                  </div>
                  <div className="stat-card">
                    <div className="label">Profit Factor</div>
                    <div className="value green">{profitFactor}</div>
                    <div className="sub">R-Multiple Ratio</div>
                  </div>
                  <div className="stat-card">
                    <div className="label">Expectancy</div>
                    <div className="value blue">{expectancy}R</div>
                    <div className="sub">Average per trade</div>
                  </div>
                  <div className="stat-card">
                    <div className="label">Total R Gained</div>
                    <div className={`value ${netR >= 0 ? 'green' : 'red'}`}>
                      {netR >= 0 ? '+' : ''}{netR.toFixed(2)}R
                    </div>
                    <div className="sub">{currentStreak > 0 ? `${currentStreak} ${streakType.toLowerCase()} streak` : '—'}</div>
                  </div>
                </div>

                <div className="charts-row">
                  <div className="chart-card">
                    <h3>Cumulative R-Multiple</h3>
                    <div className="chart-wrap">
                      <canvas ref={equityCanvasRef}></canvas>
                    </div>
                  </div>
                  <div className="chart-card">
                    <h3>Win / Loss Distribution</h3>
                    <div className="chart-wrap">
                      <canvas ref={winlossCanvasRef}></canvas>
                    </div>
                  </div>
                </div>

                <div className="charts-row">
                  <div className="chart-card">
                    <h3>Performance by Session</h3>
                    <div className="chart-wrap">
                      <canvas ref={sessionCanvasRef}></canvas>
                    </div>
                  </div>
                  <div className="chart-card">
                    <h3>R-Multiple per Trade</h3>
                    <div className="chart-wrap">
                      <canvas ref={rtradesCanvasRef}></canvas>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ═══ JOURNAL TAB ═══ */}
            {activeTab === 'journal' && (
              <div className="page">
                <div className="page-header-row">
                  <h2 className="page-title">Trade Journal</h2>
                </div>

                <div className="table-container">
                  <div className="table-header">
                    <h3>All Trades</h3>
                    <span className="count">{filteredTrades.length} trades</span>
                  </div>

                  <div className="table-filters">
                    <select className="filter-select" value={filterDirection} onChange={(e) => setFilterDirection(e.target.value)}>
                      <option value="">Direction: All</option>
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                    </select>
                    <select className="filter-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                      <option value="">Status: All</option>
                      <option value="OPEN">OPEN</option>
                      <option value="WON">WON</option>
                      <option value="LOST">LOST</option>
                      <option value="BE">BREAK EVEN</option>
                    </select>
                    <select className="filter-select" value={filterSession} onChange={(e) => setFilterSession(e.target.value)}>
                      <option value="">Session: All</option>
                      <option value="London">London</option>
                      <option value="New York">New York</option>
                      <option value="Asia">Asia</option>
                    </select>
                  </div>

                  <div style={{ overflowX: 'auto' }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Direction</th>
                          <th>Entry</th>
                          <th>SL</th>
                          <th>TP</th>
                          <th>Exit</th>
                          <th>Status</th>
                          <th>R</th>
                          <th>Session</th>
                          <th>Setup</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredTrades.length === 0 ? (
                          <tr>
                            <td colSpan="11">
                              <div className="empty-state">No trades matching current filters found.</div>
                            </td>
                          </tr>
                        ) : (
                          filteredTrades.map(t => {
                            const r = parseFloat(t.pnl_r) || 0;
                            const dateStr = t.timestamp ? new Date(t.timestamp).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' }) : '—';
                            return (
                              <tr key={t.trade_id}>
                                <td>{dateStr}</td>
                                <td>
                                  <span className={`badge ${t.direction === 'BUY' ? 'buy' : 'sell'}`}>{t.direction}</span>
                                </td>
                                <td>{t.entry_price}</td>
                                <td>{t.sl}</td>
                                <td>{t.tp || '—'}</td>
                                <td>{t.exit_price || '—'}</td>
                                <td>
                                  <span className={`badge ${t.status.toLowerCase()}`}>{t.status}</span>
                                </td>
                                <td style={{ color: r >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                                  {t.status === 'OPEN' ? '—' : `${r >= 0 ? '+' : ''}${r.toFixed(2)}R`}
                                </td>
                                <td>{t.session || '—'}</td>
                                <td style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.technique}>
                                  {t.technique || '—'}
                                </td>
                                <td>
                                  <div className="actions-cell">
                                    <button className="btn-icon" onClick={() => openEditMode(t)} title="Edit">&#9998;</button>
                                    <button className="btn-icon delete" onClick={() => handleDeleteTrade(t.trade_id)} title="Delete">&#10005;</button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* ═══ ADD/EDIT TRADE TAB ═══ */}
            {activeTab === 'add' && (
              <div className="page">
                <h2 className="page-title">{formMode === 'edit' ? 'Edit Trade' : 'Log a Trade'}</h2>
                <div className="form-card">
                  <form onSubmit={handleTradeSubmit}>
                    <div className="form-grid">
                      <div className="form-group">
                        <label>Direction</label>
                        <select value={fDirection} onChange={(e) => setFDirection(e.target.value)} required>
                          <option value="BUY">BUY (Long)</option>
                          <option value="SELL">SELL (Short)</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Status</label>
                        <select value={fStatus} onChange={(e) => setFStatus(e.target.value)} required>
                          <option value="OPEN">OPEN</option>
                          <option value="WON">WON</option>
                          <option value="LOST">LOST</option>
                          <option value="BE">BREAK EVEN</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Entry Price</label>
                        <input
                          type="number"
                          step="0.01"
                          value={fEntry}
                          onChange={(e) => setFEntry(e.target.value)}
                          required
                          placeholder="2350.50"
                        />
                      </div>
                      <div className="form-group">
                        <label>Stop Loss</label>
                        <input
                          type="number"
                          step="0.01"
                          value={fSl}
                          onChange={(e) => setFSl(e.target.value)}
                          required
                          placeholder="2340.50"
                        />
                      </div>
                      <div className="form-group">
                        <label>Take Profit</label>
                        <input
                          type="number"
                          step="0.01"
                          value={fTp}
                          onChange={(e) => setFTp(e.target.value)}
                          placeholder="2375.00"
                        />
                      </div>
                      
                      {fStatus !== 'OPEN' && (
                        <div className="form-group">
                          <label>Exit Price</label>
                          <input
                            type="number"
                            step="0.01"
                            value={fExit}
                            onChange={(e) => setFExit(e.target.value)}
                            required
                            placeholder="2375.00"
                          />
                        </div>
                      )}

                      <div className="form-group">
                        <label>Session</label>
                        <select value={fSession} onChange={(e) => setFSession(e.target.value)}>
                          <option value="">— Select —</option>
                          <option value="Asia">Asia</option>
                          <option value="London">London</option>
                          <option value="New York">New York</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Timeframe</label>
                        <select value={fTimeframe} onChange={(e) => setFTimeframe(e.target.value)}>
                          <option value="">— Select —</option>
                          <option value="1M">1M</option>
                          <option value="5M">5M</option>
                          <option value="15M">15M</option>
                          <option value="1H">1H</option>
                          <option value="4H">4H</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Technique / Setup</label>
                        <input
                          type="text"
                          value={fTechnique}
                          onChange={(e) => setFTechnique(e.target.value)}
                          placeholder="e.g. Order Block, FVG Tap"
                        />
                      </div>
                      {fStatus === 'LOST' && (
                        <div className="form-group">
                          <label>Failure Cause</label>
                          <select value={fFailure} onChange={(e) => setFFailure(e.target.value)}>
                            <option value="">— Select —</option>
                            <option value="FOMO">FOMO</option>
                            <option value="Overtrading">Overtrading</option>
                            <option value="Early Exit">Early Exit</option>
                            <option value="Stop Hunt Sweep">Stop Hunt Sweep</option>
                            <option value="Trend Against">Trend Against</option>
                            <option value="News Impact">News Impact</option>
                          </select>
                        </div>
                      )}
                      <div className="form-group full">
                        <label>Confirmations</label>
                        <textarea
                          value={fConfirmations}
                          onChange={(e) => setFConfirmations(e.target.value)}
                          placeholder="e.g. Liquidity Sweep, MSS, FVG Alignment"
                        ></textarea>
                      </div>
                    </div>
                    <div className="form-actions">
                      <button type="button" className="btn btn-secondary" onClick={resetForm}>
                        Clear
                      </button>
                      <button type="submit" className="btn btn-primary">
                        {formMode === 'edit' ? 'Save Changes' : 'Log Trade'}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* ═══ ANALYSIS TAB ═══ */}
            {activeTab === 'analysis' && (
              <div className="page">
                <div className="page-header-row">
                  <h2 className="page-title">Strategy Analysis</h2>
                  <button className="btn btn-primary" onClick={runDirectiveAnalysis} disabled={isAnalyzing}>
                    {isAnalyzing ? 'Analyzing...' : 'Generate Directives'}
                  </button>
                </div>

                {directiveReport ? (
                  <div className="analysis-section" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                    <div style={{ whiteSpace: 'pre-wrap', fontSize: '13px', lineHeight: '1.7', color: 'var(--text)' }}>
                      {directiveReport}
                    </div>
                  </div>
                ) : (
                  <div className="empty-state">
                    <p>Run the quantitative strategy directives generator to view your autopsy insights.</p>
                    <button className="btn btn-primary" style={{ marginTop: '16px' }} onClick={runDirectiveAnalysis}>
                      Generate Directives
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* ── TOAST MESSAGE ── */}
      <div className={`toast ${toastType} ${showToast ? 'show' : ''}`}>{toastMsg}</div>
    </div>
  );
}

export default App;
