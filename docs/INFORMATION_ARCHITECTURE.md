# Information Architecture — Multi-Cloud FinOps + Governance

Single source of truth for app structure: section names, order, and what each shows. Use this to rename/restructure pages and navigation.

---

## 0. Product flow (how users move through the app)

### Entry
- User lands on **Overview** (default home) or **Setup** (first-time: connect clouds).
- Sidebar shows all 8 pages in order; user can go to any page at any time.

### Typical flow (first time)
1. **Setup** → Connect at least one cloud (AWS / GCP / Azure), set auth, optionally run first sync.
2. **Overview** → See KPIs (spend, budget %, optimization potential, violations). Click a KPI or alert to jump to the right page.
3. **Spend** / **Budgets** / **Optimization** / **Governance** / **Chargeback** → Used as needed; no required sequence.

### Cross-links (flow between pages)
- **Overview** → Links/cards to: Spend, Budgets & Forecast, Optimization, Governance.
- **Spend** → “Add to budget” (later) → Budgets & Forecast. Export for Chargeback/Finance.
- **Budgets & Forecast** → “View spend for this budget” → Spend (filtered to scope).
- **Optimization** → “View in Spend” (cost context) → Spend. Export recommendations.
- **Governance** → Violations link to resource/account; “View in Spend” → Spend.
- **Chargeback** → Uses same data as Spend (by team/product); Export reports.
- **Setup** → “Sync now” refreshes data used on Overview, Spend, Optimization, etc.

### Summary
- **8 pages** (or 7 if Settings is merged into Setup).
- **No strict wizard;** user chooses where to go. Setup first, then Overview as home; everything else is task-based (see spend, manage budgets, act on recommendations, fix governance, run chargeback).

---

## 0b. Exact page list and what’s on each (one-page reference)

| # | Page name (sidebar + route) | What is displayed on this page |
|---|-----------------------------|---------------------------------|
| **1** | **Setup** | Cloud connections (AWS, GCP, Azure): add/remove, auth (env/keys/role), default regions, account/project IDs, status (connected/error/last sync). Optional: org defaults (currency, fiscal year, cost allocation tags). Button: “Sync now” / “Run scans”; last run time. |
| **2** | **Overview** | KPI strip: total spend (MTD, last month, YoY%), budget consumption %, optimization potential $, open violations count. Chart: spend by cloud (pie/bar). Chart: spend trend (line, 3–12 months). Alerts: top 3–5 (budget overrun, violation, top cost driver, top recommendation). Links to Spend, Budgets, Optimization, Governance. |
| **3** | **Spend** | Filters: time range, cloud(s), account(s), group-by (account / project / team tag / service). Summary row: total spend + vs prior period. Main table: rows = chosen grouping, columns = spend, % of total, trend; export CSV. Optional: top N services/accounts. |
| **4** | **Budgets & Forecast** | Budget list table: name, scope (e.g. account/team), amount, period (monthly/quarterly), consumed %, status (on track / at risk / over). Drill-down: current vs budget, forecast to period end, variance, history chart. Alerts: budgets at risk or over; link to Spend filtered to scope. Actions: Create budget, Edit, Set alert threshold. |
| **5** | **Optimization** | Scope selector: cloud, region, account. Summary KPIs: total potential savings, count “action” vs “OK”, by resource type. Sub-tabs/cards: **Compute** (EC2/GCE: idle, rightsizing, reserved vs on-demand), **Containers** (Fargate/GKE: over-provisioned, idle), **Serverless** (Lambda/Cloud Functions: low utilization), **Commitment** (Savings Plans/CUDs: coverage, alignment, expiry). Per row: resource id, current config, recommendation, estimated savings, Apply/Dismiss. Actions: Run scan, Export. |
| **6** | **Governance** | Policies list: name, type, severity, status (active/disabled), violation count. Violations table: policy, resource, account, date, status (open/approved/rejected); filters. Approvals (later): pending requests; Approve/Reject. Optional: audit log. Actions: Create policy, Acknowledge violation. |
| **7** | **Chargeback** | Allocation model: by tag (team/product), by account, or fixed %. Summary: by team or product (total cost, % of total). Detail table: rows = team or product, columns = cost, trend, optional vs budget. Export: CSV/PDF. Actions: Set allocation tags, Change period, Export report. |
| **8** | **Settings** | App preferences: currency, date format, default time range. Notifications: email/Slack for budget alerts, violations (when added). Users & access (when RBAC added): roles, invite. *(Optional: can be merged into Setup.)* |

**Total: 8 pages** (or 7 if Settings is merged into Setup).

---

## 1. Section list (navigation order)

| # | Section ID (URL/slug) | Label in UI | Purpose |
|---|------------------------|-------------|---------|
| 0 | `setup` | **Setup** | Connect clouds, auth, org defaults |
| 1 | `overview` | **Overview** | Cross-cloud KPIs and health at a glance |
| 2 | `spend` | **Spend** | Where money goes (by cloud, account, team, time) |
| 3 | `budgets` | **Budgets & Forecast** | Budgets, forecasts, variance |
| 4 | `optimization` | **Optimization** | Waste, rightsizing, recommendations (current scanners live here) |
| 5 | `governance` | **Governance** | Policies, violations, approvals |
| 6 | `chargeback` | **Chargeback** | Showback/chargeback by team or product |
| 7 | `settings` | **Settings** | App-wide preferences (optional; can merge into Setup) |

---

## 2. What each section shows

### 0 — Setup  
**Slug:** `setup` · **Label:** Setup  

- **Cloud connections**  
  - Add/remove clouds: AWS, GCP, Azure.  
  - Per cloud: auth (env, keys, or cross-account role), default region(s), account/project IDs.  
  - Status: connected / error / last sync time.  
- **Organization defaults** (optional for v1)  
  - Default currency, fiscal year start, cost allocation tags to use for “team” or “product.”  
- **Data sync**  
  - Trigger “sync spend” / “run scans” and see last run time.  

**Primary actions:** Connect cloud, Edit credentials, Sync now.

---

### 1 — Overview  
**Slug:** `overview` · **Label:** Overview  

- **KPI strip**  
  - Total cloud spend (MTD, last month, YoY%).  
  - Budget consumption % (e.g. “78% of monthly budget”).  
  - Optimization potential (e.g. “$X identified savings”).  
  - Open governance violations count.  
- **Spend by cloud**  
  - Pie or bar: AWS vs GCP vs Azure (and “Other” if needed).  
- **Spend trend**  
  - Line chart: daily or monthly spend over last 3–12 months.  
- **Alerts / highlights**  
  - Top 3–5 items: budget overrun, new violation, top cost driver, or top recommendation.  

**Primary actions:** Drill into Spend, Budgets, Optimization, or Governance from cards/links.

---

### 2 — Spend  
**Slug:** `spend` · **Label:** Spend  

- **Filters**  
  - Time range, cloud(s), account(s), group-by (account, project, team tag, service).  
- **Summary row**  
  - Total spend for selection; comparison to prior period.  
- **Main table**  
  - Rows = chosen grouping (e.g. by account, by service); columns = spend, % of total, trend.  
  - Export CSV.  
- **Optional secondary view**  
  - Top N services or top N accounts as small tables or charts.  

**Primary actions:** Change filters, Export, “Add to budget” or “Pin to Overview” (later).

---

### 3 — Budgets & Forecast  
**Slug:** `budgets` · **Label:** Budgets & Forecast  

- **Budget list**  
  - Name, scope (e.g. “AWS account 123”, “Team Backend”), amount, period (monthly/quarterly), consumed %, status (on track / at risk / over).  
- **Per-budget detail** (drill-down or side panel)  
  - Current spend vs budget; forecast to period end; variance; history chart.  
- **Forecast**  
  - Simple forecast (e.g. “At current run rate, period end = $X”). Optional: trend-based or model-based later.  
- **Alerts**  
  - List of budgets at risk or over; link to Spend filtered to that scope.  

**Primary actions:** Create budget, Edit budget, Set alert threshold.

---

### 4 — Optimization  
**Slug:** `optimization` · **Label:** Optimization  

- **Scope selector**  
  - Cloud (AWS / GCP / Azure), region, account.  
- **Summary KPIs**  
  - Total potential savings; count of “action” vs “OK” (or similar); by resource type.  
- **Recommendations by type** (sub-tabs or sub-pages if needed)  
  - **Compute (e.g. EC2 / GCE / VMs):** idle, rightsizing, reserved vs on-demand.  
  - **Containers (e.g. Fargate / GKE / AKS):** over-provisioned, idle.  
  - **Serverless (e.g. Lambda / Cloud Functions):** low utilization, right-sizing.  
  - **Commitment (e.g. Savings Plans / CUDs / RIs):** coverage, alignment, expiry.  
- **Per-recommendation**  
  - Resource id, current config, recommendation, estimated savings, “Apply” or “Dismiss” (or link to runbook).  

**Primary actions:** Run scan / refresh, Filter by cloud/account, Export list, “Apply” or “Create ticket” (later).

*This is where current EC2, Lambda, Fargate, Savings Plans, EC2 vs SP alignment content lives—as tabs or cards under Optimization.*

---

### 5 — Governance  
**Slug:** `governance` · **Label:** Governance  

- **Policies list**  
  - Name, type (e.g. “No GPUs without approval”, “Budget cap per project”), severity, status (active/disabled), violation count.  
- **Violations**  
  - Table: policy, resource, account, date, status (open / approved / rejected).  
  - Filters: policy, cloud, account, date.  
- **Approvals** (when you add workflows)  
  - Pending requests; Approve / Reject with comment.  
- **Audit log** (optional for v1)  
  - Who changed what policy or approved what, when.  

**Primary actions:** Create policy, Acknowledge violation, Approve / Reject request.

---

### 6 — Chargeback  
**Slug:** `chargeback` · **Label:** Chargeback  

- **Allocation model**  
  - How cost is split: by tag (e.g. “team”, “product”), by account, or by fixed %.  
- **Summary by dimension**  
  - e.g. By team: total cost, % of total; by product: same.  
- **Detail table**  
  - Rows = team or product; columns = cost, trend, optional comparison to budget.  
- **Export**  
  - CSV/PDF for finance or per-team reports.  

**Primary actions:** Set allocation tags, Change period, Export report.

---

### 7 — Settings (optional)  
**Slug:** `settings` · **Label:** Settings  

- **App preferences**  
  - Currency, date format, default time range.  
- **Notifications**  
  - Email/Slack for budget alerts, governance violations (when you add them).  
- **Users & access** (when you add RBAC)  
  - Roles, invite.  

If you keep the app minimal, this can be folded into **Setup** (e.g. “Setup & settings”).

---

## 3. URL / file naming (Streamlit)

Streamlit uses file names in `pages/` for routes. Suggested mapping:

| Section | Suggested file name | Streamlit route |
|---------|---------------------|------------------|
| Setup | `0_Setup.py` | Setup |
| Overview | `1_Overview.py` | Overview |
| Spend | `2_Spend.py` | Spend |
| Budgets & Forecast | `3_Budgets_Forecast.py` | Budgets & Forecast |
| Optimization | `4_Optimization.py` | Optimization |
| Governance | `5_Governance.py` | Governance |
| Chargeback | `6_Chargeback.py` | Chargeback |
| Settings | `7_Settings.py` (or merged into 0) | Settings |

So: **one page per section**, ordered by number prefix. Current EC2, Lambda, Fargate, Savings Plans, EC2 vs SP become **sub-views or tabs inside `4_Optimization.py`**, not top-level pages.

---

## 4. Sidebar / nav copy

Use short labels in the sidebar so the IA is obvious:

- **Setup**
- **Overview**
- **Spend**
- **Budgets & Forecast**
- **Optimization**
- **Governance**
- **Chargeback**
- **Settings** (optional)

No “AWS Setup” or “EC2” at the top level—those are under Setup and Optimization respectively.

---

## 5. What to build first (IA priority)

1. **Rename and reorder**  
   Implement the 8 sections above; move current AWS/EC2/Lambda/Fargate/SP content under **Optimization** (tabs or sub-pages).  

2. **Overview**  
   One page with KPIs and links to Spend, Budgets, Optimization, Governance. Start with data you already have (e.g. optimization potential, scan time).  

3. **Spend**  
   One view (e.g. AWS only at first) with table + filters + export.  

4. **Budgets & Forecast**  
   Simple budgets (name, scope, amount, period) and consumed %; link scope to Spend.  

5. **Governance**  
   Start with a list of “policies” and “violations” (can be static or from a simple rules engine).  

6. **Chargeback**  
   After allocation tags and Spend are stable; one table by team/product and export.  

7. **Setup**  
   Evolve current AWS Setup into “Setup” with placeholders for GCP/Azure and org defaults.  

This IA is the structure for a multi-cloud FinOps + governance product; you can ship sections incrementally (e.g. Overview + Optimization first, then Spend, then Budgets, then Governance, then Chargeback).
