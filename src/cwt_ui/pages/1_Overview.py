# pages/1_Overview.py — Overview (default home)
from __future__ import annotations

import sys
from pathlib import Path

for p in [Path(__file__).resolve().parent, *Path(__file__).resolve().parent.parents]:
    if (p / "src").exists() and str(p / "src") not in sys.path:
        sys.path.insert(0, str(p / "src"))
        break

import pandas as pd
import streamlit as st

from cwt_ui.components.ui.header import render_page_header
from cwt_ui.services.spend_aggregate import get_spend_from_scan, get_optimization_metrics
from cwt_ui.services.synthetic_data import load_synthetic_data_into_session
from cwt_ui.utils.money import format_usd

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

# --- 8pt grid, softer shadows, modern palette ---
st.markdown("""
<style>
    /* 8pt base */
    .overview-root { --space-1: 8px; --space-2: 16px; --space-3: 24px; --space-4: 32px; }
    /* Service colors (consistent across app) */
    .overview-service-ec2 { --service-color: #f59e0b; }
    .overview-service-sp-covered { --service-color: #10b981; }
    .overview-service-sp-ondemand { --service-color: #06b6d4; }
    .overview-service-lambda { --service-color: #8b5cf6; }
    .overview-service-fargate { --service-color: #ec4899; }
    /* Hero: primary KPI */
    .overview-hero {
        background: linear-gradient(145deg, #0f172a 0%, #1e293b 50%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: var(--space-3, 24px) var(--space-4, 32px);
        margin-bottom: var(--space-2, 16px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .overview-hero-label { font-size: 0.8rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }
    .overview-hero-value { font-size: 2.25rem; font-weight: 700; color: #22c55e; line-height: 1.2; }
    .overview-hero-sub { font-size: 0.85rem; color: #64748b; margin-top: 8px; }
    /* Secondary row: 3 equal cards */
    .overview-sec-card {
        background: linear-gradient(145deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2d3548;
        border-radius: 12px;
        padding: var(--space-2, 16px);
        margin-bottom: var(--space-1, 8px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .overview-sec-label { font-size: 0.75rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
    .overview-sec-value { font-size: 1.35rem; font-weight: 700; color: #f1f5f9; }
    .overview-sec-meta { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
    /* Section titles */
    .overview-section { font-size: 0.95rem; font-weight: 600; color: #cbd5e1; margin: var(--space-3, 24px) 0 var(--space-1, 8px) 0; padding-bottom: 8px; border-bottom: 1px solid #334155; }
    /* Spend bar (stacked proportions) */
    .overview-spend-bar { display: flex; height: 24px; border-radius: 8px; overflow: hidden; margin: 8px 0; background: #1e293b; }
    .overview-spend-seg { flex-grow: 0; flex-shrink: 0; min-width: 4px; }
    /* EC2 + SP cost breakdown card */
    .overview-breakdown-card {
        background: linear-gradient(145deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2d3548;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .overview-breakdown-title { font-size: 0.85rem; font-weight: 600; color: #94a3b8; margin-bottom: 4px; }
    .overview-breakdown-total { font-size: 1.5rem; font-weight: 700; color: #f1f5f9; margin-bottom: 16px; }
    .overview-breakdown-bar { display: flex; height: 28px; border-radius: 8px; overflow: hidden; margin: 12px 0; background: #0f172a; }
    .overview-breakdown-seg { flex-grow: 0; flex-shrink: 0; min-width: 6px; }
    .overview-breakdown-legend { display: flex; flex-wrap: wrap; gap: 20px 24px; margin-top: 12px; font-size: 0.9rem; }
    .overview-breakdown-legend-item { display: flex; align-items: center; gap: 6px; }
    .overview-breakdown-legend-dot { width: 10px; height: 10px; border-radius: 4px; }
    .overview-breakdown-legend-label { color: #cbd5e1; }
    .overview-breakdown-legend-value { font-weight: 600; color: #f1f5f9; }
    .overview-breakdown-context { font-size: 0.8rem; color: #64748b; margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155; }
    /* What changed */
    .overview-delta-box { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px; margin-top: 8px; }
    .overview-delta-item { font-size: 0.9rem; color: #cbd5e1; margin-bottom: 4px; }
    .overview-delta-item .up { color: #22c55e; }
    .overview-delta-item .down { color: #f59e0b; }
    /* Recommendation card */
    .overview-rec-card {
        background: #1e293b; border: 1px solid #334155; border-radius: 12px;
        padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .overview-rec-header { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
    .overview-rec-severity { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; padding: 2px 8px; border-radius: 6px; }
    .overview-rec-severity.critical { background: #7f1d1d; color: #fecaca; }
    .overview-rec-severity.moderate { background: #78350f; color: #fde68a; }
    .overview-rec-severity.low { background: #1e3a5f; color: #93c5fd; }
    .overview-rec-id { font-weight: 600; color: #f1f5f9; }
    .overview-rec-savings { color: #22c55e; font-weight: 600; font-size: 0.9rem; }
    .overview-rec-text { font-size: 0.9rem; color: #94a3b8; margin: 8px 0; }
    .overview-rec-meta { font-size: 0.8rem; color: #64748b; }
    /* Data badge */
    .overview-data-badge { display: inline-block; background: #334155; color: #94a3b8; font-size: 0.7rem; padding: 4px 8px; border-radius: 6px; margin-left: 8px; }
    .overview-data-badge.synthetic { background: #1e3a5f; color: #7dd3fc; }
    /* CTA block */
    .overview-cta-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-top: 16px; }
</style>
""", unsafe_allow_html=True)

render_page_header(
    title="Overview",
    subtitle="What's happening and what to do next.",
    icon="📊",
)

# --- Data source bar ---
data_source = st.session_state.get("data_source", "none")
with st.container():
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("📥 Load synthetic data", type="secondary", help="Load demo data to explore without an active AWS account."):
            load_synthetic_data_into_session()
            st.rerun()
    with c2:
        if data_source == "synthetic":
            st.markdown('<span class="overview-data-badge synthetic">Using synthetic data</span>', unsafe_allow_html=True)
            st.caption("Run a scan from **Setup** to replace with live AWS data.")

# --- Data from session state ---
ec2_df = st.session_state.get("ec2_df", pd.DataFrame())
last_scan_at = st.session_state.get("last_scan_at", "")
spend_total_usd, spend_df = get_spend_from_scan()

optimization_potential = st.session_state.get("optimization_potential")
action_count = st.session_state.get("action_count")
if optimization_potential is None or action_count is None:
    optimization_potential, action_count = get_optimization_metrics(ec2_df) if ec2_df is not None and not ec2_df.empty else (0.0, 0)
else:
    optimization_potential = float(optimization_potential)
    action_count = int(action_count)

prev_opt = st.session_state.get("previous_optimization_potential")
prev_act = st.session_state.get("previous_action_count")
has_prev = prev_opt is not None and prev_act is not None

# ----- 1. What's happening: Hero + secondary row -----
st.markdown('<p class="overview-section">What\'s happening</p>', unsafe_allow_html=True)

# Hero: one large card — Potential Savings (primary KPI)
hero_col, _ = st.columns([2, 1])
with hero_col:
    st.markdown(
        f'''
        <div class="overview-hero">
            <div class="overview-hero-label">Potential savings (primary KPI)</div>
            <div class="overview-hero-value">{format_usd(optimization_potential) if optimization_potential else "—"}</div>
            <div class="overview-hero-sub">Estimated monthly savings from current recommendations. Review actions below.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

# Secondary row: 3 equal cards — Spend, Budget, Actions
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        f'''
        <div class="overview-sec-card">
            <div class="overview-sec-label">Total cloud spend</div>
            <div class="overview-sec-value">{format_usd(spend_total_usd) if spend_total_usd and spend_total_usd > 0 else "—"}</div>
            <div class="overview-sec-meta">{"Full service list" if data_source == "synthetic" else "EC2 + Savings Plans"} from last scan.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.caption("From last scan. See **Spend** for breakdown.")
with col2:
    st.markdown(
        '''
        <div class="overview-sec-card">
            <div class="overview-sec-label">Budget consumption</div>
            <div class="overview-sec-value">—</div>
            <div class="overview-sec-meta">Set monthly or quarterly budgets per account or team.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.caption("Coming in **Budgets & Forecast**. Set targets and track variance.")
with col3:
    st.markdown(
        f'''
        <div class="overview-sec-card">
            <div class="overview-sec-label">Actions recommended</div>
            <div class="overview-sec-value">{action_count if (ec2_df is not None and not ec2_df.empty) or action_count else "—"}</div>
            <div class="overview-sec-meta">Items needing attention. Sort and filter below.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.caption("Items needing attention. Review in **Optimization**.")

# Tertiary: Last scan + "What changed since last scan"
st.markdown('<p class="overview-section">Data & changes</p>', unsafe_allow_html=True)
scan_col1, scan_col2 = st.columns([1, 1])
with scan_col1:
    last_scan_display = (last_scan_at[:16] if last_scan_at and len(last_scan_at) > 16 else last_scan_at) or "Never"
    st.markdown(
        f'''
        <div class="overview-delta-box">
            <div class="overview-delta-item"><strong>Last scan:</strong> {last_scan_display}</div>
            <div class="overview-delta-item" style="font-size:0.8rem;color:#64748b;">Scans run on demand from Setup. Re-run to refresh.</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
with scan_col2:
    if has_prev and (prev_opt is not None or prev_act is not None):
        lines = []
        if prev_opt is not None:
            diff = optimization_potential - float(prev_opt)
            if diff > 0:
                lines.append(f'<span class="up">Potential savings ↑ {format_usd(diff)}</span>')
            elif diff < 0:
                lines.append(f'<span class="down">Potential savings ↓ {format_usd(-diff)}</span>')
            else:
                lines.append("Potential savings unchanged")
        if prev_act is not None:
            d = action_count - int(prev_act)
            if d > 0:
                lines.append(f'<span class="up">Actions ↑ {d}</span>')
            elif d < 0:
                lines.append(f'<span class="down">Actions ↓ {-d}</span>')
            else:
                lines.append("Action count unchanged")
        st.markdown(
            f'<div class="overview-delta-box"><div class="overview-delta-item"><strong>Since last scan:</strong></div>'
            + "".join(f'<div class="overview-delta-item">{x}</div>' for x in lines) + "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="overview-delta-box"><div class="overview-delta-item">Run another scan to see changes vs. last run.</div></div>',
            unsafe_allow_html=True,
        )

# ----- Spend by category + top cost drivers + cost breakdown bar -----
st.markdown('<p class="overview-section">Spend by category</p>', unsafe_allow_html=True)
CATEGORY_COLORS = {
    "Compute": "#f59e0b",
    "Storage": "#3b82f6",
    "Containers": "#ec4899",
    "Networking": "#06b6d4",
    "Databases": "#8b5cf6",
    "Monitoring": "#10b981",
    "Commitment": "#22c55e",
    "Other": "#64748b",
}
if not spend_df.empty and spend_total_usd and spend_total_usd > 0:
    by_service = spend_df.groupby("service", as_index=False)["amount_usd"].sum().sort_values("amount_usd", ascending=False)
    top5 = by_service.head(5)
    top_drivers = " · ".join([f"<strong>{r['service']}</strong> {format_usd(r['amount_usd'])}" for _, r in top5.iterrows()])

    if "category" in spend_df.columns and spend_df["category"].notna().any():
        by_cat = spend_df.groupby("category", as_index=False)["amount_usd"].sum().sort_values("amount_usd", ascending=False)
        total_cat = by_cat["amount_usd"].sum()
        if total_cat > 0:
            segs = []
            leg_items = []
            for _, row in by_cat.iterrows():
                cat = row["category"]
                amt = float(row["amount_usd"])
                pct = round(100 * amt / total_cat, 1)
                color = CATEGORY_COLORS.get(cat, "#64748b")
                segs.append(f'<div class="overview-breakdown-seg" style="width:{max(0.5, 100*amt/total_cat)}%;background:{color};" title="{cat} {format_usd(amt)}"></div>')
                leg_items.append(
                    f'<span class="overview-breakdown-legend-item">'
                    f'<span class="overview-breakdown-legend-dot" style="background:{color};"></span>'
                    f'<span class="overview-breakdown-legend-label">{cat}</span>'
                    f'<span class="overview-breakdown-legend-value">{format_usd(amt)} ({pct}%)</span></span>'
                )
            bar_html = (
                f'<div class="overview-breakdown-bar">{"".join(segs)}</div>'
                f'<div class="overview-breakdown-legend">{"".join(leg_items)}</div>'
            )
        else:
            bar_html = ""
    else:
        covered_usd = float(by_service.loc[by_service["service"] == "Savings Plans (covered)", "amount_usd"].sum())
        ondemand_services = ["EC2", "EC2-Instances", "EC2-Other", "Savings Plans (on-demand)"]
        ondemand_usd = float(by_service.loc[by_service["service"].isin(ondemand_services), "amount_usd"].sum())
        total_breakdown = covered_usd + ondemand_usd
        if total_breakdown > 0:
            covered_pct = round(100 * covered_usd / total_breakdown, 1)
            ondemand_pct = round(100 * ondemand_usd / total_breakdown, 1)
            bar_html = (
                f'<div class="overview-breakdown-bar">'
                f'<div class="overview-breakdown-seg" style="width:{max(0.5, 100*covered_usd/total_breakdown)}%;background:#10b981;" title="Covered by SP"></div>'
                f'<div class="overview-breakdown-seg" style="width:{max(0.5, 100*ondemand_usd/total_breakdown)}%;background:#ea580c;" title="On-Demand"></div>'
                f'</div>'
                f'<div class="overview-breakdown-legend">'
                f'<span class="overview-breakdown-legend-item"><span class="overview-breakdown-legend-dot" style="background:#10b981;"></span>'
                f'<span class="overview-breakdown-legend-label">Covered by Savings Plans</span>'
                f'<span class="overview-breakdown-legend-value">{format_usd(covered_usd)} ({covered_pct}%)</span></span>'
                f'<span class="overview-breakdown-legend-item"><span class="overview-breakdown-legend-dot" style="background:#ea580c;"></span>'
                f'<span class="overview-breakdown-legend-label">On-Demand</span>'
                f'<span class="overview-breakdown-legend-value">{format_usd(ondemand_usd)} ({ondemand_pct}%)</span></span>'
                f'</div>'
            )
        else:
            bar_html = ""
    context_parts = []
    if last_scan_at:
        context_parts.append("Re-run a scan from Setup to refresh.")
    if optimization_potential and optimization_potential > 0:
        context_parts.append(f"Potential savings: {format_usd(optimization_potential)}/mo.")
    context_html = " ".join(context_parts) if context_parts else "See <strong>Spend</strong> for filters and export."
    st.markdown(
        f'''
        <div class="overview-breakdown-card">
            <div class="overview-breakdown-title">Total cloud spend</div>
            <div class="overview-breakdown-total">{format_usd(spend_total_usd)}</div>
            <div class="overview-breakdown-context" style="margin-bottom:8px;"><strong>Top cost drivers:</strong> {top_drivers}</div>
            {bar_html}
            <div class="overview-breakdown-context">{context_html}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    st.caption("See **Spend** for full breakdown by service and category.")
else:
    st.markdown(
        '<div class="overview-breakdown-card">'
        '<div class="overview-breakdown-title">Total cloud spend</div>'
        '<div class="overview-breakdown-total">—</div>'
        '<div class="overview-breakdown-context">No spend data yet. Run a scan or load synthetic data from Overview.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption("Load synthetic data or run a scan to see spend by category.")

# ----- 2. What should I do: Recommendations -----
st.markdown('<p class="overview-section">What should I do?</p>', unsafe_allow_html=True)

def _severity(savings: float) -> tuple[str, str]:
    if savings >= 100:
        return "critical", "Critical waste"
    if savings >= 20:
        return "moderate", "Moderate waste"
    return "low", "Low priority"

if ec2_df is not None and not ec2_df.empty and action_count > 0:
    savings_col = next((c for c in ["potential_savings_usd", "Potential Savings ($)", "potential_savings"] if c in ec2_df.columns), None)
    id_col = next((c for c in ["instance_id", "InstanceId", "Instance ID"] if c in ec2_df.columns), None)
    rec_col = next((c for c in ["recommendation", "Recommendation"] if c in ec2_df.columns), None)
    dept_col = "department" if "department" in ec2_df.columns else None

    if savings_col and id_col and rec_col:
        # Start here: single biggest lever (ensure best is always a row, not a scalar)
        ser_all = pd.to_numeric(ec2_df[savings_col], errors="coerce").fillna(0)
        if ser_all.astype(float).sum() > 0:
            best_idx = ser_all.idxmax()
            best_row = ec2_df.loc[best_idx]
            best = best_row.iloc[0] if isinstance(best_row, pd.DataFrame) else best_row
            best_id = best.get(id_col, "—") if hasattr(best, "get") else str(best)
            best_savings = best.get(savings_col, 0) if hasattr(best, "get") else 0
            st.markdown(
                f'<div class="overview-delta-box" style="border-left:4px solid #22c55e;">'
                f'<div class="overview-delta-item">🎯 <strong>Start here:</strong> <span class="overview-rec-id">{best_id}</span> — '
                f'<span class="overview-rec-savings">{format_usd(best_savings)}/mo</span> if you apply the recommendation.</div></div>',
                unsafe_allow_html=True,
            )
        # Sort options (Savings, ID, Department if available)
        sort_opts = ["Savings impact (highest first)", "Instance ID"]
        if dept_col and dept_col in ec2_df.columns:
            sort_opts.append("Department (team)")
        sort_by = st.selectbox(
            "Sort recommendations by",
            sort_opts,
            key="overview_rec_sort",
            help="Order by savings impact, instance ID, or department.",
        )
        ser = pd.to_numeric(ec2_df[savings_col], errors="coerce").fillna(0)
        rec_df_full = ec2_df.copy()
        if sort_by == "Savings impact (highest first)":
            rec_df_full = rec_df_full.sort_values(savings_col, ascending=False)
        elif sort_by == "Instance ID":
            rec_df_full = rec_df_full.sort_values(id_col, ascending=True)
        else:
            if dept_col and dept_col in rec_df_full.columns:
                rec_df_full = rec_df_full.sort_values([dept_col, savings_col], ascending=[True, False])
            else:
                rec_df_full = rec_df_full.sort_values(savings_col, ascending=False)
        rec_count = len(rec_df_full)
        rec_df_display = rec_df_full.head(5)

        for idx, row in rec_df_display.iterrows():
            save_val = float(row.get(savings_col, 0) or 0)
            sev_key, sev_label = _severity(save_val)
            inst_id = row.get(id_col, "—")
            rec_text = row.get(rec_col, "—")
            dept = row.get(dept_col, "") if dept_col else ""
            # Plain-language confidence
            confidence = "Based on CPU/memory usage from scan. Apply in Optimization after review."
            with st.expander(f"**{inst_id}** — {format_usd(save_val)}/mo · {sev_label}", expanded=False):
                st.markdown(f"**Recommendation:** {rec_text}")
                st.caption(f"*{confidence}*")
                if dept:
                    st.caption(f"Department / project: {dept}")
                # Quick actions (UI only; persistence can be added later)
                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("Mark as intentional", key=f"intent_{idx}_{inst_id}", help="Exclude from future counts (coming soon)"):
                        st.info("Mark-as-intentional will be saved in a future release.")
                with b2:
                    if st.button("Ignore for 30 days", key=f"ignore_{idx}_{inst_id}", help="Snooze this recommendation (coming soon)"):
                        st.info("Ignore-for-30-days will be saved in a future release.")
                with b3:
                    try:
                        st.page_link("pages/4_Optimization.py", label="Review in Optimization →", icon="🔧")
                    except Exception:
                        st.markdown("[Review in **Optimization** →](pages/4_Optimization.py)")
        if rec_count > 5:
            st.markdown("")  # spacing
            try:
                st.page_link("pages/4_Optimization.py", label=f"View all {rec_count} suggestions in Optimization →", icon="📋")
            except Exception:
                st.markdown(f"[**View all {rec_count} suggestions in Optimization** →](pages/4_Optimization.py)")
            st.caption("Showing top 5 by current sort. Open Optimization to filter, sort, and act on all.")
    else:
        st.markdown("Recommendation columns not found. Open **Optimization** for full table.")
else:
    st.markdown("No optimization recommendations yet.")
    st.caption("Load **synthetic data** or run a scan from **Setup**, then open **Optimization**.")

# ----- Clear CTAs -----
st.markdown('<p class="overview-section">Next steps</p>', unsafe_allow_html=True)
if action_count > 0:
    try:
        st.page_link("pages/4_Optimization.py", label=f"Review all {action_count} recommendations", icon="✅")
    except Exception:
        st.markdown(f"[**Review all {action_count} recommendations** →](pages/4_Optimization.py)")
    st.caption("Primary action: review and apply recommendations in Optimization.")
    if st.button("Automate low-risk actions", key="cta_automate", help="Bulk apply stop/schedule for low-risk items. Coming soon."):
        st.info("Automation for low-risk actions is planned. Use Optimization to act on items manually for now.")
else:
    try:
        st.page_link("pages/4_Optimization.py", label="Open Optimization", icon="🔧")
    except Exception:
        st.markdown("[Open **Optimization** →](pages/4_Optimization.py)")

# ----- Quick links -----
st.markdown('<p class="overview-section">Quick links</p>', unsafe_allow_html=True)
try:
    link_col1, link_col2, link_col3, link_col4 = st.columns(4)
    with link_col1:
        st.page_link("pages/2_Spend.py", label="Spend", icon="💰", help="Where money goes.")
    with link_col2:
        st.page_link("pages/3_Budgets_Forecast.py", label="Budgets & Forecast", icon="📈", help="Budgets, forecasts, variance.")
    with link_col3:
        st.page_link("pages/4_Optimization.py", label="Optimization", icon="🔧", help="Waste, rightsizing, recommendations.")
    with link_col4:
        st.page_link("pages/5_Governance.py", label="Governance", icon="🛡️", help="Policies, violations, approvals.")
except Exception:
    st.markdown("- **Spend** · **Budgets & Forecast** · **Optimization** · **Governance**")
