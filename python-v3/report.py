"""report.py -- builds report.html from the hunter's logs (no dependencies)."""
import json, math, os, html, time

HERE = os.path.dirname(os.path.abspath(__file__))

def _load():
    B = []
    for fn in ('batches.jsonl', 'jobs.jsonl'):
        fp = os.path.join(HERE, fn)
        if os.path.exists(fp):
            B += [r for r in (json.loads(l) for l in open(fp)) if r.get('kind', 'job') == 'job']
    st = json.load(open(os.path.join(HERE, 'hunt_state.json'))) if os.path.exists(os.path.join(HERE, 'hunt_state.json')) else {'arms': {}}
    found = [l.rstrip('\n').split('\t') for l in open(os.path.join(HERE, 'FOUND.tsv'))] if os.path.exists(os.path.join(HERE, 'FOUND.tsv')) else []
    best = []
    gp = os.path.join(HERE, 'gaps.tsv')
    if os.path.exists(gp):
        for l in open(gp):
            f = l.split('\t')
            if len(f) > 9 and f[5] == '1':
                best.append((float(f[9]), int(f[8]), f[0], f[1], f[6]))
    best.sort(reverse=True)
    return B, st, found, best[:12]

def _svg_rates(B):
    if not B: return '<p class="muted">no batches yet</p>'
    W, H, pad = 720, 220, 40
    arms = sorted(set(b['arm'] for b in B))
    xs = [b['t'] for b in B]; t0, t1 = min(xs), max(xs) + 1
    ys = [math.log10(max(b['rate'] * 3600, 1e-12)) for b in B]
    y0, y1 = min(ys) - 0.5, max(ys) + 0.5
    X = lambda t: pad + (W - 2 * pad) * (t - t0) / (t1 - t0)
    Y = lambda y: H - pad + (2 * pad - H) * (y - y0) / (y1 - y0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="rate per batch">']
    for k in range(math.ceil(y0), math.floor(y1) + 1):
        out.append(f'<line x1="{pad}" x2="{W-pad}" y1="{Y(k):.1f}" y2="{Y(k):.1f}" class="grid"/><text x="{pad-6}" y="{Y(k)+4:.1f}" class="tick" text-anchor="end">1e{k}</text>')
    for i, a in enumerate(arms):
        pts = [(X(b['t']), Y(math.log10(max(b['rate'] * 3600, 1e-12)))) for b in B if b['arm'] == a]
        for x, y in pts:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="s{i % 6}"><title>{html.escape(a)}</title></circle>')
    out.append('</svg>')
    legend = ''.join(f'<span class="lg"><i class="s{i % 6}"></i>{html.escape(a)}</span>' for i, a in enumerate(arms))
    return ''.join(out) + f'<div class="legend">{legend}</div>'

def build():
    B, st, found, best = _load()
    rows = []
    for k, s in sorted(st['arms'].items(), key=lambda kv: -(kv[1]['value'] / kv[1]['secs'] if kv[1]['secs'] else 0)):
        rate = s['value'] / s['secs'] * 3600 if s.get('secs') else 0
        cal = f"{s['pcal']:.1f} / {s['calhits']}" if s['completed'] else '—'
        rows.append(f"<tr><td>{html.escape(k)}</td><td>{len(s['logs'])}</td><td>{s['secs']/3600:.2f}</td><td>{s['tested']}</td>"
                    f"<td>{rate:.2e}</td><td>{cal}</td><td>{s['hits']}</td></tr>")
    total_h = sum(s['secs'] for s in st['arms'].values()) / 3600
    exp_impr = sum(s['value'] for s in st['arms'].values())
    nfound = len(found)
    frows = ''.join(f"<tr><td>{html.escape(f[0])}</td><td>{html.escape(f[1])}</td><td class='mono'>{html.escape(f[2])}</td><td>{html.escape(f[3].split('=')[-1])}</td><td>{html.escape(f[4])}</td></tr>" for f in found) or '<tr><td colspan="5" class="muted">none yet</td></tr>'
    brows = ''.join(f"<tr><td>{m:.3f}</td><td>{g}</td><td>{html.escape(a)}</td><td class='mono'>m={html.escape(mm)}, a={html.escape(aa)}</td></tr>" for m, g, a, mm, aa in best) or '<tr><td colspan="4" class="muted">none yet</td></tr>'
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gap Hunter</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#77736b;--line:#e3e0d8;--acc:#b5532a;--c0:#b5532a;--c1:#2f6f8f;--c2:#6c8f3a;--c3:#8a5aa8;--c4:#c29a1e;--c5:#4b4b4b}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161513;--fg:#ece9e2;--mut:#9a958b;--line:#2c2a26;--acc:#e07a4f;--c0:#e07a4f;--c1:#6fb2d4;--c2:#9cc463;--c3:#c095dd;--c4:#e2c04d;--c5:#bbb}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:820px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:15px;text-transform:lowercase;letter-spacing:.04em;color:var(--mut);margin:28px 0 8px}}
.muted{{color:var(--mut)}} .mono{{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;word-break:break-all}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}}
.kpi{{border:1px solid var(--line);border-radius:10px;padding:10px 12px}} .kpi b{{display:block;font-size:22px}} .kpi span{{color:var(--mut);font-size:12.5px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}} th{{color:var(--mut);font-weight:500}}
.tw{{overflow-x:auto}} svg{{width:100%;height:auto}} .grid{{stroke:var(--line)}} .tick{{fill:var(--mut);font-size:11px}}
.s0{{fill:var(--c0);background:var(--c0)}}.s1{{fill:var(--c1);background:var(--c1)}}.s2{{fill:var(--c2);background:var(--c2)}}.s3{{fill:var(--c3);background:var(--c3)}}.s4{{fill:var(--c4);background:var(--c4)}}.s5{{fill:var(--c5);background:var(--c5)}}
.legend{{display:flex;flex-wrap:wrap;gap:10px;font-size:12px;color:var(--mut)}} .lg i{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}}
</style></head><body><main>
<h1>gap hunter</h1><div class="muted">rb labs · updated {time.strftime('%Y-%m-%d %H:%M')}</div>
<div class="kpis"><div class="kpi"><b>{nfound}</b><span>record-table improvements</span></div>
<div class="kpi"><b>{exp_impr:.2e}</b><span>expected improvements so far (model)</span></div>
<div class="kpi"><b>{total_h:.1f}</b><span>core-hours hunted</span></div>
<div class="kpi"><b>{len(B)}</b><span>batches</span></div></div>
<h2>found</h2><div class="tw"><table><tr><th>gap</th><th>merit</th><th>start prime</th><th>old record</th><th>when</th></tr>{frows}</table></div>
<h2>learning: rate per batch (expected improvements per core-hour)</h2>{_svg_rates(B)}
<h2>arms</h2><div class="tw"><table><tr><th>arm</th><th>batches</th><th>core-h</th><th>tested</th><th>rate / core-h</th><th>calibration pred / seen</th><th>hits</th></tr>{''.join(rows)}</table></div>
<h2>best merits seen</h2><div class="tw"><table><tr><th>merit</th><th>gap</th><th>arm</th><th>where</th></tr>{brows}</table></div>
<p class="muted">calibration compares the model's predicted count of gaps above a frequent merit threshold with how many actually showed up. close numbers mean the law is steering honestly.</p>
</main></body></html>"""
    open(os.path.join(HERE, 'report.html'), 'w').write(page)

if __name__ == '__main__':
    build()
