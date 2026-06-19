import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import requests
from config import settings
from db import get_db

def load_data() -> pd.DataFrame:
    """Fetch closed trades from database and return as pandas DataFrame."""
    try:
        db = get_db()
        trades = db.get_closed_trades()
        if not trades:
            return pd.DataFrame()
        return pd.DataFrame(trades)
    except Exception as e:
        print(f"Error loading trades from database: {e}")
        return pd.DataFrame()

def send_discord_report(report_md: str):
    """Sends the daily Trading Directive report to Discord as an embed."""
    if not settings.DISCORD_WEBHOOK_URL:
        return
        
    payload = {
        "embeds": [
            {
                "title": "📊 Daily GOLD Strategy Autopsy & Directive",
                "description": report_md[:4000],
                "color": 2123412, # Gold Color equivalent (approx hex 20676C)
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    }
    
    try:
        response = requests.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code not in [200, 204]:
            print(f"Discord API returned error code {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Failed to send Discord webhook: {e}")

def run_autopsy(df: pd.DataFrame) -> str:
    """Perform quantitative analysis on Gold confirmations/sessions and generate directives."""
    # Ensure datatypes
    df['pnl_r'] = df['pnl_r'].astype(float)
    df['entry_price'] = df['entry_price'].astype(float)
    df['sl'] = df['sl'].astype(float)
    df['tp'] = df['tp'].astype(float)
    
    # 1. Global Performance metrics
    total_trades = len(df)
    won_trades = df[df['status'] == 'WON']
    lost_trades = df[df['status'] == 'LOST']
    
    win_rate = (len(won_trades) / total_trades) * 100 if total_trades > 0 else 0.0
    
    total_profit_r = won_trades['pnl_r'].sum()
    total_loss_r = abs(lost_trades['pnl_r'].sum())
    
    profit_factor = total_profit_r / total_loss_r if total_loss_r > 0 else (total_profit_r if total_profit_r > 0 else 1.0)
    net_r = df['pnl_r'].sum()
    
    avg_win_r = won_trades['pnl_r'].mean() if len(won_trades) > 0 else 0.0
    avg_loss_r = lost_trades['pnl_r'].mean() if len(lost_trades) > 0 else 0.0
    
    best_trade = df['pnl_r'].max()
    worst_trade = df['pnl_r'].min()
    
    report = []
    report.append(f"# XAUUSD Performance Autopsy - {datetime.utcnow().strftime('%Y-%m-%d')}\n")
    
    report.append("## 📈 Global Performance Metrics")
    report.append("| Metric | Value |")
    report.append("| :--- | :--- |")
    report.append(f"| **Total Closed Trades** | {total_trades} |")
    report.append(f"| **Win Rate (GOLD)** | {win_rate:.2f}% ({len(won_trades)}W / {len(lost_trades)}L) |")
    report.append(f"| **Net R-Multiple Gained** | {net_r:+.2f}R |")
    report.append(f"| **Profit Factor (R-based)** | {profit_factor:.2f} |")
    report.append(f"| **Average Win / Loss** | {avg_win_r:+.2f}R / {avg_loss_r:+.2f}R |")
    report.append(f"| **Best / Worst Trade** | {best_trade:+.2f}R / {worst_trade:+.2f}R |")
    report.append("\n" + "---" + "\n")
    
    # 2. Performance by Session
    report.append("## 🕒 Session Execution Metrics")
    if 'session' in df.columns and df['session'].dropna().nunique() > 0:
        session_groups = df.groupby('session')
        report.append("| Session | Count | Win Rate | Net R | Profit Factor |")
        report.append("| :--- | :---: | :---: | :---: | :---: |")
        for name, group in session_groups:
            s_total = len(group)
            s_won = group[group['status'] == 'WON']
            s_lost = group[group['status'] == 'LOST']
            s_win = (len(s_won) / s_total) * 100
            s_net = group['pnl_r'].sum()
            s_prof = s_won['pnl_r'].sum()
            s_los = abs(s_lost['pnl_r'].sum())
            s_pf = s_prof / s_los if s_los > 0 else s_prof
            
            report.append(f"| {name} | {s_total} | {s_win:.1f}% | {s_net:+.2f}R | {s_pf:.2f} |")
    else:
        report.append("*No session data recorded.*")
    report.append("\n" + "---" + "\n")
    
    # 3. Performance by Timeframe
    report.append("## 📐 Timeframe Structure Metrics")
    if 'timeframe' in df.columns and df['timeframe'].dropna().nunique() > 0:
        tf_groups = df.groupby('timeframe')
        report.append("| Timeframe | Count | Win Rate | Net R |")
        report.append("| :--- | :---: | :---: | :---: |")
        for name, group in tf_groups:
            t_total = len(group)
            t_won = group[group['status'] == 'WON']
            t_win = (len(t_won) / t_total) * 100
            t_net = group['pnl_r'].sum()
            
            report.append(f"| {name} | {t_total} | {t_win:.1f}% | {t_net:+.2f}R |")
    else:
        report.append("*No timeframe details recorded.*")
    report.append("\n" + "---" + "\n")

    # 4. Confirmation Tag Analytics
    report.append("## 🔍 Confirmation Expectancy Analysis")
    conf_stats = []
    if 'confirmations' in df.columns:
        conf_counts = {}
        for _, r in df.iterrows():
            conf_str = r.get("confirmations")
            if pd.isna(conf_str) or not conf_str:
                continue
            confs = [c.strip() for c in conf_str.split(",") if c.strip()]
            for c in confs:
                if c not in conf_counts:
                    conf_counts[c] = {"total": 0, "won": 0, "lost": 0, "pnl_r": 0.0}
                conf_counts[c]["total"] += 1
                if r["status"] == "WON":
                    conf_counts[c]["won"] += 1
                elif r["status"] == "LOST":
                    conf_counts[c]["lost"] += 1
                conf_counts[c]["pnl_r"] += float(r["pnl_r"])
                
        if conf_counts:
            report.append("| Confirmation Tag | Count | Win Rate | Net Expectancy |")
            report.append("| :--- | :---: | :---: | :---: |")
            for name, stats in conf_counts.items():
                win_pct = (stats["won"] / stats["total"]) * 100
                conf_stats.append({
                    "name": name,
                    "count": stats["total"],
                    "win_rate": win_pct,
                    "net_r": stats["pnl_r"]
                })
                report.append(f"| {name} | {stats['total']} | {win_pct:.1f}% | {stats['pnl_r']:+.2f}R |")
        else:
            report.append("*No confirmation tags logged.*")
    else:
        report.append("*No confirmations column detected.*")
    report.append("\n" + "---" + "\n")
    
    # 5. Failure Cause Autopsy
    report.append("## 🕵️ Failure Cause Analysis")
    if 'failure_cause' in df.columns and df['failure_cause'].dropna().nunique() > 0:
        losses_df = df[df['status'] == 'LOST']
        if len(losses_df) > 0:
            cause_counts = losses_df['failure_cause'].value_counts()
            report.append("| Failure Cause | Count | % of Losses |")
            report.append("| :--- | :---: | :---: |")
            for cause, count in cause_counts.items():
                pct = (count / len(losses_df)) * 100
                report.append(f"| {cause} | {count} | {pct:.1f}% |")
        else:
            report.append("*No losing trades recorded. Clean sheet!*")
    else:
        report.append("*No failure cause details logged.*")
    report.append("\n" + "---" + "\n")
    
    # 6. Actionable Trading Directive (Rules Engine)
    report.append("## 🎯 Actionable Trading Directive")
    
    double_down = []
    change_list = []
    stop_list = []
    
    # Session directives
    if 'session' in df.columns and df['session'].dropna().nunique() > 0:
        session_stats = df.groupby('session').agg(
            count=('status', 'count'),
            win_rate=('status', lambda x: (sum(x == 'WON') / len(x)) * 100),
            net_r=('pnl_r', 'sum')
        )
        for s_name, row in session_stats.iterrows():
            if row['count'] >= 3:
                if row['win_rate'] >= 60.0 and row['net_r'] > 0:
                    double_down.append(f"Execute in **{s_name} Session** (Win Rate: {row['win_rate']:.1f}%, Net R: {row['net_r']:+.1f}R)")
                elif row['win_rate'] < 40.0:
                    stop_list.append(f"Avoid trading GOLD in **{s_name} Session** (Win Rate: {row['win_rate']:.1f} over {row['count']} trades). Expectancy is negative.")

    # Confirmation tag directives
    for c in conf_stats:
        if c['count'] >= 3:
            if c['win_rate'] >= 65.0:
                double_down.append(f"Double down on entries with **{c['name']}** confirmation (Win Rate: {c['win_rate']:.1f}%).")
            elif c['win_rate'] < 35.0:
                stop_list.append(f"Stop taking setups referencing **{c['name']}** (Win Rate: {c['win_rate']:.1f}%). Retest confirmation metrics.")

    # Timeframe directives
    if 'timeframe' in df.columns and df['timeframe'].dropna().nunique() > 0:
        tf_stats = df.groupby('timeframe').agg(
            count=('status', 'count'),
            win_rate=('status', lambda x: (sum(x == 'WON') / len(x)) * 100)
        )
        for tf, row in tf_stats.iterrows():
            if row['count'] >= 3:
                if row['win_rate'] < 40.0:
                    change_list.append(f"Re-evaluate timeframe layout **{tf}** (Win Rate: {row['win_rate']:.1f}%). Tighten SL definitions.")

    # Mental/Failure cause directives
    if 'failure_cause' in df.columns and len(df[df['status'] == 'LOST']) > 0:
        losses_df = df[df['status'] == 'LOST']
        cause_pct = losses_df['failure_cause'].value_counts(normalize=True) * 100
        for cause, pct in cause_pct.items():
            if pct >= 40.0:
                change_list.append(f"**{cause}** is responsible for {pct:.1f}% of all losses. Establish strict rules to eliminate this trigger.")

    # Format output lists
    if double_down:
        report.append("### 🔥 Double Down On")
        for item in double_down:
            report.append(f"- {item}")
    else:
        report.append("### 🔥 Double Down On\n- *No high-win-rate session or confirmation edge identified yet.*")
        
    if change_list:
        report.append("\n### 🛠️ What to Change")
        for item in change_list:
            report.append(f"- {item}")
    else:
        report.append("\n### 🛠️ What to Change\n- *No major structure adjustments flagged.*")
        
    if stop_list:
        report.append("\n### 🚫 What to Stop")
        for item in stop_list:
            report.append(f"- {item}")
    else:
        report.append("\n### 🚫 What to Stop\n- *No negative expectancy limiters identified yet.*")

    return "\n".join(report)

def main():
    print("Initializing statistical autopsy...")
    df = load_data()
    
    if df.empty:
        print("No closed trades found in the data store. Exiting analysis.")
        sys.exit(0)
        
    report_md = run_autopsy(df)
    
    print("\n=======================================================")
    print(report_md)
    print("=======================================================\n")
    
    # Save report locally
    os.makedirs("reports", exist_ok=True)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    daily_report_path = f"reports/directive_{today_str}.md"
    with open(daily_report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Daily analysis saved to: {daily_report_path}")
    
    latest_report_path = "reports/latest_directive.md"
    with open(latest_report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
        
    send_discord_report(report_md)
    print("Statistical autopsy completed successfully.")

if __name__ == "__main__":
    main()
