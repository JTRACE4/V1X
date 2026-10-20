"""Welcome page, account pages, admin and the How-to-use guide for BRAIN (added 2026-10-20).
Plain HTML/CSS/JS strings - no build step. The island-town art is an original inline SVG (bold-outline cartoon look,
sunset 'vice city' palette) drawn for this page."""
import html as _html
import time

E = _html.escape

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Bungee&family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">')


def brain_logo(size=44, p="l"):
    w, h = size, int(size * 56 / 64)
    return (f'<svg viewBox="0 0 64 56" width="{w}" height="{h}" aria-hidden="true"><defs>'
            f'<linearGradient id="{p}1" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f7c3d3"/><stop offset="1" stop-color="#e595b0"/></linearGradient>'
            f'<linearGradient id="{p}2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f3e0c8"/><stop offset="1" stop-color="#d2ae86"/></linearGradient></defs>'
            f'<path d="M31 6 C25 2 17 4 15 10 C9 10 5 15 7 21 C2 24 2 32 7 35 C5 41 10 47 16 46 C18 51 26 53 31 49 Z" fill="url(#{p}1)" stroke="#2a1630" stroke-width="2.6" stroke-linejoin="round"/>'
            f'<path d="M33 6 C39 2 47 4 49 10 C55 10 59 15 57 21 C62 24 62 32 57 35 C59 41 54 47 48 46 C46 51 38 53 33 49 Z" fill="url(#{p}2)" stroke="#2a1630" stroke-width="2.6" stroke-linejoin="round"/>'
            '<path d="M15 16 C19 15 21 18 24 17 M10 27 C15 25 17 29 22 27 M14 38 C18 36 21 40 25 38 M24 9 C24 13 27 14 27 18" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" opacity="0.9"/>'
            '<path d="M49 16 C45 15 43 18 40 17 M54 27 C49 25 47 29 42 27 M50 38 C46 36 43 40 39 38 M40 9 C40 13 37 14 37 18" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" opacity="0.9"/>'
            '<path d="M58 2 L59.4 5.6 L63 7 L59.4 8.4 L58 12 L56.6 8.4 L53 7 L56.6 5.6 Z" fill="#ffd36e"/></svg>')


# ------------------------------------------------------------------------------------------------ the island town
def _house(x, y, w, h, wall, roof, lit=(1, 1), sign=None):
    ink = 'stroke="#2a1630" stroke-width="3" stroke-linejoin="round"'
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{wall}" {ink}/>'
         f'<path d="M{x - 8} {y + 2} L{x + w / 2} {y - h * 0.55} L{x + w + 8} {y + 2} Z" fill="{roof}" {ink}/>'
         f'<rect x="{x + w / 2 - 7}" y="{y + h - 22}" width="14" height="22" rx="2" fill="#7a4a3a" {ink}/>')
    cols = 2 if w > 60 else 1
    for c in range(cols):
        wx = x + (w / (cols + 1)) * (c + 1) - 8
        on = lit[c % len(lit)]
        s += (f'<rect class="{"win" if on else ""}" x="{wx}" y="{y + 12}" width="16" height="14" rx="2" '
              f'fill="{"#ffe66d" if on else "#5b4a6b"}" {ink}/>')
    if sign:
        s += sign
    return s


def _palm(x, y, s=1.0, flip=False):
    k = -1 if flip else 1
    ink = 'stroke="#2a1630" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"'
    tx = f'translate({x} {y}) scale({k * s} {s})'
    return (f'<g transform="{tx}" class="palm">'
            '<path d="M0 0 C6 -40 4 -80 18 -120" fill="none" stroke="#2a1630" stroke-width="13" stroke-linecap="round"/>'
            '<path d="M0 0 C6 -40 4 -80 18 -120" fill="none" stroke="#a8693f" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M18 -120 C-10 -130 -40 -120 -60 -95 C-35 -112 -10 -115 18 -118 Z" fill="#3fbf6a" {ink}/>'
            f'<path d="M18 -120 C40 -140 75 -138 95 -115 C70 -128 45 -125 20 -118 Z" fill="#2ea35a" {ink}/>'
            f'<path d="M18 -120 C10 -150 30 -170 55 -172 C35 -160 25 -140 20 -121 Z" fill="#46c975" {ink}/>'
            f'<path d="M18 -120 C45 -110 70 -90 78 -62 C60 -88 40 -105 18 -117 Z" fill="#35b062" {ink}/>'
            f'<path d="M18 -120 C-5 -105 -25 -80 -28 -55 C-15 -82 0 -102 17 -117 Z" fill="#2ea35a" {ink}/>'
            '<circle cx="14" cy="-114" r="6" fill="#7a4a2a" stroke="#2a1630" stroke-width="2.5"/>'
            '<circle cx="24" cy="-112" r="6" fill="#8a5632" stroke="#2a1630" stroke-width="2.5"/></g>')


def island_scene():
    ink = 'stroke="#2a1630" stroke-width="3" stroke-linejoin="round"'
    stars = "".join(f'<circle class="tw" style="animation-delay:{(i * 0.37) % 3:.2f}s" cx="{(i * 97) % 1200}" '
                    f'cy="{18 + (i * 53) % 190}" r="{1.2 + (i % 3) * 0.6}" fill="#fff7e8"/>' for i in range(46))
    neon = ('<g class="neon"><rect x="318" y="282" width="150" height="46" rx="8" fill="#2a1630" stroke="#ff8fb8" stroke-width="3"/>'
            '<text x="393" y="316" text-anchor="middle" font-family="Bungee, sans-serif" font-size="26" fill="#ffd1e3">BRAIN</text>'
            '<line x1="350" y1="328" x2="350" y2="350" stroke="#2a1630" stroke-width="4"/>'
            '<line x1="436" y1="328" x2="436" y2="350" stroke="#2a1630" stroke-width="4"/></g>')
    houses = (_house(150, 410, 70, 62, "#ffd6a5", "#e76f51", (1, 0))
              + _house(232, 398, 64, 74, "#a0e7e5", "#2a7f9e", (1, 1))
              + _house(330, 352, 120, 120, "#ffc6d9", "#8e5bd1", (1, 1))
              + _house(470, 405, 66, 67, "#bdb2ff", "#e76f51", (0, 1))
              + _house(548, 416, 58, 56, "#fdffb6", "#2a9d8f", (1,)))
    lighthouse = (f'<g><path d="M672 470 L684 330 L716 330 L728 470 Z" fill="#fbf4ec" {ink}/>'
                  '<path d="M680 420 L720 420 L723 445 L677 445 Z M682 375 L718 375 L720 398 L680 398 Z" fill="#e85a6b"/>'
                  f'<path d="M672 470 L684 330 L716 330 L728 470 Z" fill="none" {ink}/>'
                  f'<rect x="680" y="300" width="40" height="30" rx="4" fill="#ffe66d" {ink}/>'
                  f'<path d="M674 302 L700 278 L726 302 Z" fill="#e85a6b" {ink}/>'
                  '<path class="beam" d="M700 315 L1150 260 L1150 370 Z" fill="#fff3b0" opacity="0.18"/></g>')
    pier = ("".join(f'<rect x="{760 + i * 46}" y="455" width="8" height="48" fill="#6b4630" stroke="#2a1630" stroke-width="2.5"/>'
                    for i in range(6))
            + f'<rect x="740" y="446" width="270" height="14" rx="3" fill="#a8693f" {ink}/>'
            + "".join(f'<g><line x1="{800 + i * 90}" y1="446" x2="{800 + i * 90}" y2="412" stroke="#2a1630" stroke-width="4"/>'
                      f'<circle class="lamp" cx="{800 + i * 90}" cy="408" r="7" fill="#ffe66d" stroke="#2a1630" stroke-width="2.5"/></g>'
                      for i in range(3)))
    boat = ('<g class="boat"><path d="M960 520 L1060 520 L1045 545 L975 545 Z" fill="#fbf4ec" stroke="#2a1630" stroke-width="3" stroke-linejoin="round"/>'
            '<path d="M1010 520 L1010 462 L1048 515 Z" fill="#ff8fb8" stroke="#2a1630" stroke-width="3" stroke-linejoin="round"/>'
            '<path d="M1006 520 L1006 470 L978 515 Z" fill="#3fd0c0" stroke="#2a1630" stroke-width="3" stroke-linejoin="round"/></g>')
    clouds = (f'<path class="cloud c1" d="M90 150 q10 -30 45 -22 q15 -28 50 -12 q30 -8 38 22 q25 4 18 26 l-160 0 q-18 -6 9 -14 z" fill="#f7c6d6" {ink}/>'
              f'<path class="cloud c2" d="M930 120 q12 -26 44 -18 q18 -24 48 -8 q28 -4 32 20 q22 6 14 24 l-150 0 q-16 -6 12 -18 z" fill="#f3d2e6" {ink}/>')
    birds = ('<g class="birds" fill="none" stroke="#2a1630" stroke-width="3" stroke-linecap="round">'
             '<path d="M520 170 q10 -10 20 0 q10 -10 20 0"/><path d="M570 150 q8 -8 16 0 q8 -8 16 0"/>'
             '<path d="M610 185 q7 -7 14 0 q7 -7 14 0"/></g>')
    waves = "".join(f'<path class="wave w{i % 3}" d="M-60 {520 + i * 18} q30 -8 60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 '
                    f't60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0 t60 0" fill="none" '
                    f'stroke="#bff6ef" stroke-width="3" stroke-linecap="round" opacity="{0.55 - i * 0.08:.2f}"/>' for i in range(5))
    return (
        '<svg class="scene" viewBox="0 0 1200 600" preserveAspectRatio="xMidYMax slice" role="img" '
        'aria-label="Cartoon island town at sunset with a BRAIN neon sign">'
        '<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1b1430"/>'
        '<stop offset="0.42" stop-color="#5d3570"/><stop offset="0.7" stop-color="#e46f8e"/><stop offset="1" stop-color="#f9bb8a"/></linearGradient>'
        '<linearGradient id="sun" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe58f"/><stop offset="1" stop-color="#ff7fa0"/></linearGradient>'
        '<linearGradient id="sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#47d3c4"/><stop offset="1" stop-color="#1c5878"/></linearGradient>'
        '<mask id="sunmask"><rect width="1200" height="600" fill="#fff"/>'
        + "".join(f'<rect x="0" y="{352 + i * 13}" width="1200" height="{3 + i * 1.3:.1f}" fill="#000"/>' for i in range(6))
        + '</mask></defs>'
        '<rect width="1200" height="600" fill="url(#sky)"/>' + stars
        + '<circle cx="840" cy="400" r="150" fill="url(#sun)" mask="url(#sunmask)"/>'
        + clouds + birds
        + '<path d="M0 410 L80 380 L170 395 L260 360 L360 392 L470 372 L560 398 L1200 398 L1200 412 L0 412 Z" fill="#4a2c5c"/>'
        '<rect y="405" width="1200" height="195" fill="url(#sea)"/>'
        '<g opacity="0.8"><rect x="770" y="420" width="140" height="5" rx="2.5" fill="#ffd1a0"/>'
        '<rect x="790" y="436" width="100" height="5" rx="2.5" fill="#ffb3c4"/><rect x="805" y="452" width="70" height="4" rx="2" fill="#ffd1a0"/></g>'
        + waves
        + f'<path d="M40 500 C80 452 160 440 260 446 C380 436 520 436 640 444 C700 448 740 462 760 492 C700 520 560 528 400 526 C240 530 110 528 40 500 Z" fill="#f3d9a4" {ink}/>'
        + f'<path d="M110 470 C180 440 300 430 420 432 C520 430 610 436 660 452 C600 470 450 474 300 474 C200 476 140 476 110 470 Z" fill="#7cc95f" {ink}/>'
        + neon + houses + lighthouse + _palm(95, 488, 1.0) + _palm(620, 480, 0.9, True) + _palm(300, 486, 0.75) + pier + boat
        + '</svg>')


# ------------------------------------------------------------------------------------------------ shared style
BASE_CSS = r"""
:root{--bg:#211b1e;--ink:#2a1630;--cream:#fbf4ec;--text:#eee2d7;--mute:#bcaaa1;--tan:#dcbb91;--blush:#e9a5bb;--pink:#ff8fb8;
--teal:#3fd0c0;--gold:#ffd36e;--tile:rgba(48,36,46,.86);--line:rgba(240,214,200,.14);--up:#3fd0c0;--down:#ff6b81}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--text);font:15px/1.45 Nunito,-apple-system,Segoe UI,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--blush)}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px}
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 16px;position:relative;z-index:3}
.brand{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--cream)}
.brand b{font-family:Bungee,sans-serif;font-size:22px;letter-spacing:1px;text-shadow:2px 2px 0 var(--ink)}
.pill{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;background:rgba(27,20,40,.72);
 border:2px solid var(--ink);font-weight:800;font-size:13px;white-space:nowrap}
.btn{display:inline-block;padding:12px 22px;border-radius:14px;font:900 16px Nunito,sans-serif;text-decoration:none;cursor:pointer;
 border:3px solid var(--ink);box-shadow:4px 4px 0 var(--ink);transition:transform .08s,box-shadow .08s}
.btn:active{transform:translate(3px,3px);box-shadow:1px 1px 0 var(--ink)}
.btn.pink{background:var(--pink);color:var(--ink)}.btn.teal{background:var(--teal);color:var(--ink)}.btn.cream{background:var(--cream);color:var(--ink)}
.card{background:var(--tile);border:2px solid var(--ink);border-radius:18px;padding:14px;box-shadow:5px 5px 0 rgba(42,22,48,.8)}
.card h3{margin:0 0 8px;font-family:Bungee,sans-serif;font-weight:400;font-size:15px;letter-spacing:1px;color:var(--tan)}
.mute{color:var(--mute)}.up{color:var(--up)}.down{color:var(--down)}
input,select,textarea{font:inherit;color:var(--cream);background:#1a1418;border:2px solid #4a3a46;border-radius:12px;padding:11px 12px;width:100%}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--pink)}
label{display:block;font-weight:800;font-size:13px;margin:10px 0 4px;color:var(--tan)}
.err{background:rgba(255,107,129,.14);border:2px solid var(--down);color:#ffd2d9;padding:9px 12px;border-radius:12px;margin:8px 0;font-weight:700}
.ok{background:rgba(63,208,192,.12);border:2px solid var(--teal);color:#d5fff9;padding:9px 12px;border-radius:12px;margin:8px 0;font-weight:700}
"""


def page(title, body, extra_css="", extra_head="", scripts=""):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>{E(title)}</title><meta name="theme-color" content="#211b1e">{FONTS}{extra_head}'
            f'<style>{BASE_CSS}{extra_css}</style></head><body>{body}{scripts}</body></html>')


# ------------------------------------------------------------------------------------------------ welcome page
LANDING_CSS = r"""
.hero{position:relative;height:min(76vh,620px);min-height:440px;overflow:hidden;border-bottom:3px solid var(--ink)}
.hero .scene{position:absolute;inset:0;width:100%;height:100%}
.hero .top{position:absolute;left:0;right:0;top:0}
.hero-copy{position:absolute;left:0;right:0;top:15%;text-align:center;z-index:2;padding:0 16px}
.hero-copy h1{margin:0;font-family:Bungee,sans-serif;font-weight:400;font-size:clamp(54px,13vw,128px);line-height:.95;color:var(--cream);
 text-shadow:5px 5px 0 var(--ink),-2px -2px 0 var(--ink),2px -2px 0 var(--ink),-2px 2px 0 var(--ink);letter-spacing:2px}
.hero-copy p{margin:10px 0 18px;font-weight:900;font-size:clamp(15px,3.6vw,20px);color:#fff4e8;text-shadow:2px 2px 0 var(--ink)}
.hero-copy .cta{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
.tw{animation:tw 3s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.25}50%{opacity:1}}
.wave{animation:wv 6s linear infinite}.w1{animation-duration:8s}.w2{animation-duration:10s}@keyframes wv{to{transform:translateX(-120px)}}
.cloud{animation:drift 40s ease-in-out infinite alternate}.c2{animation-duration:55s}@keyframes drift{to{transform:translateX(60px)}}
.boat{animation:bob 4s ease-in-out infinite}@keyframes bob{50%{transform:translateY(5px) rotate(-1deg)}}
.neon text{filter:drop-shadow(0 0 6px #ff8fb8);animation:flick 5s infinite}@keyframes flick{0%,92%,100%{opacity:1}93%{opacity:.4}95%{opacity:1}96%{opacity:.5}}
.win{animation:glow 4s ease-in-out infinite}@keyframes glow{50%{fill:#fff3a8}}
.beam{transform-origin:700px 315px;animation:sweep 7s ease-in-out infinite alternate}@keyframes sweep{to{transform:rotate(-14deg)}}
.birds{animation:fly 20s linear infinite}@keyframes fly{to{transform:translateX(-700px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
.grid{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin:18px auto 24px}
@media (max-width:860px){.grid{grid-template-columns:1fr}}
.chart-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px;justify-content:space-between}
.px{font-family:Bungee,sans-serif;font-size:clamp(28px,6vw,40px);color:var(--cream);text-shadow:3px 3px 0 var(--ink);line-height:1}
.chg{font-weight:900}
.tabs{display:flex;gap:6px;flex-wrap:wrap}
.tab{border:2px solid var(--ink);background:#2c2230;color:var(--text);border-radius:10px;padding:6px 11px;font-weight:900;cursor:pointer}
.tab.on{background:var(--gold);color:var(--ink)}
#chart{height:330px;margin-top:10px;border-radius:12px;overflow:hidden}
.strip{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;font-weight:800;font-size:13px}
.strip span{background:#1a1418;border:2px solid #3e3140;border-radius:10px;padding:5px 9px}
.side{display:flex;flex-direction:column;gap:16px}
.wx{display:flex;align-items:center;gap:12px}.wx .ic{font-size:44px;line-height:1}
.wx .t{font-family:Bungee,sans-serif;font-size:30px;color:var(--cream)}
.gauge{position:relative;height:16px;border-radius:999px;border:2px solid var(--ink);
 background:linear-gradient(90deg,#ff6b81,#ffb36b,#ffe66d,#a8e06b,#3fd0c0);margin:10px 0 6px}
.gauge i{position:absolute;top:-7px;width:6px;height:26px;border-radius:3px;background:var(--cream);border:2px solid var(--ink);transform:translateX(-3px)}
.tip{padding:8px 0;border-bottom:1px dashed var(--line)}.tip:last-child{border-bottom:0}
.tip b{display:block;color:var(--cream);font-weight:900}.tip span{color:var(--mute);font-weight:600;font-size:14px}
.news a{display:block;text-decoration:none;color:var(--text);padding:9px 0;border-bottom:1px dashed var(--line)}
.news a:last-child{border-bottom:0}.news b{display:block;font-weight:800;line-height:1.3}
.news small{color:var(--mute);font-weight:700}
footer{text-align:center;color:var(--mute);font-size:12px;padding:10px 16px 30px}
select.asset{width:auto;padding:7px 10px;font-weight:900}
"""

LANDING_JS = r"""
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<script>
const $=s=>document.querySelector(s);
let asset='BTC',mode='round';try{asset=localStorage.getItem('pubAsset')||'BTC';mode=localStorage.getItem('pubMode')||'round';}catch(e){}
const fmtET=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'});
const fmtETs=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit',second:'2-digit'});
const fmtDay=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',month:'short',day:'numeric'});
const dec=()=>asset==='XRP'?4:2;
const money=v=>v==null?'--':'$'+Number(v).toLocaleString('en-US',{minimumFractionDigits:dec(),maximumFractionDigits:dec()});
function clock(){const n=new Date();$('#clock').textContent=n.toLocaleDateString('en-US',{timeZone:'America/New_York',weekday:'short',month:'short',day:'numeric'})+' · '+fmtETs.format(n);}
setInterval(clock,1000);clock();
let chart,series,avgSeries,lineRef,last=null,secsLeft=null;
function makeChart(){
  const el=$('#chart');el.innerHTML='';
  chart=LightweightCharts.createChart(el,{autoSize:true,layout:{background:{type:'solid',color:'#1a1418'},textColor:'#bcaaa1',fontFamily:'Nunito'},
    grid:{vertLines:{color:'rgba(240,214,200,.06)'},horzLines:{color:'rgba(240,214,200,.06)'}},
    rightPriceScale:{borderColor:'#3e3140'},timeScale:{borderColor:'#3e3140',timeVisible:true,secondsVisible:mode==='round',
      tickMarkFormatter:(t)=>mode==='1d'?fmtDay.format(new Date(t*1000)):fmtET.format(new Date(t*1000))},
    localization:{timeFormatter:(t)=>fmtETs.format(new Date(t*1000)),priceFormatter:p=>money(p)},crosshair:{mode:0}});
  if(mode==='round'){
    series=chart.addAreaSeries({lineColor:'#ff8fb8',topColor:'rgba(255,143,184,.35)',bottomColor:'rgba(255,143,184,0)',lineWidth:3,priceLineVisible:false});
    avgSeries=chart.addLineSeries({color:'#ffd36e',lineWidth:2,lineStyle:2,priceLineVisible:false,lastValueVisible:false});
  }else{
    series=chart.addCandlestickSeries({upColor:'#3fd0c0',downColor:'#ff6b81',borderVisible:false,wickUpColor:'#3fd0c0',wickDownColor:'#ff6b81'});
    avgSeries=null;
  }
  lineRef=null;
}
function rolling(pts){const out=[];let q=[],s=0;for(const p of pts){q.push(p);s+=p.value;while(q.length&&p.time-q[0].time>=60){s-=q.shift().value;}out.push({time:p.time,value:s/q.length});}return out;}
async function load(){
  makeChart();
  if(mode==='round'){
    const j=await (await fetch('/public/ticks?asset='+asset)).json();
    const pts=(j.ticks||[]).map(x=>({time:x[0],value:x[1]}));series.setData(pts);avgSeries.setData(rolling(pts));last=pts.length?pts[pts.length-1]:null;
  }else{
    const j=await (await fetch('/public/candles?asset='+asset+'&tf='+mode)).json();
    const cs=(j.candles||[]).map(c=>({time:c[0],open:c[1],high:c[2],low:c[3],close:c[4]}));series.setData(cs);last=cs.length?cs[cs.length-1]:null;
  }
  chart.timeScale().fitContent();tick();
}
async function tick(){
  let t;try{t=await (await fetch('/public/ticker?asset='+asset)).json();}catch(e){return;}
  if(t.price!=null){
    $('#px').textContent=money(t.price);
    const c=t.chg24;$('#chg').textContent=c==null?'':(c>=0?'▲ ':'▼ ')+Math.abs(c).toFixed(2)+'% 24h';$('#chg').className='chg '+(c>=0?'up':'down');
    const now=Math.floor(Date.now()/1000);
    if(mode==='round'&&series){
      if(!last||now>last.time){last={time:now,value:t.price};series.update(last);if(t.avg60!=null)avgSeries.update({time:now,value:t.avg60});}
    }else if(series&&last){
      const g={'1m':60,'5m':300,'15m':900,'1h':3600,'1d':86400}[mode];const b=Math.floor(now/g)*g;
      if(b>last.time){last={time:b,open:t.price,high:t.price,low:t.price,close:t.price};}else{last={...last,high:Math.max(last.high,t.price),low:Math.min(last.low,t.price),close:t.price};}
      series.update(last);
    }
  }
  if(t.line){
    if(!lineRef||lineRef._v!==t.line){if(lineRef)series.removePriceLine(lineRef);
      lineRef=series.createPriceLine({price:t.line,color:'#3fd0c0',lineWidth:2,lineStyle:0,axisLabelVisible:true,title:'Round line'});lineRef._v=t.line;}
    const d=t.price!=null?t.price-t.line:null;
    $('#line').innerHTML='Round line <b>'+money(t.line)+'</b>'+(d==null?'':' · <b class="'+(d>=0?'up':'down')+'">'+(d>=0?'+':'−')+money(Math.abs(d)).slice(1)+' '+(d>=0?'above':'below')+'</b>');
  }else{$('#line').textContent='Round line --';}
  if(t.seconds_left!=null)secsLeft=t.seconds_left;
  $('#avg').innerHTML='60s avg <b>'+money(t.avg60)+'</b>';
  $('#hl').innerHTML='24h <b>'+money(t.low24)+'</b> – <b>'+money(t.high24)+'</b>';
}
setInterval(tick,2000);
setInterval(()=>{if(secsLeft==null)return;secsLeft=Math.max(0,secsLeft-1);const m=Math.floor(secsLeft/60),s=Math.floor(secsLeft%60);$('#cd').innerHTML='round closes in <b>'+m+':'+String(s).padStart(2,'0')+'</b>';},1000);
async function side(){
  try{const f=await (await fetch('/public/fng')).json();if(f.value!=null){$('#fng').innerHTML='<div class="gauge"><i style="left:'+f.value+'%"></i></div>'+
      '<b style="font-family:Bungee;font-size:22px">'+f.value+'</b> <span class="mute"><b>'+f.label+'</b></span>';}}catch(e){}
  try{const n=await (await fetch('/public/news?asset='+asset)).json();
    $('#news').innerHTML=(n.items||[]).map(x=>{const ago=x.ts?Math.max(1,Math.round((Date.now()/1000-x.ts)/60)):null;
      const a=ago==null?'':(ago<60?ago+'m':(ago<1440?Math.round(ago/60)+'h':Math.round(ago/1440)+'d'))+' ago';
      return '<a href="'+x.url+'" target="_blank" rel="noopener"><b></b><small></small></a>';}).join('')||'<span class="mute">No headlines right now.</span>';
    const as=$('#news').querySelectorAll('a');(n.items||[]).forEach((x,i)=>{if(!as[i])return;as[i].querySelector('b').textContent=x.title;
      const ago=x.ts?Math.max(1,Math.round((Date.now()/1000-x.ts)/60)):null;
      as[i].querySelector('small').textContent=x.src+(ago==null?'':' · '+(ago<60?ago+'m':(ago<1440?Math.round(ago/60)+'h':Math.round(ago/1440)+'d'))+' ago');});
  }catch(e){}
}
function setMode(m){mode=m;try{localStorage.setItem('pubMode',m)}catch(e){};document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.m===m));load();}
function setAsset(a){asset=a;try{localStorage.setItem('pubAsset',a)}catch(e){};$('#nm').textContent=a;load();side();}
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>setMode(b.dataset.m));
$('#assetSel').value=asset;$('#assetSel').onchange=e=>setAsset(e.target.value);$('#nm').textContent=asset;
document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.m===mode));
const TIPS=[["Only risk what you can lose","Money you need for rent, bills or emergencies stays out of trading."],
 ["Size small","Keep any one position a small slice of your total. One bad call shouldn't hurt."],
 ["Have a plan before you click","Know your entry, your exit and how much you'll lose if wrong - before you enter."],
 ["Don't chase","A big candle already happened. Wait for the next clean setup instead of buying the top."],
 ["Streaks end","Wins and losses come in runs. Don't double up after losses or get reckless after wins."],
 ["Spread it out","Don't put everything in one coin, one trade or one idea."],
 ["Fees add up","Small fees on lots of trades can eat most of your edge. Count them."],
 ["Keep records","Write down every trade and why. Your own history is the best teacher."],
 ["Long term beats lucky","Steady habits over months matter more than any single day."],
 ["Take breaks","Tired or emotional? Step away. The market will be there tomorrow."]];
function tips(){const pick=[...TIPS].sort(()=>Math.random()-.5).slice(0,3);
  $('#tips').innerHTML=pick.map(t=>'<div class="tip"><b></b><span></span></div>').join('');
  $('#tips').querySelectorAll('.tip').forEach((el,i)=>{el.querySelector('b').textContent=pick[i][0];el.querySelector('span').textContent=pick[i][1];});}
tips();setInterval(tips,45000);
load();side();setInterval(side,300000);
</script>"""


def landing(user=None):
    if user:
        cta = (f'<a class="btn pink" href="/app">Open BRAIN &rarr;</a>'
               f'<a class="btn cream" href="/logout">Log out</a>')
        hello = f'<p>Welcome back, {E(user["username"])}.</p>'
    else:
        cta = '<a class="btn pink" href="/login">Log in</a><a class="btn teal" href="/signup">Sign up</a>'
        hello = '<p>Reads the tape. Calls the round.</p>'
    body = (
        '<section class="hero">' + island_scene()
        + '<div class="top"><a class="brand" href="/">' + brain_logo(38, "h") + '<b>BRAIN</b></a>'
          '<div style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end"><span class="pill" id="clock"></span>'
          '</div></div>'
        + f'<div class="hero-copy"><h1>BRAIN</h1>{hello}<div class="cta">{cta}</div></div></section>'
        '<main class="wrap"><div class="grid"><section class="card">'
        '<div class="chart-head"><div><div style="display:flex;align-items:center;gap:8px">'
        '<select id="assetSel" class="asset" aria-label="Coin"><option value="BTC">BTC</option><option value="XRP">XRP</option></select>'
        '<span class="mute" style="font-weight:800">live · free</span></div>'
        '<div style="margin-top:6px"><span class="px" id="px">--</span> <span class="chg" id="chg"></span></div></div>'
        '<div class="tabs"><button class="tab" data-m="round">Round</button><button class="tab" data-m="1m">1m</button>'
        '<button class="tab" data-m="15m">15m</button><button class="tab" data-m="1h">1H</button><button class="tab" data-m="1d">1D</button></div></div>'
        '<div id="chart"></div>'
        '<div class="strip"><span id="line">Round line --</span><span id="cd">round closes in --</span>'
        '<span id="avg">60s avg --</span><span id="hl">24h --</span></div></section>'
        '<aside class="side"><section class="card"><h3>SMART MONEY HABITS</h3><div id="tips"></div></section>'
        '<section class="card"><h3>FEAR &amp; GREED</h3><div id="fng"><span class="mute">loading...</span></div></section>'
        '<section class="card"><h3><span id="nm">BTC</span> NEWS</h3><div class="news" id="news"><span class="mute">loading...</span></div></section>'
        '</aside></div></main>'
        '<footer>For informational and educational use only &middot; not financial advice &middot; '
        '<a href="/terms">Terms &amp; conditions</a></footer>')
    return page("BRAIN", body, LANDING_CSS, scripts=LANDING_JS)


# ------------------------------------------------------------------------------------------------ account pages
AUTH_CSS = r"""
.authbg{position:fixed;inset:0;z-index:0}.authbg .scene{width:100%;height:100%;filter:saturate(1.05) brightness(.62)}
.authwrap{position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:18px 16px 40px}
.authcard{width:100%;max-width:420px;margin-top:4vh}
.authtabs{display:flex;gap:6px;margin-bottom:12px}
.authtabs a{flex:1;text-align:center;text-decoration:none;color:var(--text);font-weight:900;padding:9px 6px;border-radius:12px;
 border:2px solid var(--ink);background:#2c2230;font-size:14px}
.authtabs a.on{background:var(--gold);color:var(--ink)}
.authcard .btn{width:100%;margin-top:16px;text-align:center}
.small{font-size:13px}
.tw,.wave,.cloud,.boat,.win,.beam,.birds,.neon text{animation:none}
"""


def auth_page(kind, error="", info="", values=None, extra=""):
    v = values or {}
    tabs = ('<div class="authtabs">'
            + "".join(f'<a href="{href}" class="{"on" if kind == k else ""}">{lab}</a>'
                      for k, href, lab in (("login", "/login", "Log in"), ("signup", "/signup", "Sign up"), ("forgot", "/forgot", "Reset password")))
            + '</div>')
    msg = (f'<div class="err">{E(error)}</div>' if error else "") + (f'<div class="ok">{E(info)}</div>' if info else "")
    nxt = f'<input type="hidden" name="next" value="{E(v.get("next", ""))}">' if v.get("next") else ""
    if kind == "login":
        form = ('<form method="post" action="/login" autocomplete="on">' + nxt
                + f'<label for="u">Username or email</label><input id="u" name="login" value="{E(v.get("login", ""))}" autocomplete="username" required>'
                '<label for="p">Password</label><input id="p" type="password" name="password" autocomplete="current-password" required>'
                '<button class="btn pink" type="submit">Log in</button>'
                '<p class="small mute">This device stays signed in for 180 days.</p></form>')
    elif kind == "signup":
        form = ('<form method="post" action="/signup" autocomplete="on">'
                f'<label for="u">Username</label><input id="u" name="username" value="{E(v.get("username", ""))}" autocomplete="username" required>'
                f'<label for="e">Email</label><input id="e" type="email" name="email" value="{E(v.get("email", ""))}" autocomplete="email" required>'
                '<label for="p">Password</label><input id="p" type="password" name="password" autocomplete="new-password" minlength="8" required>'
                '<label for="p2">Password again</label><input id="p2" type="password" name="password2" autocomplete="new-password" minlength="8" required>'
                f'<label for="n">Anything the owner should know? <span class="mute">(optional)</span></label>'
                f'<textarea id="n" name="note" rows="2" maxlength="300">{E(v.get("note", ""))}</textarea>'
                '<label style="display:flex;gap:8px;align-items:flex-start;font-weight:700;color:var(--text)">'
                '<input type="checkbox" name="agree" value="1" required style="width:auto;margin-top:3px"> '
                '<span>I agree to the <a href="/terms" target="_blank">terms</a> - informational and educational use only.</span></label>'
                '<button class="btn teal" type="submit">Request access</button>'
                '<p class="small mute">The owner approves every new account. You get an email once you\'re in.</p></form>')
    elif kind == "forgot":
        form = ('<form method="post" action="/forgot">'
                f'<label for="e">Your account email</label><input id="e" type="email" name="email" value="{E(v.get("email", ""))}" autocomplete="email" required>'
                '<button class="btn cream" type="submit">Send reset link</button>'
                '<p class="small mute">Forgot your username? It\'s in your approval email - or log in with your email instead.</p></form>')
    elif kind == "reset":
        form = ('<form method="post" action="/reset">'
                f'<input type="hidden" name="t" value="{E(v.get("t", ""))}">'
                '<label for="p">New password</label><input id="p" type="password" name="password" autocomplete="new-password" minlength="8" required>'
                '<label for="p2">New password again</label><input id="p2" type="password" name="password2" autocomplete="new-password" minlength="8" required>'
                '<button class="btn pink" type="submit">Save new password</button></form>')
    elif kind == "setup":
        form = ('<form method="post" action="/setup">'
                '<p class="small">One-time owner setup. Use the setup code from your Railway variables (OWNER_SETUP_CODE).</p>'
                f'<label for="u">Username</label><input id="u" name="username" value="{E(v.get("username", ""))}" required>'
                f'<label for="e">Email</label><input id="e" type="email" name="email" value="{E(v.get("email", ""))}" required>'
                '<label for="p">Password</label><input id="p" type="password" name="password" minlength="8" required>'
                '<label for="p2">Password again</label><input id="p2" type="password" name="password2" minlength="8" required>'
                '<label for="c">Setup code</label><input id="c" name="code" required>'
                '<button class="btn pink" type="submit">Create owner account</button></form>')
    else:
        form = extra
    show_tabs = kind in ("login", "signup", "forgot")
    body = ('<div class="authbg">' + island_scene() + '</div><div class="authwrap">'
            '<div class="top" style="width:100%;max-width:1080px"><a class="brand" href="/">' + brain_logo(34, "a") + '<b>BRAIN</b></a></div>'
            '<div class="authcard card">' + (tabs if show_tabs else "") + msg + form + '</div></div>')
    return page({"login": "Log in", "signup": "Sign up", "forgot": "Reset password", "reset": "New password",
                 "setup": "Owner setup"}.get(kind, "BRAIN"), body, AUTH_CSS)


def message_page(title, text, link="/", link_label="Back home", tone="ok"):
    extra = (f'<h3>{E(title)}</h3><div class="{tone}">{E(text)}</div>'
             f'<a class="btn cream" href="{E(link)}">{E(link_label)}</a>')
    return auth_page("message", extra=extra)


# ------------------------------------------------------------------------------------------------ in-app tabs + admin
TABS_CSS = r"""
.app-tabs{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px;align-items:center}
.app-tabs a{text-decoration:none;font:900 13px Nunito,sans-serif;color:#eee2d7;padding:7px 12px;border-radius:999px;
 border:1px solid rgba(240,214,200,.2);background:rgba(56,45,50,.7)}
.app-tabs a.on{background:#e9a5bb;color:#1a1218;border-color:#e9a5bb}
.app-tabs .nb{display:inline-block;min-width:18px;padding:0 5px;margin-left:4px;border-radius:999px;background:#ff6b81;color:#fff;font-size:11px;text-align:center}
.app-tabs .who{margin-left:auto;font:700 12px Nunito,sans-serif;color:#bcaaa1}
"""


def app_tabs(user, active="live", pending=0):
    items = [("live", "/app", "Live"), ("guide", "/guide", "How to use")]
    if user and user.get("role") == "owner":
        items.append(("admin", "/admin", "Admin" + (f'<span class="nb">{pending}</span>' if pending else "")))
    links = "".join(f'<a href="{h}" class="{"on" if k == active else ""}">{lab}</a>' for k, h, lab in items)
    return (f'<style>{TABS_CSS}</style><nav class="app-tabs">{links}'
            f'<span class="who">{E(user["username"]) if user else ""} &middot; <a href="/logout" style="padding:3px 8px">Log out</a></span></nav>')


ADMIN_CSS = r"""
.adm{max-width:900px;margin:0 auto;padding:12px 16px 40px}
.adm table{width:100%;border-collapse:collapse;font-size:14px}.adm td,.adm th{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.adm form{display:inline}.adm .b{padding:6px 10px;border-radius:10px;border:2px solid var(--ink);font-weight:900;cursor:pointer}
.b.ok{background:var(--teal);color:var(--ink)}.b.no{background:var(--down);color:#fff}.b.n{background:#3a2e3c;color:var(--text)}
.adm .card{margin-top:14px}.tag{font-size:11px;font-weight:900;padding:2px 7px;border-radius:999px;background:#3a2e3c}
"""


def admin_page(user, db, email_on, flash="", reset_links=None):
    rows_p, rows_a = [], []
    for u in sorted(db["users"].values(), key=lambda x: -x["created"]):
        when = time.strftime("%b %d %H:%M", time.localtime(u["created"]))
        uname = E(u["username"])
        if u["status"] == "pending":
            rows_p.append(f'<tr><td><b>{uname}</b><br><span class="mute">{E(u["email"])}</span>'
                          + (f'<br><i class="mute">"{E(u.get("note", ""))}"</i>' if u.get("note") else "")
                          + f'</td><td class="mute">{when}</td><td>'
                          f'<form method="post" action="/admin"><input type="hidden" name="u" value="{uname}"><button class="b ok" name="a" value="approve">Approve</button></form> '
                          f'<form method="post" action="/admin"><input type="hidden" name="u" value="{uname}"><button class="b no" name="a" value="deny">Deny</button></form></td></tr>')
        else:
            nd = sum(1 for d in db["devices"].values() if d["u"] == u["username"].lower())
            act = "" if u.get("role") == "owner" else (
                (f'<form method="post" action="/admin"><input type="hidden" name="u" value="{uname}"><button class="b n" name="a" value="deny">Block</button></form> '
                 if u["status"] == "approved" else
                 f'<form method="post" action="/admin"><input type="hidden" name="u" value="{uname}"><button class="b ok" name="a" value="approve">Allow</button></form> ')
                + f'<form method="post" action="/admin" onsubmit="return confirm(\'Remove {uname}?\')"><input type="hidden" name="u" value="{uname}"><button class="b no" name="a" value="remove">Remove</button></form>')
            rows_a.append(f'<tr><td><b>{uname}</b> <span class="tag">{E(u.get("role", ""))}</span><br><span class="mute">{E(u["email"])}</span></td>'
                          f'<td>{E(u["status"])}<br><span class="mute">{nd} device{"s" if nd != 1 else ""}</span></td><td>{act}</td></tr>')
    resets = ""
    for r in db.get("reset_requests", []):
        link = (reset_links or {}).get(r["u"])
        resets += (f'<tr><td><b>{E(r["u"])}</b></td><td class="mute">{time.strftime("%b %d %H:%M", time.localtime(r["t"]))}</td><td>'
                   + (f'<input readonly value="{E(link)}" onclick="this.select()">' if link else
                      f'<form method="post" action="/admin"><input type="hidden" name="u" value="{E(r["u"])}"><button class="b ok" name="a" value="resetlink">Make reset link</button></form>')
                   + '</td></tr>')
    em = ('<div class="ok">Email is on - new sign-ups and password resets are emailed.</div>' if email_on else
          '<div class="err">Email isn\'t set up yet, so requests wait here. Add RESEND_API_KEY (or SMTP_HOST / SMTP_USER / SMTP_PASS) '
          'and EMAIL_FROM in Railway to get them by email.</div>')
    log = "".join(f'<div class="mute small">{time.strftime("%b %d %H:%M", time.localtime(t))} &middot; {E(m)}</div>'
                  for t, m in reversed(db.get("log", [])[-25:]))
    body = (app_tabs(user, "admin", sum(1 for u in db["users"].values() if u["status"] == "pending"))
            + (f'<div class="ok">{E(flash)}</div>' if flash else "") + em
            + f'<section class="card"><h3>WAITING FOR APPROVAL</h3><table>{"".join(rows_p) or "<tr><td class=mute>Nobody waiting.</td></tr>"}</table></section>'
            + (f'<section class="card"><h3>PASSWORD RESET REQUESTS</h3><table>{resets}</table></section>' if resets else "")
            + f'<section class="card"><h3>ACCOUNTS</h3><table>{"".join(rows_a)}</table></section>'
            + f'<section class="card"><h3>RECENT ACTIVITY</h3>{log or "<span class=mute>nothing yet</span>"}</section>')
    return page("Admin - BRAIN", f'<div class="adm">{body}</div>', ADMIN_CSS + ".small{font-size:12px}")


# ------------------------------------------------------------------------------------------------ how to use
GUIDE = [
    ("The basics", [
        ("What BRAIN does", "Every 15 minutes there's a new BTC (and XRP) up-or-down round. BRAIN watches price across the big exchanges every "
         "second and makes two calls each round: will it finish ABOVE the round's line (UP) or BELOW it (DOWN)?"),
        ("The line", "The target price for this round. Rounds settle on the average price of the final 60 seconds, from the "
         "CF Benchmarks index (Coinbase, Kraken, Bitstamp, Gemini). BRAIN's live price uses those same exchanges."),
        ("Time until call", "Countdown to the next call. EARLY locks at 4:00 into the round, SEALED at 8:00."),
    ]),
    ("The calls", [
        ("EARLY call (4:00)", "First read of the round. More time left = more can change."),
        ("SEALED call (8:00)", "The main call. Locked and never changed. This is the one the streak counts."),
        ("SUPER / GOOD / WEAK", "Confidence. SUPER = the reads strongly agree, GOOD = solid, WEAK = leaning but close. "
         "Only skipped when it's a true coin flip for a full minute."),
        ("↺ REVERSAL", "BRAIN is calling the side that's LOSING right now - because flip risk is high and RSI + momentum point "
         "the other way. Shows the payout (e.g. ~4.5x). Riskier, pays more. Turned off automatically if the backtest "
         "shows reversals lose money."),
        ("★ 80% SETUP", "This exact kind of setup won 80%+ in the backtest on rounds it had never seen. Shows its money result too - "
         "an 80% winner bought at 85¢ can still lose money."),
    ]),
    ("The tiles", [
        ("FLIP RADAR", "Chance the call on screen flips before the close: LOW 0-20%, WATCH 21-45%, HIGH 46-70%, CRITICAL 71%+. "
         "Built from live selling/buying pressure, how close price is to the line, line crosses, order-book walls and the "
         "final-minute average. Pressure has to hold 10 seconds before it can jump above 20%."),
        ("RSI (14)", "Overbought (70+) or oversold (30-) - stretched moves often snap back."),
        ("LINE CROSSES", "How many times price crossed the line this round. 0-1 = clean, 2 = some chop, 3+ = choppy."),
        ("STREAK", "Sealed-call wins or losses in a row. Gold = wins, lavender = losses."),
        ("Win-rate badge (top right)", "Current streak + win %. Tap it for every round: today, this week, all-time, by day and by week."),
        ("BUY PRESSURE", "Coins bought vs sold right now across every exchange (each trade counted once)."),
        ("Projected settlement", "In the last minute: the running 60-second average the round settles on, and what the remaining "
         "seconds must average to flip it. LOCKED = basically out of reach."),
    ]),
    ("Alerts", [
        ("WHALE", "One giant market order."),
        ("⟳ WALL MOVED", "A big resting order was pulled and re-placed at a new price. Sell wall moving DOWN = a seller chasing price "
         "lower (bearish). Buy wall moving UP = a buyer chasing it higher (bullish)."),
        ("× PULLED / SPOOF", "A big order right next to price vanished without being re-placed - liquidity pulled, often a fake wall."),
        ("FILLED", "A big wall got eaten - that floor or ceiling is gone."),
        ("FAKE BREAKOUT", "Price poked past the recent high/low and snapped right back."),
        ("FORCED SALE", "Liquidations on futures exchanges - extra pressure in that direction."),
    ]),
    ("Good habits", [
        ("Use the tiers", "SUPER and GOOD are the strong calls. Treat WEAK and REVERSAL as smaller-size ideas."),
        ("Watch the radar late", "A HIGH or CRITICAL radar after 8:00 is your warning the sealed call is in trouble."),
        ("Nothing is certain", "Any 15-minute round can flip on one big order. BRAIN is for information and education only - not financial advice."),
    ]),
]

GUIDE_CSS = r"""
.guide{max-width:820px;margin:0 auto;padding:12px 16px 50px;font-family:Nunito,sans-serif}
.guide h2{font-family:Bungee,sans-serif;font-weight:400;color:#dcbb91;letter-spacing:1px;margin:22px 0 8px;font-size:18px}
.guide .it{background:rgba(56,45,50,.85);border:1px solid rgba(240,214,200,.14);border-radius:14px;padding:11px 13px;margin:8px 0}
.guide .it b{display:block;color:#fbf4ec;font-size:15px;margin-bottom:2px}.guide .it span{color:#e2d4c9}
"""


def guide_html(user):
    out = [app_tabs(user, "guide"), '<div class="guide"><h1 style="font-family:Bungee,sans-serif;font-weight:400;'
           'color:#fbf4ec;margin:6px 0 2px">How to use BRAIN</h1><p class="mute">Everything on the screen, in plain words.</p>']
    for sec, items in GUIDE:
        out.append(f'<h2>{E(sec).upper()}</h2>')
        out += [f'<div class="it"><b>{E(t)}</b><span>{E(d)}</span></div>' for t, d in items]
    out.append('</div>')
    return page("How to use - BRAIN", "".join(out), GUIDE_CSS)


TERMS = [
    ("Information and education only", "BRAIN shows market data, charts and model readings for informational and educational "
     "purposes only. Nothing on this site is financial, investment, legal or tax advice, or a recommendation to buy or sell anything."),
    ("No guarantees", "Calls, confidence levels, win rates, backtests and every other reading are estimates. Past results don't "
     "predict future results, data can be late or wrong, and the service can go down without warning."),
    ("Your decisions, your risk", "Trading and investing can lose money, including everything you put in. You're responsible for "
     "your own decisions. Talk to a licensed professional before making financial decisions."),
    ("Access", "Accounts are approved by the owner and can be paused or removed at any time. Keep your login private - don't "
     "share your account or copy and resell what you see here."),
    ("Your data", "We store your username, email, a scrambled (hashed) password and which devices are signed in, only to run "
     "your account. Ask the owner any time to delete your account."),
    ("Changes", "These terms can change. Using the site after a change means you accept the new terms."),
]


def terms_page():
    items = "".join(f'<div class="it"><b>{E(t)}</b><span>{E(d)}</span></div>' for t, d in TERMS)
    body = ('<div class="guide"><div class="top" style="padding:10px 0"><a class="brand" href="/">' + brain_logo(34, "t")
            + '<b>BRAIN</b></a></div><h1 style="font-family:Bungee,sans-serif;font-weight:400;color:#fbf4ec;margin:6px 0 2px">'
            'Terms &amp; conditions</h1><p class="mute">Last updated October 20, 2026.</p>' + items
            + '<p style="margin-top:18px"><a class="btn cream" href="/">Back home</a></p></div>')
    return page("Terms - BRAIN", body, GUIDE_CSS)
