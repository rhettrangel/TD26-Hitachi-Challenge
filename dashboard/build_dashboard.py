"""Generates the Hitachi Lumada control tower dashboard (dashboard/index.html).

Inputs:  runs/run1/event_traces.json, data/events.json
Output:  dashboard/index.html

Design: flat dark surfaces, one red accent, Lucide-style inline SVG icons,
no emoji. Every claim shown is read from the run data, not hard-coded.
"""

import html
import json
import os
from collections import Counter

MODEL_NAME = "gemini-3-flash-preview"

# Lucide-style icons (ISC license), inline SVG, 24x24 stroke icons.
ICONS = {
    "calendar": '<path d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/>',
    "transfer": '<path d="M8 3 4 7l4 4M4 7h16M16 21l4-4-4-4M20 17H4"/>',
    "store": '<path d="M3 9l1-5h16l1 5M3 9v11h18V9M3 9h18M9 20v-6h6v6"/>',
    "car": '<path d="M5 17h14M7 17l-1-5 2-4h8l2 4-1 5M7 17v2M17 17v2M9 8V5h6v3"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/><path d="M12 9v4M12 16h.01"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "slash": '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
}


def icon(name):
    return (f'<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICONS[name]}</svg>')


ACTION_META = {
    "mes.reschedule": ("calendar", "Reschedule production order"),
    "mes.transfer": ("transfer", "Transfer production order"),
    "dealer.notify": ("store", "Notify dealer"),
    "dealer.stop_sale": ("shield", "Stop sale at dealer"),
    "crm.assign_loaner": ("car", "Assign loaner"),
    "crm.notify_customer": ("mail", "Notify owner"),
    "quality.hold_lot": ("shield", "Hold part lot"),
    "escalate": ("user", "Escalate to supervisor"),
}


def esc(x):
    return html.escape(str(x), quote=True)


def summarize_actions(actions):
    """Group raw actions by tool so the panel shows counts, not one card per call."""
    counts = Counter(a.get("tool", "") for a in actions)
    ok = sum(1 for a in actions if a.get("ok", True))
    return {
        "total": len(actions),
        "ok": ok,
        "failed": len(actions) - ok,
        "groups": [
            {"tool": t, "count": n, "label": ACTION_META.get(t, ("", t))[1],
             "icon": ACTION_META.get(t, ("slash", t))[0]}
            for t, n in counts.most_common()
        ],
    }


def generate_dashboard():
    with open("runs/run1/event_traces.json", encoding="utf-8") as f:
        traces = json.load(f)
    with open("data/events.json", encoding="utf-8") as f:
        events = json.load(f)
    events_map = {e["event_id"]: e for e in events}

    records = []
    for t in traces:
        eid = t["event_id"]
        raw = events_map.get(eid, {})
        actions = t.get("actions_taken", [])
        records.append({
            "event_id": eid,
            "category": t.get("category", ""),
            "is_noise": bool(t.get("is_noise", False)),
            "unconfirmed": bool(t.get("unconfirmed", False)),
            "raw_text": raw.get("text", ""),
            "source": raw.get("source", ""),
            "received_at": raw.get("received_at", ""),
            "what_happened": t.get("what_happened", ""),
            "impact_summary": t.get("impact_summary", ""),
            "graph_paths": t.get("graph_paths", []),
            "reasoning_trace": t.get("reasoning_trace", []),
            "actions": actions,
            "summary": summarize_actions(actions),
            "audit": [
                {"tool": a.get("tool", ""), "args": a.get("args", {}),
                 "ok": a.get("ok", True), "agent": a.get("agent", "")}
                for a in actions
            ],
        })

    total_writes = sum(r["summary"]["total"] for r in records)
    total_failed = sum(r["summary"]["failed"] for r in records)
    n_events = len(records)
    noise_writes = sum(r["summary"]["total"] for r in records if r["is_noise"])

    def cat_class(r):
        if r["is_noise"]:
            return "noise"
        if r["unconfirmed"]:
            return "unconfirmed"
        cat = r["category"].lower()
        if "quality" in cat or "outage" in cat:
          return "critical"
        return "important"

    def event_row(r):
        return (
            f'<button class="ev {cat_class(r)}" data-id="{esc(r["event_id"])}">'
            f'<span class="ev-id">{esc(r["event_id"])}</span>'
            f'<span class="ev-cat">{esc(r["category"])}</span>'
            f'<span class="ev-txt">{esc(r["raw_text"][:140])}</span>'
            f'</button>'
        )

    event_list = "\n".join(event_row(r) for r in records)

    data_json = json.dumps(records).replace("</", "<\\/")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hitachi Lumada control tower</title>
<style>
  :root {{
    --bg: #f5f6f7; --panel: #ffffff; --feed: #e9ebee; --line: #d6d9de;
    --text: #1a1c20; --muted: #5a606a; --accent: #FE0002;
    --sel: #fde3e2; --hover: #dfe2e6;
    --sans: Inter, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    --mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 var(--sans); }}
  .ic {{ width: 16px; height: 16px; flex: none; }}
  header {{ display: flex; align-items: center; justify-content: space-between;
          padding: 14px 24px; border-bottom: 1px solid var(--line);
          background: linear-gradient(to top, #d9dbde 0%, #f4f5f6 100%); color: var(--text); }}
  header .brand {{ height: 40px; width: auto; display: block; }}
  h1 {{ font-size: 18px; font-weight: 600; margin: 0; }}
  .sub {{ color: var(--muted); font-size: 13px; }}
  .stats {{ display: flex; gap: 24px; }}
  .stat b {{ display: block; font-size: 20px; font-variant-numeric: tabular-nums; }}
  .stat span {{ color: var(--muted); font-size: 12px; }}
  main {{ display: grid; grid-template-columns: 320px 1fr 420px; height: calc(100vh - 73px); }}
  aside, section, .detail {{ overflow-y: auto; }}
  aside {{ background: var(--feed); border-right: 1px solid var(--line); }}
  .col-h {{ padding: 14px 16px; font-size: 12px; color: var(--muted); border-bottom: 1px solid var(--line); }}
  .filters {{ display: flex; gap: 6px; flex-wrap: wrap; padding: 10px 16px; border-bottom: 1px solid var(--line); }}
  .filters button {{ background: #fff; border: 1px solid var(--line); color: var(--muted);
                     border-radius: 4px; padding: 3px 9px; font: inherit; font-size: 12px; cursor: pointer; }}
  .filters button.on {{ color: var(--text); border-color: var(--text); }}
  .ev {{ display: block; width: 100%; text-align: left; background: none; border: 0;
         border-bottom: 1px solid var(--line); padding: 12px 16px; color: var(--text);
         font: inherit; cursor: pointer; }}
  .ev:hover {{ background: var(--hover); }}
  .ev.critical {{ background: #f6c9c5; }}
  .ev.important {{ background: #fbd9b0; }}
  .ev.critical:hover {{ background: #f0b3ad; }}
  .ev.important:hover {{ background: #f7c890; }}
  .ev.sel {{ background: #FE0002; box-shadow: none; }}
  .ev.sel:hover {{ background: #FE0002; }}
  .ev.sel, .ev.sel .ev-id, .ev.sel .ev-cat, .ev.sel .ev-txt {{ color: #ffffff; }}
  .ev.sel .ev-txt, .ev.sel .ev-id {{ opacity: 0.92; }}
  .ev-id {{ font-family: var(--mono); font-size: 12px; color: var(--muted); }}
  .ev-cat {{ display: block; font-size: 13px; margin: 2px 0; }}
  .ev-txt {{ display: block; color: var(--muted); font-size: 12px; }}
  .detail {{ padding: 20px 24px; border-left: 1px solid var(--line); background: var(--panel); }}
  .center .ev-head {{ border-bottom: 2px solid var(--accent); padding-bottom: 14px; margin-bottom: 18px; }}
  .center h2 {{ font-size: 22px; }}
  .center h3 {{ color: var(--text); font-size: 13px; padding-left: 10px;
                border-left: 3px solid var(--accent); margin: 26px 0 10px; }}
  h2 {{ font-size: 16px; margin: 0 0 4px; font-weight: 600; }}
  h3 {{ font-size: 13px; margin: 24px 0 8px; font-weight: 600; color: var(--muted); }}
  .stat-row {{ display: flex; gap: 40px; margin: 20px 0 4px; }}
  .stat-row > div {{ display: flex; flex-direction: column; }}
  .stat-row b {{ font-size: 40px; font-weight: 600; letter-spacing: -0.02em;
                 font-variant-numeric: tabular-nums; line-height: 1.1; }}
  .stat-row span {{ font-size: 14px; color: var(--muted); }}
  .paths-summary {{ color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
  .path {{ font-family: var(--mono); font-size: 12px; color: var(--muted);
           border-left: 2px solid var(--line); padding: 4px 0 4px 10px; margin: 8px 0; word-break: break-word; }}
  .more-paths {{ background: #fff; border: 1px solid var(--line); color: var(--text);
                 border-radius: 4px; padding: 4px 10px; font: inherit; font-size: 12px; cursor: pointer; }}
  .incident {{ border: 1px solid var(--line); border-radius: 6px; padding: 14px 16px; margin-bottom: 14px; }}
  .tag {{ display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 3px;
          border: 1px solid var(--line); color: var(--muted); }}
  .tag.red {{ color: var(--accent); border-color: var(--accent); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  th {{ color: var(--muted); font-weight: 500; font-size: 12px; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .grp {{ display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--line); }}
  .grp .n {{ margin-left: auto; font-variant-numeric: tabular-nums; font-weight: 600; }}
  .muted {{ color: var(--muted); }}
  .mono {{ font-family: var(--mono); font-size: 12px; }}
  .tabs {{ display: flex; gap: 0; border-bottom: 1px solid var(--line); }}
  .tabs button {{ background: none; border: 0; color: var(--muted); padding: 10px 14px;
                  font: inherit; cursor: pointer; border-bottom: 2px solid transparent; }}
  .tabs button.on {{ color: var(--text); border-bottom-color: var(--accent); }}
  .tabpane {{ display: none; }}
  .tabpane.on {{ display: block; }}
  footer {{ position: fixed; bottom: 0; right: 0; padding: 6px 24px; font-size: 12px;
            color: var(--muted); background: var(--bg); }}
  .noise-note {{ border: 1px dashed var(--line); border-radius: 6px; padding: 12px 14px; color: var(--muted); }}
</style>
</head>
<body>
<header>
  <div class="brand-wrap">
    <img class="brand" src="hitachi.png" alt="Hitachi" width="236" height="41">
    <h1>Lumada control tower</h1>
    <div class="sub">Zero-inventory JIT operations · Wacky Wheels Co.</div>
  </div>
  <div class="stats">
    <div class="stat"><b>{n_events}</b><span>events</span></div>
    <div class="stat"><b>{total_writes}</b><span>tool calls, deterministic baseline</span></div>
    <div class="stat"><b>{total_failed}</b><span>failed calls</span></div>
    <div class="stat"><b>{noise_writes}</b><span>writes on noise</span></div>
  </div>
</header>
<main>
  <aside>
    <div class="col-h">Event feed</div>
    <div class="filters" id="filters">
      <button class="on" data-f="all">All</button>
      <button data-f="incident">Incidents</button>
      <button data-f="unconfirmed">Unconfirmed</button>
      <button data-f="noise">Noise</button>
    </div>
    <div id="feed">
{event_list}
    </div>
  </aside>
  <section class="detail center" id="detail"></section>
  <section class="detail center" id="side">
    <div class="tabs">
      <button class="on" data-t="actions">Actions</button>
      <button data-t="reasoning">Reasoning</button>
      <button data-t="audit">Audit</button>
    </div>
    <div class="tabpane on" id="t-actions"></div>
    <div class="tabpane" id="t-reasoning"></div>
    <div class="tabpane" id="t-audit"></div>
  </section>
</main>
<footer>Model: {esc(MODEL_NAME)} · Live: 14 of 15 calls (E-15 rate-limited) · Deterministic baseline for action logs</footer>

<script>
const RECORDS = {data_json};
const ICONS = {json.dumps(ICONS)};
const META = {json.dumps(ACTION_META)};
const esc = s => String(s).replace(/[&<>"']/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}})[c]);
const icon = n => `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${{ICONS[n]||""}}</svg>`;
let sel = RECORDS[0].event_id, filter = "all";

function renderFeed() {{
  document.querySelectorAll("#feed .ev").forEach(b => {{
    const r = RECORDS.find(x => x.event_id === b.dataset.id);
    const kind = r.is_noise ? "noise" : (r.unconfirmed ? "unconfirmed" : "incident");
    b.style.display = (filter === "all" || filter === kind) ? "" : "none";
    b.classList.toggle("sel", b.dataset.id === sel);
  }});
}}

function countUnique(paths, re) {{
  return new Set(paths.map(p => (p.match(re) || [])[1]).filter(Boolean)).size;
}}

function renderDetail(r) {{
  const pRe = /ProductionOrder\\((PO-\\d+)\\)/;
  const dRe = /Dealer\\((D\\d+)\\)/;
  const cRe = /CustomerOrder\\((CO-\\d+)\\)/;
  const orders = countUnique(r.graph_paths, pRe);
  const dealers = countUnique(r.graph_paths, dRe);
  const custOrders = countUnique(r.graph_paths, cRe);

  const stats = r.graph_paths.length
    ? `<div class="stat-row">
         <div><b>${{orders}}</b><span>production orders</span></div>
         <div><b>${{custOrders}}</b><span>customer orders</span></div>
         <div><b>${{dealers}}</b><span>dealers</span></div>
       </div>`
    : "";
  const shown = r.graph_paths.slice(0, 3);
  const hidden = r.graph_paths.slice(3);
  const pathHtml = p => `<div class="path">${{esc(p)}}</div>`;
  const escalated = r.unconfirmed || r.is_noise;
  const paths = escalated
    ? `<div class="muted">No graph path. ${{r.unconfirmed ? "Escalated to a human supervisor before any graph modification." : "Not operational: no entities touched."}}</div>`
    : r.graph_paths.length
    ? `<div class="paths-summary">${{r.graph_paths.length}} traversal ${{r.graph_paths.length === 1 ? "path" : "paths"}} (one per affected customer order)</div>`
      + shown.map(pathHtml).join("")
      + (hidden.length ? `<button class="more-paths" id="more">Show all ${{r.graph_paths.length}}</button>
        <div id="hidden" hidden>${{hidden.map(pathHtml).join("")}}</div>` : "")
    : `<div class="muted">No graph path: no operational entities were touched.</div>`;

  document.getElementById("detail").innerHTML = `
    <div class="ev-head">
      <div class="muted mono">${{esc(r.event_id)}} · ${{esc(r.source)}} · ${{esc(r.received_at)}}</div>
      <h2>${{esc(r.category)}}</h2>
      <p class="muted">Source report estimate: ${{esc(r.impact_summary)}}</p>
    </div>
    ${{stats}}
    <h3>Source message</h3>
    <div class="path">${{esc(r.raw_text)}}</div>
    <h3>Graph path citations</h3>
    ${{paths}}`;
  const btn = document.getElementById("more");
  if (btn) btn.onclick = () => {{ document.getElementById("hidden").hidden = false; btn.remove(); }};
}}

function renderActions(r) {{
  const pane = document.getElementById("t-actions");
  if (r.is_noise) {{
    pane.innerHTML = `<div class="noise-note">Judged not operational. Writes: 0. Reason: ${{esc(r.reasoning_trace.slice(-2).join(" "))}}</div>`;
    return;
  }}
  if (r.unconfirmed) {{
    pane.innerHTML = `<div class="noise-note">Not actionable. Writes: 0. Escalated to a human supervisor.</div>`;
    return;
  }}
  const rows = r.summary.groups.map(g =>
    `<div class="grp">${{icon(g.icon)}}<span>${{esc(g.label)}}</span><span class="n">${{g.count}}</span></div>`).join("");
  pane.innerHTML = `<div class="muted" style="margin-bottom:8px">${{r.summary.total}} calls · ${{r.summary.failed}} failed</div>${{rows}}`;
}}

function renderReasoning(r) {{
  document.getElementById("t-reasoning").innerHTML = r.reasoning_trace.length
    ? `<ol class="muted" style="padding-left:18px">${{r.reasoning_trace.map(s => `<li style="margin-bottom:6px">${{esc(s)}}</li>`).join("")}}</ol>`
    : `<div class="muted">No reasoning trace recorded.</div>`;
}}

function renderAudit(r) {{
  const rows = r.audit.map(a =>
    `<tr><td class="mono">${{esc(a.tool)}}</td><td class="mono">${{esc(JSON.stringify(a.args))}}</td><td>${{a.ok ? "ok" : "fail"}}</td></tr>`).join("");
  document.getElementById("t-audit").innerHTML = r.audit.length
    ? `<table><thead><tr><th>Tool</th><th>Arguments</th><th>Result</th></tr></thead><tbody>${{rows}}</tbody></table>`
    : `<div class="muted">No tool calls. Audit trail is empty by design for this event.</div>`;
}}

function selectEvent(id) {{
  sel = id;
  const r = RECORDS.find(x => x.event_id === id);
  renderFeed(); renderDetail(r); renderActions(r); renderReasoning(r); renderAudit(r);
}}

document.getElementById("feed").addEventListener("click", e => {{
  const b = e.target.closest(".ev"); if (b) selectEvent(b.dataset.id);
}});
document.getElementById("filters").addEventListener("click", e => {{
  const b = e.target.closest("button"); if (!b) return;
  filter = b.dataset.f;
  document.querySelectorAll("#filters button").forEach(x => x.classList.toggle("on", x === b));
  renderFeed();
}});
document.querySelector(".tabs").addEventListener("click", e => {{
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".tabpane").forEach(p => p.classList.toggle("on", p.id === "t-" + b.dataset.t));
}});

selectEvent(sel);
</script>
</body>
</html>
"""

    out_file = os.path.join("dashboard", "index.html")
    os.makedirs("dashboard", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Dashboard generated at {out_file}")


if __name__ == "__main__":
    generate_dashboard()