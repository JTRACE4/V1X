"""Welcome page, account pages, admin and the How-to-use guide for BRAIN (added 2026-10-20).
Plain HTML/CSS/JS strings - no build step. The island-town art is an original inline SVG (bold-outline cartoon look,
sunset 'vice city' palette) drawn for this page."""
import html as _html
import time
try:
    from zoneinfo import ZoneInfo as _ZI
    _ET_TZ = _ZI("America/New_York")
except Exception:
    _ET_TZ = None

E = _html.escape

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT@0,9..144,400..900,0..100;1,9..144,400..900,0..100&family=Nunito:wght@400;600;700;800;900&family=Montserrat:wght@500;600;700;800;900&family=Carlito:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">')


def brain_logo(size=44, p="l"):
    """The BRAIN mark - the same brain as in the hero art (static/logo.png, rendered by tools/make_logo.py)."""
    return f'<img class="mark" src="/static/logo.png" width="{size}" height="{size}" alt="">'


# ------------------------------------------------------------------------------------------------ hero art
def hero_img(cls="scene"):
    """The brain at its trading desk over a Puerto Rico forest cove at dusk (rendered by tools/hero_art.py)."""
    return (f'<picture class="{cls}"><source srcset="/static/hero.webp" type="image/webp">'
            '<img src="/static/hero.jpg" alt="The BRAIN at a trading desk with three chart screens, looking out over a '
            'forest cove at dusk" width="1600" height="1200" decoding="async" fetchpriority="high"></picture>')


# ------------------------------------------------------------------------------------------------ shared style
BASE_CSS = r"""
:root{--bg:#211b1e;--tile:rgba(48,38,43,.82);--line:rgba(240,214,200,.13);--cream:#fbf4ec;--text:#eee2d7;--mute:#bcaaa1;
--tan:#dcbb91;--rose:#e9a5bb;--gold:#e5b85c;--up:#43cdb7;--down:#e8798f;--ink:#1a1416;
--serif:'Fraunces',Georgia,'Times New Roman',serif;--sans:'Carlito','Calibri',-apple-system,'Segoe UI',sans-serif;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--bg);color:var(--text);font:15px/1.5 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--rose)}
.wrap{max-width:1080px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.top{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px max(16px,env(safe-area-inset-right,0px)) 12px max(16px,env(safe-area-inset-left,0px));position:relative;z-index:3}
.brand{display:flex;align-items:center;gap:9px;text-decoration:none;color:var(--cream)}
.brand .mark{filter:drop-shadow(0 2px 10px rgba(233,165,187,.35))}
.brand b{font-family:var(--serif);font-weight:700;font-size:21px;letter-spacing:.3px;font-variation-settings:"SOFT" 100}
.pill{display:inline-flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;background:rgba(20,15,18,.55);
 border:1px solid var(--line);font-weight:700;font-size:13px;white-space:nowrap;color:var(--text);backdrop-filter:blur(6px);font-variant-numeric:tabular-nums}
.btn{display:inline-block;padding:12px 24px;border-radius:999px;font:800 15px var(--sans);text-decoration:none;cursor:pointer;
 border:1px solid transparent;transition:transform .12s,filter .12s;letter-spacing:.2px}
.btn:hover{filter:brightness(1.06)}.btn:active{transform:translateY(1px)}
.btn:focus-visible,.tab:focus-visible,select:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.btn.pink{background:var(--rose);color:var(--ink)}
.btn.teal{background:rgba(251,244,236,.08);color:var(--cream);border-color:rgba(251,244,236,.45);backdrop-filter:blur(6px)}
.btn.cream{background:rgba(251,244,236,.08);color:var(--cream);border-color:var(--line)}
.card{background:var(--tile);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.card h3{margin:0 0 10px;font:600 12px var(--sans);letter-spacing:1.6px;text-transform:uppercase;color:var(--tan)}
.mute{color:var(--mute)}.up{color:var(--up)}.down{color:var(--down)}
input,select,textarea{font:inherit;color:var(--cream);background:rgba(20,15,18,.7);border:1px solid #4a3b42;border-radius:12px;padding:11px 12px;width:100%}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--rose)}
label{display:block;font-weight:700;font-size:13px;margin:12px 0 5px;color:var(--tan)}
.err{background:rgba(232,121,143,.12);border:1px solid var(--down);color:#ffd9df;padding:9px 12px;border-radius:12px;margin:8px 0;font-weight:700}
.ok{background:rgba(67,205,183,.1);border:1px solid var(--up);color:#d8fff8;padding:9px 12px;border-radius:12px;margin:8px 0;font-weight:700}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


# link preview (2026-10-20): what iMessage / Discord / Slack / X show when the BRAIN link is pasted. The dashboard fills these
# in at startup - base = the public site address, desc = a callable returning a live one-line summary (BTC / XRP prices + odds).
OG = {"base": "", "desc": None}


def og_tags():
    base = OG.get("base") or ""
    try:
        desc = (OG["desc"]() if OG.get("desc") else "") or ""
    except Exception:
        desc = ""
    desc = desc or "Live BTC and XRP prices with 15-minute market odds - BRAIN's read on every round."
    img = f"{base}/og.png?t={int(time.time() // 60)}"
    t = "BRAIN - live BTC & XRP market odds"
    return (f'<meta name="description" content="{E(desc)}">'
            '<meta property="og:type" content="website"><meta property="og:site_name" content="BRAIN">'
            f'<meta property="og:title" content="{E(t)}"><meta property="og:description" content="{E(desc)}">'
            f'<meta property="og:url" content="{E(base + "/")}">'
            f'<meta property="og:image" content="{E(img)}"><meta property="og:image:secure_url" content="{E(img)}">'
            '<meta property="og:image:type" content="image/png"><meta property="og:image:width" content="1200">'
            '<meta property="og:image:height" content="630">'
            '<meta property="og:image:alt" content="BRAIN - live BTC and XRP prices with market UP / DOWN odds">'
            '<meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:title" content="{E(t)}"><meta name="twitter:description" content="{E(desc)}">'
            f'<meta name="twitter:image" content="{E(img)}">')


def page(title, body, extra_css="", extra_head="", scripts=""):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>{E(title)}</title><meta name="theme-color" content="#211b1e">{og_tags()}'
            '<link rel="icon" type="image/png" href="/static/logo-64.png"><link rel="apple-touch-icon" href="/static/logo-180.png">'
            f'{FONTS}{extra_head}'
            f'<style>{BASE_CSS}{extra_css}</style></head><body>{body}{scripts}</body></html>')


# ------------------------------------------------------------------------------------------------ welcome page
LANDING_CSS = r"""
.hero{position:relative;height:min(82vh,760px);min-height:520px;overflow:hidden}
.hero .scene,.hero .scene img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 72%}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(11,16,22,.78) 0%,rgba(11,16,22,.2) 34%,rgba(11,16,22,0) 55%,rgba(33,27,30,.85) 100%);pointer-events:none}
.hero .top{position:absolute;left:0;right:0;top:0;z-index:3}
.hero-copy{position:absolute;left:0;right:0;top:12%;text-align:center;z-index:2;padding:0 16px}
.hero-copy h1{margin:0;font-family:var(--serif);font-weight:800;font-size:clamp(56px,13vw,124px);line-height:.95;color:var(--cream);
 letter-spacing:-1px;font-variation-settings:"SOFT" 100,"opsz" 144;text-shadow:0 0 40px rgba(233,165,187,.35),0 2px 0 rgba(0,0,0,.35)}
.hero-copy p{margin:12px 0 20px;font:600 italic clamp(16px,3.6vw,20px) var(--serif);color:#f3e3d6}
.hero-copy .cta{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.ff{position:absolute;width:5px;height:5px;border-radius:50%;background:#ffe2a0;box-shadow:0 0 10px 3px rgba(255,214,140,.55);z-index:1;animation:ff 6s ease-in-out infinite}
@keyframes ff{0%,100%{opacity:.15;transform:translate(0,0)}50%{opacity:1;transform:translate(6px,-8px)}}
.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:16px;margin:-40px auto 26px;position:relative;z-index:4}
@media (max-width:860px){.grid{grid-template-columns:minmax(0,1fr)}}
.chart-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px;justify-content:space-between}
.px{font-family:var(--serif);font-weight:700;font-size:clamp(30px,6vw,40px);color:var(--cream);line-height:1;font-variant-numeric:tabular-nums}
.chg{font-weight:800;font-size:14px}
.tabs{display:flex;gap:4px;flex-wrap:wrap;background:rgba(20,15,18,.6);border:1px solid var(--line);border-radius:999px;padding:3px}
.tab{border:0;background:transparent;color:var(--mute);border-radius:999px;padding:6px 11px;font:800 13px var(--sans);cursor:pointer}
.tab.on{background:var(--rose);color:var(--ink)}
#chart{height:340px;margin-top:12px;border-radius:12px;overflow:hidden}
.strip{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;font-weight:700;font-size:13px;font-variant-numeric:tabular-nums}
.strip span{background:rgba(20,15,18,.6);border:1px solid var(--line);border-radius:999px;padding:5px 11px;color:var(--mute)}
.strip b{color:var(--text)}
.side{display:flex;flex-direction:column;gap:16px;min-width:0}
.gauge{position:relative;height:10px;border-radius:999px;background:linear-gradient(90deg,#e8798f,#dcbb91,#e5b85c,#9fcf9a,#43cdb7);margin:12px 0 8px}
.gauge i{position:absolute;top:-6px;width:4px;height:22px;border-radius:2px;background:var(--cream);transform:translateX(-2px);box-shadow:0 0 0 3px rgba(26,20,22,.8)}
.fng{display:flex;align-items:baseline;gap:8px}.fng b{font-family:var(--serif);font-size:28px;color:var(--cream)}
.tip{padding:10px 0;border-bottom:1px solid var(--line)}.tip:last-child{border-bottom:0}
.tip b{display:block;color:var(--cream);font-weight:800}.tip span{color:var(--mute);font-size:14px}
.news a{display:block;text-decoration:none;color:var(--text);padding:10px 0;border-bottom:1px solid var(--line)}
.news a:last-child{border-bottom:0}.news b{display:block;font-weight:700;line-height:1.35}
.news small{color:var(--mute);font-weight:700}
footer{text-align:center;color:var(--mute);font-size:12px;padding:6px 16px 34px}
select.asset{width:auto;padding:7px 12px;font-weight:800;border-radius:999px}
"""

LANDING_JS = r"""
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<script>
const $=s=>document.querySelector(s);
let asset='BTC',mode='1m';try{asset=localStorage.getItem('pubAsset')||'BTC';mode=localStorage.getItem('pubMode2')||'1m';}catch(e){}
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
  chart=LightweightCharts.createChart(el,{autoSize:true,layout:{background:{type:'solid',color:'rgba(20,15,18,0)'},textColor:'#bcaaa1',fontFamily:'Montserrat',attributionLogo:false},
    grid:{vertLines:{color:'rgba(240,214,200,.06)'},horzLines:{color:'rgba(240,214,200,.06)'}},
    rightPriceScale:{borderColor:'rgba(240,214,200,.13)'},timeScale:{borderColor:'rgba(240,214,200,.13)',timeVisible:true,secondsVisible:mode==='round',
      tickMarkFormatter:(t)=>mode==='1d'?fmtDay.format(new Date(t*1000)):fmtET.format(new Date(t*1000))},
    localization:{timeFormatter:(t)=>fmtETs.format(new Date(t*1000)),priceFormatter:p=>money(p)},crosshair:{mode:0}});
  if(mode==='round'){
    series=chart.addAreaSeries({lineColor:'#e9a5bb',topColor:'rgba(233,165,187,.30)',bottomColor:'rgba(233,165,187,0)',lineWidth:2,priceLineVisible:false});
    avgSeries=chart.addLineSeries({color:'#e5b85c',lineWidth:2,lineStyle:2,priceLineVisible:false,lastValueVisible:false});
  }else{
    series=chart.addCandlestickSeries({upColor:'#43cdb7',downColor:'#e8798f',borderVisible:false,wickUpColor:'#43cdb7',wickDownColor:'#e8798f'});
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
      lineRef=series.createPriceLine({price:t.line,color:'#fbf4ec',lineWidth:1,lineStyle:2,axisLabelVisible:true,title:'Round line'});lineRef._v=t.line;}
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
  try{const f=await (await fetch('/public/fng')).json();if(f.value!=null){$('#fng').innerHTML='<div class="gauge"><i style="left:'+f.value+'%"></i></div><div class="fng"><b>'+f.value+'</b><span class="mute">'+f.label+'</span></div>';}}catch(e){}
  try{const n=await (await fetch('/public/news?asset='+asset)).json();
    $('#news').innerHTML=(n.items||[]).map(x=>{const ago=x.ts?Math.max(1,Math.round((Date.now()/1000-x.ts)/60)):null;
      const a=ago==null?'':(ago<60?ago+'m':(ago<1440?Math.round(ago/60)+'h':Math.round(ago/1440)+'d'))+' ago';
      return '<a href="'+x.url+'" target="_blank" rel="noopener"><b></b><small></small></a>';}).join('')||'<span class="mute">No headlines right now.</span>';
    const as=$('#news').querySelectorAll('a');(n.items||[]).forEach((x,i)=>{if(!as[i])return;as[i].querySelector('b').textContent=x.title;
      const ago=x.ts?Math.max(1,Math.round((Date.now()/1000-x.ts)/60)):null;
      as[i].querySelector('small').textContent=x.src+(ago==null?'':' · '+(ago<60?ago+'m':(ago<1440?Math.round(ago/60)+'h':Math.round(ago/1440)+'d'))+' ago');});
  }catch(e){}
}
function setMode(m){mode=m;try{localStorage.setItem('pubMode2',m)}catch(e){};document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.m===m));load();}
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
        cta = '<a class="btn pink" href="/analysis">Open BRAIN</a><a class="btn teal" href="/logout">Log out</a>'
        hello = f'<p>Welcome back, {E(user["username"])}.</p>'
    else:
        cta = '<a class="btn pink" href="/pricing">Get access</a><a class="btn teal" href="/login">Log in</a>'
        hello = '<p>Market intelligence, wired in.</p>'
    flies = "".join(f'<i class="ff" style="left:{l}%;top:{t}%;animation-delay:{dl}s"></i>'
                    for l, t, dl in ((14, 44, 0), (27, 40, 1.3), (39, 47, 2.6), (58, 42, 0.8), (71, 46, 3.1), (84, 41, 1.9), (49, 38, 4.2)))
    body = (
        '<section class="hero">' + hero_img() + flies
        + '<div class="top"><a class="brand" href="/">' + brain_logo(34, "h") + '<b>BRAIN</b></a>'
          '<span class="pill" id="clock"></span></div>'
        + f'<div class="hero-copy"><h1>BRAIN</h1>{hello}<div class="cta">{cta}</div></div></section>'
        '<main class="wrap"><div class="grid"><section class="card">'
        '<div class="chart-head"><div><div style="display:flex;align-items:center;gap:8px">'
        '<select id="assetSel" class="asset" aria-label="Coin"><option value="BTC">BTC</option><option value="XRP">XRP</option></select>'
        '<span class="mute" style="font-weight:700;font-size:13px">live</span></div>'
        '<div style="margin-top:8px"><span class="px" id="px">--</span> <span class="chg" id="chg"></span></div></div>'
        '<div class="tabs"><button class="tab" data-m="1m">1m</button><button class="tab" data-m="15m">15m</button>'
        '<button class="tab" data-m="1h">1H</button><button class="tab" data-m="1d">1D</button><button class="tab" data-m="round">Line</button></div></div>'
        '<div id="chart"></div>'
        '<div class="lw-credit" style="font-size:10.5px;color:#8f8079;margin-top:4px">Charting by <a href="https://www.tradingview.com/" target="_blank" rel="noopener">TradingView Lightweight Charts&trade;</a> &middot; &copy; TradingView, Inc.</div>'
        '<div class="strip"><span id="line">Round line --</span><span id="cd">round closes in --</span>'
        '<span id="avg">60s avg --</span><span id="hl">24h --</span></div></section>'
        '<aside class="side"><section class="card"><h3>Smart money habits</h3><div id="tips"></div></section>'
        '<section class="card"><h3>Fear &amp; Greed</h3><div id="fng"><span class="mute">loading...</span></div></section>'
        '<section class="card"><h3><span id="nm">BTC</span> news</h3><div class="news" id="news"><span class="mute">loading...</span></div></section>'
        '</aside></div></main>'
        '<footer>For informational and educational use only &middot; not financial advice &middot; '
        '<a href="/info">Info Center</a> &middot; <a href="/terms">Terms &amp; conditions</a></footer>')
    return page("BRAIN", body, LANDING_CSS, scripts=LANDING_JS)


# ------------------------------------------------------------------------------------------------ account pages
AUTH_CSS = r"""
.authbg{position:fixed;inset:0;z-index:0}.authbg .scene,.authbg img{width:100%;height:100%;object-fit:cover;object-position:50% 72%;filter:blur(7px) brightness(.48) saturate(1.05);transform:scale(1.05)}
.authwrap{position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:16px 16px 40px}
.authcard{width:100%;max-width:420px;margin-top:4vh;backdrop-filter:blur(10px)}
.authtabs{display:flex;gap:4px;margin-bottom:14px;background:rgba(20,15,18,.6);border:1px solid var(--line);border-radius:999px;padding:3px}
.authtabs a{flex:1;text-align:center;text-decoration:none;color:var(--mute);font-weight:800;padding:8px 6px;border-radius:999px;font-size:14px}
.authtabs a.on{background:var(--rose);color:var(--ink)}
.authcard .btn{width:100%;margin-top:18px;text-align:center}
.small{font-size:13px}
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
                '<p class="small mute">Free account. The live dashboard needs a membership - you\'ll pick one next.</p></form>')
    elif kind == "forgot":
        form = ('<form method="post" action="/forgot">'
                f'<label for="e">Your account email</label><input id="e" type="email" name="email" value="{E(v.get("email", ""))}" autocomplete="email" required>'
                '<button class="btn cream" type="submit">Send reset link</button>'
                '<p class="small mute">Forgot your username? Log in with your email instead.</p></form>')
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
    body = ('<div class="authbg">' + hero_img() + '</div><div class="authwrap">'
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
.app-tabs .tg{display:inline-flex;gap:3px;padding:3px;border-radius:999px;background:rgba(30,46,50,.42);border:1px solid rgba(255,255,255,.14);
 -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px)}
.app-tabs a{display:inline-flex;align-items:center;gap:6px;text-decoration:none;font:800 13px Montserrat,Arial,sans-serif;color:#eee2d7;
 padding:8px 15px;border-radius:999px;letter-spacing:.3px}
.app-tabs a svg{width:16px;height:16px;flex:none}
.app-tabs a.on{background:#e9a5bb;color:#1a1218}
.app-tabs .tr{margin-left:auto;display:inline-flex;align-items:center;gap:6px}
.app-tabs .tr a{padding:6px 12px;font-size:12px;border:1px solid rgba(240,214,200,.2);background:rgba(56,45,50,.7)}
.app-tabs .tr a.on{background:#e9a5bb;color:#1a1218;border-color:#e9a5bb}
.app-tabs .nb{display:inline-block;min-width:18px;padding:0 5px;margin-left:4px;border-radius:999px;background:#ff6b81;color:#fff;font-size:11px;text-align:center}
.app-tabs .who{font:700 12px Montserrat,Arial,sans-serif;color:#bcaaa1}
@media (max-width:520px){.app-tabs a{padding:8px 12px}.app-tabs .who .un{display:none}}
"""


_ICO_GEAR = ('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="2"/>'
             '<path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" '
             'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>')
_ICO_CHART = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h16M7 16V9M7 9V6M12 14V5M17 17v-6" fill="none" stroke="currentColor" '
              'stroke-width="2" stroke-linecap="round"/><rect x="5.5" y="9" width="3" height="5" rx="1" fill="currentColor"/>'
              '<rect x="15.5" y="11" width="3" height="4" rx="1" fill="currentColor"/></svg>')


def app_tabs(user, active="live", pending=0):
    """2026-10-23 (user): main tabs on the left - "Analysis" (the BRAIN bot dashboard, gear icon) and "Charts"; My pass / Admin and
    the account on the right. "How to use" lives at the bottom of the Analysis page now. A Chart Only pass sees only Charts."""
    try:
        import billing as _b
        chart_only = _b.chart_only(user)
    except Exception:
        chart_only = False
    if chart_only and (user or {}).get("role") != "owner":
        main = [("charts", "/charts", _ICO_CHART + "Charts")]
    else:
        main = [("live", "/analysis", _ICO_GEAR + "Analysis"), ("charts", "/charts", _ICO_CHART + "Charts")]
    main.append(("info", "/info", "Info Center"))
    right = []
    if user and user.get("role") != "owner":
        right.append(("pricing", "/pricing", "Membership"))
    if user and user.get("role") == "owner":
        right.append(("admin", "/admin", "Admin" + (f'<span class="nb">{pending}</span>' if pending else "")))
    lk = lambda items: "".join(f'<a href="{h}" class="{"on" if k == active else ""}">{lab}</a>' for k, h, lab in items)
    return (f'<style>{TABS_CSS}</style><nav class="app-tabs"><div class="tg">{lk(main)}</div>'
            f'<div class="tr">{lk(right)}<span class="who"><span class="un">{E(user["username"]) if user else ""} &middot; </span>'
            f'<a href="/logout" style="padding:3px 8px;border:0;background:none">Log out</a></span></div></nav>')


ADMIN_CSS = r"""
.adm{max-width:900px;margin:0 auto;padding:12px 16px 40px}
.adm table{width:100%;border-collapse:collapse;font-size:14px}.adm td,.adm th{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.adm form{display:inline}.adm .b{padding:6px 12px;border-radius:999px;border:0;font-weight:800;cursor:pointer}
.b.ok{background:var(--up);color:var(--ink)}.b.no{background:var(--down);color:#fff}.b.n{background:#3a2e3c;color:var(--text)}
.adm .card{margin-top:14px}.tag{font-size:11px;font-weight:900;padding:2px 7px;border-radius:999px;background:#3a2e3c}.st{display:inline-block;font-size:11px;font-weight:900;letter-spacing:1px;padding:3px 8px;border-radius:999px;margin-bottom:4px}.st-on{background:rgba(61,214,156,.18);color:#3dd69c}.st-pend{background:rgba(233,180,90,.18);color:#e9b45a}.st-off{background:rgba(240,84,84,.18);color:#f05454}.st-chart{background:rgba(110,170,230,.18);color:#8fc4f0}
"""


def admin_page(user, db, email_on, flash="", reset_links=None, kalshi=None):
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
            au = float(u.get("access_until") or 0)
            # 2026-10-23 (user): BRAIN ACTIVE = paid / has the bot tabs; PENDING BRAIN = no access yet (hasn't paid)
            if u.get("role") == "owner":
                st, pas = '<span class="st st-on">OWNER</span>', "always"
            elif u["status"] != "approved":
                st, pas = '<span class="st st-off">BLOCKED</span>', "no access"
            elif u["username"].lower() in {"j44", "itsjordayer", "jordanmcontact", "j4admin"}:   # billing.COMP_ACCOUNTS
                st, pas = '<span class="st st-on">BRAIN ACTIVE</span>', "always (your account)"
            elif au > time.time():
                _et = _ET_TZ
                _w = (__import__("datetime").datetime.fromtimestamp(au, _et).strftime("%b %d %-I:%M %p ET") if _et else
                      time.strftime("%b %d %H:%M", time.localtime(au)))
                st, pas = '<span class="st st-on">BRAIN ACTIVE</span>', f"until {_w}"
            elif float(u.get("chart_until") or 0) > time.time():
                _cu = float(u["chart_until"])
                _w = (__import__("datetime").datetime.fromtimestamp(_cu, _ET_TZ).strftime("%b %d %-I:%M %p ET") if _ET_TZ else
                      time.strftime("%b %d %H:%M", time.localtime(_cu)))
                st, pas = '<span class="st st-chart">CHART ONLY</span>', f"until {_w}"
            else:
                st, pas = '<span class="st st-pend">PENDING BRAIN</span>', "hasn&rsquo;t paid &middot; no access"
            give = "" if u.get("role") == "owner" else (
                f'<form method="post" action="/admin"><input type="hidden" name="u" value="{uname}"><input type="hidden" name="a" value="grant">'
                f'<input name="days" type="number" min="1" max="400" value="7" style="width:64px"> '
                f'<select name="kind" style="padding:5px;border-radius:8px"><option value="full">BRAIN</option><option value="chart">Chart Only</option></select> '
                f'<button class="b ok">Give days</button></form> ')
            rows_a.append(f'<tr><td><b>{uname}</b> <span class="tag">{E(u.get("role", ""))}</span><br><span class="mute">{E(u["email"])}</span></td>'
                          f'<td>{st}<br><b>{pas}</b><br><span class="mute">{nd} device{"s" if nd != 1 else ""}</span></td><td>{give}{act}</td></tr>')
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
            + kalshi_key_card(kalshi or {})
            + f'<section class="card"><h3>WAITING FOR APPROVAL</h3><table>{"".join(rows_p) or "<tr><td class=mute>Nobody waiting.</td></tr>"}</table></section>'
            + (f'<section class="card"><h3>PASSWORD RESET REQUESTS</h3><table>{resets}</table></section>' if resets else "")
            + f'<section class="card"><h3>ACCOUNTS</h3><table>{"".join(rows_a)}</table></section>'
            + f'<section class="card"><h3>RECENT ACTIVITY</h3>{log or "<span class=mute>nothing yet</span>"}</section>')
    return page("Admin - BRAIN", f'<div class="adm">{body}</div>', ADMIN_CSS + ".small{font-size:12px}")


PRICING_CSS = r"""
.pr{max-width:980px;margin:0 auto;padding:18px 16px 44px}
.pr h1{font-family:Fraunces,Georgia,serif;font-weight:700;color:#fbf4ec;margin:8px 0 4px;font-size:34px}
.pr .lead{color:#d6cac4;margin:0 0 18px}
.pr .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.pr .plan{position:relative;background:rgba(30,46,50,.42);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,.18);border-radius:22px;padding:20px 18px;box-shadow:0 0 18px rgba(255,255,255,.10)}
.pr .plan.best{border-color:rgba(242,196,107,.65);box-shadow:0 0 22px rgba(242,196,107,.22)}
.pr .tagb{position:absolute;top:-11px;right:16px;background:#f2c46b;color:#2a2226;font-weight:900;font-size:11px;letter-spacing:1px;
  padding:3px 10px;border-radius:999px}
.pr .nm{font-weight:900;letter-spacing:1.5px;color:#cdb6ad;font-size:13px}
.pr .px{font-family:Fraunces,Georgia,serif;font-size:40px;color:#fbf4ec;margin:6px 0 0}
.pr .per{color:#bcaaa1;font-size:13px;margin-bottom:12px}
.pr ul{list-style:none;padding:0;margin:0 0 16px;color:#e9ded8;font-size:14px;line-height:1.7}
.pr ul li::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:#a9cfc1;margin-right:9px;vertical-align:2px}
.pr .go{display:block;text-align:center;padding:12px;border-radius:999px;font-weight:900;text-decoration:none;background:#e9a5bb;color:#2a2226}
.pr .go.off{background:#3a2e3c;color:#bcaaa1;pointer-events:none}
.pr .status{margin:0 0 16px;padding:12px 14px;border-radius:14px;background:rgba(61,214,156,.10);border:1px solid rgba(61,214,156,.35);color:#c9f7e6}
.pr .status.none{background:rgba(255,255,255,.04);border-color:rgba(255,255,255,.15);color:#e9ded8}
.pr .fine{color:#bcaaa1;font-size:12.5px;margin-top:18px;line-height:1.6}
.pr .co-h{font-family:Fraunces,Georgia,serif;font-weight:700;color:#fbf4ec;margin:26px 0 10px;font-size:22px}
.pr .plan.co{max-width:420px}
.pr .renew-note{color:#d6cac4;font-size:13.5px;margin:0 0 14px}
.pr .mng{display:inline-block;margin:10px 0 2px;padding:9px 18px;border-radius:999px;border:1px solid rgba(201,247,230,.55);
  background:rgba(201,247,230,.10);color:#c9f7e6;font:inherit;font-weight:800;cursor:pointer}
.pr .mng-sub{font-size:12px;color:#a9cfc1}
"""

PLAN_FEATURES = ["Live dashboard: 4:00, 6:00 + 8:00 calls with BRAIN confidence", "Spoken alerts, flip watch, cash-out + coin-flip notes",
                 "Whale impact scores + Trader Radar", "Graded record, $100 backtest, price-target history",
                 "Live charts for every coin (same as Chart Only)", "The BRAIN Playbook (PDF guide to every screen)"]


CHART_FEATURES = ["Live BTC + XRP charts (1m to 1D)", "EMA 12 / 25 / 50, RSI and MACD read in plain words",
                  "Support + resistance zones (held / rejected counts)", "\"What do these mean?\" indicator guide",
                  "Chart patterns with their track record", "No BRAIN bot features (calls, flip radar, alerts, voice)"]


def pricing_page(user, plans, until_text=None, active=False, chart_until_text=None, manage=False, auto_renew=None):
    """plans: [(key, label, price, per_day_text, checkout_url_or_'')]. Keys starting with "chart" are the Chart Only pass.
    2026-10-24 (user): memberships auto-renew by default; manage=True shows the button to Stripe's billing page."""
    mbtn = ('<form method="post" action="/billing/portal" style="display:inline"><button class="mng">Manage membership</button></form>'
            '<div class="mng-sub">Turn auto-renew off or on, update your card, see receipts.</div>') if manage else ""
    ren = (" It renews automatically on that date." if auto_renew else (" Auto-renew is off - it ends on that date." if manage else ""))
    if user and active:
        status = (f'<div class="status">Your membership is active until <b>{E(until_text or "")}</b>.{ren} '
                  f'&middot; <a href="/playbook.pdf" style="color:#c9f7e6;font-weight:800">Download your BRAIN Playbook</a>{mbtn}</div>')
    elif user and chart_until_text:
        status = (f'<div class="status">Your Chart Only membership is active until <b>{E(chart_until_text)}</b>.{ren} '
                  f'&middot; <a href="/charts" style="color:#c9f7e6;font-weight:800">Open your charts</a> &middot; upgrade below for the full BRAIN bot.{mbtn}</div>')
    elif user:
        status = ('<div class="status none">No active membership yet - pick one below to unlock the live dashboard.'
                  + (f'<br>{mbtn}' if manage else "") + '</div>')
    else:
        status = '<div class="status none">Create a free account first, then pick a membership.</div>'
    cards = chart_card = ""
    for key, label, price, per, url in plans:
        if key.startswith("chart"):
            if not user:
                cbtn = '<a class="go" href="/signup">Create account</a>'
            elif url:
                cbtn = f'<a class="go" href="{E(url)}">Join Chart Only</a>'
            else:
                cbtn = '<span class="go off">Checkout opening soon</span>'
            chart_card = (f'<h2 class="co-h">Just the charts</h2><div class="grid"><div class="plan co">'
                          f'<div class="nm">CHART ONLY &middot; 3.5 MONTHS</div><div class="px">{E(price)}</div>'
                          f'<div class="per">{E(per)}</div>'
                          + "<ul>" + "".join(f"<li>{E(x)}</li>" for x in CHART_FEATURES) + "</ul>" + cbtn + "</div></div>")
            continue
        best = key == "105d"
        if not user:
            btn = '<a class="go" href="/signup">Create account</a>'
        elif url:
            btn = f'<a class="go" href="{E(url)}">Join for {E(label)}</a>'
        else:
            btn = '<span class="go off">Checkout opening soon</span>'
        cards += (f'<div class="plan{" best" if best else ""}">' + ('<span class="tagb">BEST VALUE</span>' if best else "")
                  + f'<div class="nm">{E(label.upper())}</div><div class="px">{E(price)}</div><div class="per">{E(per)}</div>'
                  + "<ul>" + "".join(f"<li>{E(x)}</li>" for x in PLAN_FEATURES) + "</ul>" + btn + "</div>")
    body = ((app_tabs(user, "pricing") if user else
             '<div class="top" style="padding:10px 16px"><a class="brand" href="/">' + brain_logo(34, "p") + '<b>BRAIN</b></a></div>')
            + '<div class="pr"><h1>Get BRAIN</h1><p class="lead">Live market intelligence for 15-minute BTC and XRP rounds.</p>'
            + status + '<p class="renew-note">Memberships renew automatically at the same price, so your access never lapses. '
              'Turn auto-renew off any time with one tap - you keep everything you already paid for.</p>'
            + f'<div class="grid">{cards}</div>{chart_card}'
            + '<p class="fine">Paid securely through Stripe (cards, Apple Pay, Google Pay). Memberships renew automatically every 10 days, '
              '30 days or 3.5 months (105 days) at the price you joined at, until you turn auto-renew off on My Pass (Manage membership) - '
              'you keep access until the end of the time already paid for, and we email you 2 days before each renewal. '
              '<b>All sales are final, no refunds</b>, including renewals you didn\'t turn off in time. Accounts that misuse '
              'the service or put it at risk can be suspended or ended without a refund (see Terms). BRAIN is an information and '
              'data service: it gathers and shows what market data and its models are reading. Nothing here is financial advice, '
              'a recommendation, or an instruction to trade or use your money; readings can be wrong and trading can lose money. '
              '<a href="/terms" style="color:#e9a5bb">Terms</a> &middot; questions: support@brainswatch.com</p></div>')
    return page("Pricing - BRAIN", body, PRICING_CSS)


def kalshi_key_card(k):
    """Admin: where the owner puts their Kalshi API key for auto-buy. The key itself is never shown back."""
    if k.get("set") or k.get("env"):
        src = f'key ending <b>{E(k.get("key_tail") or "")}</b>' if k.get("set") else "key from the Railway settings"
        if k.get("error"):
            status = f'<div class="err">Saved, but the market didn\'t accept it just now ({src}): {E(k["error"])}</div>'
        else:
            bal = k.get("balance")
            status = (f'<div class="ok">Connected to the market - {src}'
                      + (f' &middot; balance <b>${bal:,.2f}</b>' if bal is not None else "") + '</div>')
    else:
        status = '<div class="err">No market key yet - auto-buy can\'t place orders until you add one.</div>'
    if not k.get("can_store", True):
        status += '<div class="err">The server needs a secret to encrypt the key: add KALSHI_CREDS_SECRET in Railway.</div>'
    remove = ('<form method="post" action="/admin" onsubmit="return confirm(\'Remove the market key? Auto-buy will switch off.\')">'
              '<button class="b no" name="a" value="kalshi_remove">Remove key</button></form>') if k.get("set") else ""
    return ('<section class="card"><h3>MARKET API KEY (AUTO-BUY)</h3>' + status
            + '<p class="mute small">On the market site: Account &amp; security &rarr; API keys &rarr; Create key. Copy the Key ID and download the '
              'private key file, open it in a text editor and paste everything below, including the BEGIN and END lines. '
              'BRAIN checks it with the market, then stores it encrypted on the server. It is never shown again.</p>'
            + '<form method="post" action="/admin" autocomplete="off">'
              '<label class="mute small" for="kk-id">API key ID</label>'
              '<input id="kk-id" name="key_id" required autocomplete="off" spellcheck="false" placeholder="e.g. a1b2c3d4-...">'
              '<label class="mute small" for="kk-pem" style="display:block;margin-top:8px">Private key</label>'
              '<textarea id="kk-pem" name="pem" required rows="6" spellcheck="false" autocomplete="off" '
              'placeholder="-----BEGIN RSA PRIVATE KEY-----" style="font-family:ui-monospace,Menlo,monospace;font-size:12px"></textarea>'
              '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">'
              '<button class="b ok" name="a" value="kalshi_save">' + ("Replace key" if k.get("set") else "Save &amp; test key") + '</button>'
              '</div></form>' + remove + '</section>')


# ------------------------------------------------------------------------------------------------ how to use
GUIDE = [
    ("The basics", [
        ("What BRAIN does", "Every 15 minutes there's a new round: will the price finish above or below the round's line? "
         "BRAIN gives you its read on each round."),
        ("The line", "The target price for the round. Above it at the end = UP. Below it = DOWN."),
        ("Time until call", "A countdown to BRAIN's next call."),
    ]),
    ("The calls", [
        ("Early call", "BRAIN's first read, partway into the round. Things can still change."),
        ("Sealed call", "BRAIN's main call. Once it's sealed it never changes. This is the one the streak counts."),
        ("SUPER / GOOD / WEAK", "How confident the call is. SUPER is the strongest, WEAK is the least sure."),
        ("↺ Reversal", "A bolder call on the side that's behind right now. Bigger payout, more risk."),
        ("★ Setup", "This call matches a setup that has done well before."),
    ]),
    ("The tiles", [
        ("Flip Radar", "How likely the call is to flip before the round ends. LOW is calm, CRITICAL means it's in trouble."),
        ("RSI", "Shows if price has run up or dropped a lot very fast. Big moves like that often cool off."),
        ("Line crosses", "How many times price has crossed the line this round. More crosses = a choppier, harder round."),
        ("Streak", "Sealed-call wins or losses in a row."),
        ("Win-rate badge", "Your win rate and streak. Tap it to see every past round."),
        ("Buy pressure", "Whether buyers or sellers are more active right now."),
        ("Market row", "White = the market agrees with the call. Black = the market disagrees."),
    ]),
    ("Alerts", [
        ("Whale", "Someone just made a very large trade."),
        ("Wall moved / pulled", "A large waiting order was moved or removed. Big orders moving around can push price."),
        ("Fake breakout", "Price jumped past a recent high or low and quickly came back."),
    ]),
    ("Good habits", [
        ("Start small", "Learn how the calls behave before you put real money behind them."),
        ("Trust the strong calls more", "SUPER and GOOD calls are BRAIN's most confident. Be careful with WEAK and Reversal."),
        ("Nothing is certain", "Any round can flip at the last second. BRAIN is for information and education only - not financial advice."),
    ]),
]

GUIDE_CSS = r"""
.guide{max-width:820px;margin:0 auto;padding:12px 16px 50px;font-family:Carlito,Calibri,'Segoe UI',sans-serif}
.guide h2{font:700 12px Montserrat,Arial,sans-serif;color:#dcbb91;letter-spacing:1.6px;margin:24px 0 8px}
.guide .it{background:rgba(56,45,50,.85);border:1px solid rgba(240,214,200,.14);border-radius:14px;padding:11px 13px;margin:8px 0}
.guide .it b{display:block;color:#fbf4ec;font-size:15px;margin-bottom:2px}.guide .it span{color:#e2d4c9}
"""


def guide_html(user):
    out = [app_tabs(user, "guide"), '<div class="guide"><h1 style="font-family:Fraunces,Georgia,serif;font-weight:700;'
           'color:#fbf4ec;margin:6px 0 2px">How to use BRAIN</h1><p class="mute">Everything on the screen, in plain words.</p>']
    for sec, items in GUIDE:
        out.append(f'<h2>{E(sec).upper()}</h2>')
        out += [f'<div class="it"><b>{E(t)}</b><span>{E(d)}</span></div>' for t, d in items]
    out.append('</div>')
    return page("How to use - BRAIN", "".join(out), GUIDE_CSS)


TERMS = [
    ("What BRAIN is: an information and data service", "BRAIN is an automated information service. Its software gathers "
     "public market data (prices, trades, order books, prediction-market prices and similar), watches it, and shows what that data "
     "and BRAIN's own models are reading - charts, statistics, model estimates, labels and alerts. That is all BRAIN does: it "
     "collects, measures and displays information, for informational and educational purposes."),
    ("Not financial advice. No recommendations. No instructions.", "Nothing on BRAIN is financial, investment, trading, legal "
     "or tax advice, and nothing is a recommendation, solicitation, offer or instruction to buy, sell, hold or trade anything, or "
     "to put money anywhere. No one is advised, recommended or told to follow any call, alert or reading, or to do anything with "
     "their actual money. BRAIN does not know your finances, goals or risk tolerance and gives no advice suited to you."),
    ("What the words on screen mean", "Calls (\"early\", \"sealed\", \"late\"), directions (UP / DOWN), confidence tiers "
     "(SUPER / GOOD / WEAK), percentages, flip warnings, badges such as HOLD or REVERSAL, \"cash out\" and \"take profit\" "
     "notes, whale and Trader Radar alerts, win rates, backtests and the $100-a-trade examples are labels for what the data and "
     "models show at that moment. They describe market conditions; they are not instructions and not promises of any result. "
     "Hypothetical and backtested results are simulated, use past data, and do not reflect real trading."),
    ("No adviser relationship", "BRAIN, its owner and staff are not registered investment advisers, commodity trading advisors, "
     "brokers, dealers, financial planners or fiduciaries, and using BRAIN does not create any adviser, client or fiduciary "
     "relationship. BRAIN is not affiliated with, endorsed by or connected to any prediction market, index provider or exchange."),
    ("Your decisions, your risk", "Prediction markets and trading carry a high risk of loss, including losing everything you "
     "put in. Every decision to trade, how much, and when, is yours alone, made on your own judgment, and you are fully "
     "responsible for it and its results. Only trade money you can afford to lose. If you want advice, talk to a licensed "
     "professional. You must be 18 or older and allowed to use these markets where you live."),
    ("Accuracy and availability", "Data can be late, missing or wrong; models can be wrong; and the service can slow down, "
     "freeze or go offline without warning. Past results, streaks and win rates never predict future results. BRAIN and its "
     "owner are not responsible for any loss or damage from using, or relying on, anything shown here."),
    ("Memberships and payments", "The live dashboard needs a membership: 10 days ($65), 30 days ($165) or 3.5 months ($379); the Chart Only "
     "membership (live charts only) is 3.5 months ($35). Paid through Stripe. Memberships renew automatically at the same price at the end of each period until you turn auto-renew off (My Pass > Manage membership, any time before the renewal date); you keep access until the end of the time already paid for. We email you 2 days before each renewal. "
     "ALL SALES ARE FINAL: no refunds, including for unused time."),
    ("Suspension and termination", "BRAIN can suspend or end any account or membership at any time, at the owner's discretion, "
     "including for convenience. This covers, for example: misusing the site or the bot; sharing, reselling or copying what you "
     "see here; scraping or automating access; harassing, threatening or disrespecting the owner, staff, the bot or other members; "
     "anything that puts the service, its data or its systems at risk or could compromise them; or if BRAIN has to pause, change "
     "or stop operating. When an account or membership is suspended or ended for any of these reasons, access stops right away and "
     "NO REFUND is given, including for unused time, except where the law requires otherwise."),
    ("Access", "Keep your login private - one account per person. Don't share your account or copy and resell what you see here."),
    ("Your data", "We store your username, email, a scrambled (hashed) password and which devices are signed in, only to run "
     "your account. Ask the owner any time to delete your account."),
    ("Changes", "These terms can change. Using the site after a change means you accept the new terms."),
]


def terms_page():
    items = "".join(f'<div class="it"><b>{E(t)}</b><span>{E(d)}</span></div>' for t, d in TERMS)
    body = ('<div class="guide"><div class="top" style="padding:10px 0"><a class="brand" href="/">' + brain_logo(34, "t")
            + '<b>BRAIN</b></a></div><h1 style="font-family:Fraunces,Georgia,serif;font-weight:700;color:#fbf4ec;margin:6px 0 2px">'
            'Terms &amp; conditions</h1><p class="mute">Last updated October 22, 2026.</p>' + items
            + '<p style="margin-top:18px"><a class="btn cream" href="/">Back home</a></p></div>')
    return page("Terms - BRAIN", body, GUIDE_CSS)


# ================================================================== INFO CENTER (2026-10-24, user: "a useful links + video page called the
# Info Center, BRAIN themed - real accredited sites and YouTube that teach reading 15-min charts and candles, passive and active investing,
# options / puts / shorts / longs, free trading simulators, and BRAIN's favorite tools"). Public page, links only, nothing affiliated.
# Video links open a YouTube search for the topic + channel, so they never go dead when a single video is taken down.
def _yt(q):
    import urllib.parse as _u
    return "https://www.youtube.com/results?search_query=" + _u.quote_plus(q)


INFO_SECTIONS = [
    ("start", "Start here: how BRAIN's markets work", "The 15-minute UP / DOWN rounds BRAIN reads, straight from the source.", [
        ("Kalshi: crypto markets explained", "https://help.kalshi.com/markets/popular-markets/crypto-markets", "Kalshi Help Center",
         "How the 15-minute BTC and XRP up/down markets are set up and how they settle."),
        ("Kalshi market rules", "https://help.kalshi.com/en/articles/13823838-market-rules", "Kalshi Help Center",
         "The official rules: the line, close time and what counts as UP."),
        ("CF Benchmarks", "https://www.cfbenchmarks.com/", "CF Benchmarks",
         "The regulated price indexes Kalshi's crypto rounds settle on - the 'real' price BRAIN tracks."),
        ("CFTC: learn and protect", "https://www.cftc.gov/LearnAndProtect", "U.S. CFTC",
         "The federal regulator for event contracts and futures - plain-English guides and fraud alerts."),
        ("Kalshi responsible trading hub", "https://help.kalshi.com/en/articles/13823838-responsible-trading-hub", "Kalshi Help Center",
         "Deposit limits, cool-offs and self-exclusion tools."),
    ]),
    ("candles", "Reading candles and 15-minute charts", "What every candle on BRAIN's charts is telling you, and how to read UP vs DOWN.", [
        ("What is a Japanese candlestick?", "https://www.babypips.com/learn/forex/what-is-a-japanese-candlestick", "BabyPips School of Pipsology",
         "Open, high, low, close and the wick in one picture - the best free first lesson."),
        ("Summary of candlestick patterns", "https://www.babypips.com/learn/forex/summary-of-candlesticks", "BabyPips",
         "Hammers, dojis, engulfing candles and what they suggest about buyers vs sellers."),
        ("Candlestick charting", "https://www.investopedia.com/trading/candlestick-charting-what-is-it/", "Investopedia",
         "Reference guide to candle anatomy and the classic reversal and continuation patterns."),
        ("TradingView: free live charts", "https://www.tradingview.com/", "TradingView",
         "The charting site behind BRAIN's charts. Switch to 1m / 5m / 15m and add RSI to practice."),
        ("TradingView ideas and education", "https://www.tradingview.com/education/", "TradingView",
         "Free community lessons on support, resistance, trend lines and indicators."),
    ]),
    ("signals", "The signals on BRAIN, explained", "Each reading on the Analysis page, and a place to learn it properly.", [
        ("RSI (Relative Strength Index)", "https://www.investopedia.com/terms/r/rsi.asp", "Investopedia",
         "BRAIN's RSI box: above 70 is stretched up, below 30 stretched down."),
        ("Support and resistance", "https://www.investopedia.com/trading/support-and-resistance-basics/", "Investopedia",
         "Why price bounces off the same levels - the idea behind line crosses and walls."),
        ("Order book and market depth", "https://www.investopedia.com/terms/o/order-book.asp", "Investopedia",
         "Bids, asks and the 'walls' BRAIN flags near the price."),
        ("Liquidity and fair value gaps", _yt("fair value gap liquidity sweep explained beginner"), "YouTube",
         "Videos on the sweep and gap structure BRAIN reads on 1m-1d charts."),
        ("Bid-ask spread and fees", "https://www.investopedia.com/terms/b/bid-askspread.asp", "Investopedia",
         "Why winning more often isn't the same as making money once the spread and fees are counted."),
    ]),
    ("passive", "Passive investing (long-term, set-and-forget)", "Slow, boring and historically the most reliable way to build wealth.", [
        ("Investor.gov: investing basics", "https://www.investor.gov/introduction-investing", "U.S. SEC",
         "The SEC's free starter course: stocks, bonds, funds, risk and compounding."),
        ("Bogleheads wiki", "https://www.bogleheads.org/wiki/Main_Page", "Bogleheads",
         "Low-cost index funds, the three-fund portfolio and how to start."),
        ("FINRA: investing for everyone", "https://www.finra.org/investors", "FINRA",
         "Fund fees, broker checks and tools from the industry regulator."),
        ("Khan Academy: finance and capital markets", "https://www.khanacademy.org/economics-finance-domain/core-finance", "Khan Academy",
         "Free video course on interest, stocks, bonds and how markets price risk."),
        ("Ben Felix: Common Sense Investing", _yt("Ben Felix Common Sense Investing index funds"), "YouTube",
         "Evidence-based videos on index investing from a portfolio manager."),
    ]),
    ("active", "Active trading: longs, shorts, options, puts and calls", "How traders bet on direction - and what each one can cost you.", [
        ("Options Industry Council", "https://www.optionseducation.org/", "OIC (from OCC, the options clearinghouse)",
         "The industry's free, unbiased options school: calls, puts, strategies, risk."),
        ("Options strategies quick guide", "https://www.optionseducation.org/landingpages-options-strategy-quick-guide", "OIC",
         "One page of common strategies with their max gain and max loss."),
        ("Investor bulletin: short sales", "https://www.investor.gov/additional-resources/news-alerts/alerts-bulletins/investor-bulletin-introduction-short-sales", "U.S. SEC",
         "How shorting works, borrowing costs and why losses can be unlimited."),
        ("Short selling, defined", "https://www.investor.gov/introduction-investing/investing-basics/glossary/short-selling", "U.S. SEC",
         "The plain-English glossary entry."),
        ("Long vs short positions", "https://www.investopedia.com/ask/answers/100314/whats-difference-between-long-and-short-position-market.asp", "Investopedia",
         "Being long (betting up) vs short (betting down) in one read."),
        ("tastylive: options and futures", _yt("tastylive options basics calls puts"), "YouTube (tastylive)",
         "Free daily shows that teach options from the ground up."),
    ]),
    ("sims", "Free trading simulators (practice with fake money)", "Test an idea for weeks before risking a dollar - the way BRAIN backtests.", [
        ("Webull paper trading", "https://www.webull.com/paper-trading", "Webull",
         "Free fake-money account with stocks, ETFs and options on the real app."),
        ("Investopedia stock simulator", "https://www.investopedia.com/simulator/", "Investopedia",
         "Free browser simulator with $100k of play money and games you can join."),
        ("thinkorswim paperMoney", "https://www.schwab.com/trading/thinkorswim", "Charles Schwab",
         "Pro-level charts and options tools with a paper-trading mode."),
        ("TradingView paper trading", "https://www.tradingview.com/", "TradingView",
         "Practice orders right on the chart from the trading panel."),
    ]),
    ("videos", "Video school", "Hand-picked topics and channels. Each link opens fresh YouTube results so it never goes stale.", [
        ("How to read candlestick charts", _yt("how to read candlestick charts for beginners"), "YouTube", "Start here if candles are new."),
        ("Trading 15-minute and 1-minute charts", _yt("how to read 1 minute 15 minute chart trend scalping beginner"), "YouTube",
         "Short-timeframe trend, momentum and when NOT to trade."),
        ("Rayner Teo: price action", _yt("Rayner Teo price action candlestick"), "YouTube", "Clear lessons on trend, support and resistance."),
        ("The Plain Bagel: investing explained", _yt("The Plain Bagel investing explained"), "YouTube", "Honest, jargon-free finance from a CFA."),
        ("Khan Academy: options, calls and puts", _yt("Khan Academy call option put option"), "YouTube", "The math of options, step by step."),
        ("Prediction markets explained", _yt("how prediction markets work Kalshi explained"), "YouTube", "How event contracts like BRAIN's rounds are priced."),
    ]),
    ("favorites", "BRAIN's favorites", "The tools we'd keep open next to BRAIN. Not sponsored, not affiliated.", [
        ("TradingView", "https://www.tradingview.com/", "Charts", "Best free charting anywhere."),
        ("Kalshi", "https://kalshi.com/", "CFTC-regulated exchange", "Where the 15-minute rounds BRAIN reads are listed."),
        ("Webull", "https://www.webull.com/", "Brokerage + paper trading", "Free paper trading and clean charts on mobile."),
        ("CoinGecko", "https://www.coingecko.com/", "Crypto data", "Prices, volume and market caps across exchanges."),
        ("Investopedia dictionary", "https://www.investopedia.com/financial-term-dictionary-4769738", "Reference", "Look up any term on BRAIN."),
    ]),
    ("help", "Play it safe", "Real money deserves real limits.", [
        ("FINRA BrokerCheck", "https://brokercheck.finra.org/", "FINRA", "Check any broker or advisor before you trust them."),
        ("SEC fraud alerts", "https://www.investor.gov/protect-your-investments/fraud", "U.S. SEC", "Spot pump-and-dumps, fake gurus and crypto scams."),
        ("National Council on Problem Gambling", "https://www.ncpgambling.org/", "NCPG", "Free, confidential help 24/7 - call or text 1-800-GAMBLER."),
    ]),
]

# ---- Info Center art (2026-10-24, user: "vector art that describes stuff, a nice art style that matches BRAIN, a background image,
# video thumbnails, artsy and high quality"). Flat-vector, the same dusk palette as the hero (static/hero.*): night ink, rose and tan
# brain halves, teal-up / pink-down candles, gold sparkle. Everything is inline SVG - no extra requests, sharp at any size.
_C = {"ink": "#1a1416", "panel": "#2a2f33", "panel2": "#1f2427", "grid": "#3a4247", "up": "#43cdb7", "down": "#e8798f",
      "rose": "#e9a5bb", "tan": "#dcbb91", "gold": "#e5b85c", "cream": "#fbf4ec", "sky": "#2c3446", "dusk": "#c99aa3"}


def _cand(x, o, c, w=7, wick=4):
    up = c < o                               # svg y grows down: close above open = up
    top, bot = min(o, c), max(o, c)
    col = _C["up"] if up else _C["down"]
    return (f'<line x1="{x + w / 2}" y1="{top - wick}" x2="{x + w / 2}" y2="{bot + wick}" stroke="{col}" stroke-width="1.6"/>'
            f'<rect x="{x}" y="{top}" width="{w}" height="{max(2, bot - top)}" rx="1.2" fill="{col}"/>')


def _monitor(inner, w=160, h=100, tag=True):
    """A little BRAIN desk monitor (same as the three screens in the hero)."""
    return (f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="9" fill="{_C["panel2"]}" stroke="#0e1113" stroke-width="3"/>'
            + "".join(f'<line x1="10" y1="{y}" x2="{w - 10}" y2="{y}" stroke="{_C["grid"]}" stroke-width=".7" opacity=".7"/>'
                      for y in range(22, h - 6, 16))
            + (f'<rect x="12" y="9" width="26" height="3.5" rx="1.7" fill="{_C["rose"]}"/>'
               f'<rect x="{w - 34}" y="9" width="22" height="3.5" rx="1.7" fill="{_C["up"]}"/>' if tag else "") + inner)


def _sparkle(x, y, r=6, col=None):
    col = col or _C["gold"]
    return (f'<path d="M{x} {y - r}Q{x + r * .18} {y - r * .18} {x + r} {y}Q{x + r * .18} {y + r * .18} {x} {y + r}'
            f'Q{x - r * .18} {y + r * .18} {x - r} {y}Q{x - r * .18} {y - r * .18} {x} {y - r}Z" fill="{col}"/>')


def _brain(x, y, s=1.0):
    """The two-tone BRAIN (rose + tan halves) - tiny mascot for the art."""
    return (f'<g transform="translate({x} {y}) scale({s})">'
            f'<path d="M0 -14C-4 -18 -12 -17 -13 -11C-19 -10 -20 -2 -16 1C-19 6 -15 12 -9 11C-7 15 -2 15 0 13Z" fill="{_C["rose"]}"/>'
            f'<path d="M0 -14C4 -18 12 -17 13 -11C19 -10 20 -2 16 1C19 6 15 12 9 11C7 15 2 15 0 13Z" fill="{_C["tan"]}"/>'
            f'<line x1="0" y1="-14" x2="0" y2="13" stroke="#6b4a52" stroke-width="1.2"/>'
            f'<path d="M-10 -5q3 -2 6 0M-9 4q3 -2 6 0M4 -5q3 -2 6 0M3 4q3 -2 6 0" stroke="#fff" stroke-width="1.2" fill="none" opacity=".85"/></g>')


def _svg(w, h, body, cls=""):
    return f'<svg class="{cls}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">{body}</svg>'


def _art_start():         # an event contract: YES / NO with the line
    b = _monitor(
        f'<line x1="14" y1="58" x2="146" y2="58" stroke="{_C["cream"]}" stroke-width="1.3" stroke-dasharray="4 3" opacity=".8"/>'
        f'<path d="M14 72 L40 66 L58 70 L76 52 L96 56 L116 40 L146 34" stroke="{_C["gold"]}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
        f'<circle cx="146" cy="34" r="4" fill="{_C["gold"]}"/>'
        f'<rect x="16" y="22" width="34" height="14" rx="7" fill="{_C["up"]}"/><text x="33" y="32.5" font-size="9" font-weight="800" text-anchor="middle" fill="{_C["ink"]}" font-family="Arial">YES</text>'
        f'<rect x="56" y="22" width="34" height="14" rx="7" fill="{_C["down"]}"/><text x="73" y="32.5" font-size="9" font-weight="800" text-anchor="middle" fill="{_C["ink"]}" font-family="Arial">NO</text>'
        f'<text x="140" y="70" font-size="8" fill="{_C["cream"]}" font-family="Arial" text-anchor="end" opacity=".8">line</text>')
    return _svg(160, 100, b + _sparkle(130, 24, 5))


def _art_candles():
    cs = [(14, 70, 60), (25, 60, 66), (36, 66, 50), (47, 50, 44), (58, 44, 54), (69, 54, 40), (80, 40, 30), (91, 30, 38),
          (102, 38, 26), (113, 26, 32), (124, 32, 22), (135, 22, 28)]
    b = _monitor("".join(_cand(x, o, c) for x, o, c in cs)
                 + f'<path d="M17 66 Q50 58 70 48 T140 26" stroke="{_C["gold"]}" stroke-width="1.6" fill="none" opacity=".9"/>')
    # magnified candle callout
    b += (f'<g transform="translate(118 50)"><circle r="20" fill="{_C["ink"]}" stroke="{_C["cream"]}" stroke-width="1.5" opacity=".95"/>'
          f'<line x1="0" y1="-14" x2="0" y2="14" stroke="{_C["up"]}" stroke-width="2"/><rect x="-5" y="-7" width="10" height="13" rx="2" fill="{_C["up"]}"/>'
          f'<text x="9" y="-9" font-size="5.5" fill="{_C["cream"]}" font-family="Arial">high</text><text x="9" y="15" font-size="5.5" fill="{_C["cream"]}" font-family="Arial">low</text></g>')
    return _svg(160, 100, b)


def _art_signals():       # RSI gauge + walls
    b = _monitor(
        f'<path d="M30 76 A34 34 0 0 1 98 76" stroke="{_C["grid"]}" stroke-width="8" fill="none" stroke-linecap="round"/>'
        f'<path d="M30 76 A34 34 0 0 1 52 45" stroke="{_C["up"]}" stroke-width="8" fill="none" stroke-linecap="round"/>'
        f'<path d="M76 45 A34 34 0 0 1 98 76" stroke="{_C["down"]}" stroke-width="8" fill="none" stroke-linecap="round"/>'
        f'<line x1="64" y1="76" x2="80" y2="50" stroke="{_C["gold"]}" stroke-width="3" stroke-linecap="round"/><circle cx="64" cy="76" r="4.5" fill="{_C["gold"]}"/>'
        f'<text x="64" y="92" font-size="9" font-weight="800" fill="{_C["cream"]}" font-family="Arial" text-anchor="middle">RSI 62</text>'
        + "".join(f'<rect x="{112 + i * 0}" y="{28 + i * 9}" width="{w}" height="6" rx="2" fill="{c}"/>'
                  for i, (w, c) in enumerate([(14, _C["down"]), (30, _C["down"]), (10, _C["down"]), (8, _C["up"]), (34, _C["up"]), (16, _C["up"])])))
    return _svg(160, 100, b)


def _art_passive():       # a growing tree of coins on a slow curve
    b = (f'<rect x="2" y="2" width="156" height="96" rx="12" fill="url(#gp)"/>'
         f'<defs><linearGradient id="gp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_C["sky"]}"/><stop offset="1" stop-color="#3a2c35"/></linearGradient></defs>'
         f'<path d="M10 86 C60 84 90 70 150 18" stroke="{_C["up"]}" stroke-width="2.6" fill="none" stroke-linecap="round" opacity=".9"/>'
         f'<path d="M10 86 C60 84 90 70 150 18 L150 96 L10 96Z" fill="{_C["up"]}" opacity=".12"/>'
         f'<rect x="54" y="58" width="5" height="30" rx="2" fill="#6b4a3a"/>'
         + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x, y, r, c in
                   [(56, 52, 15, "#2f6b5c"), (44, 58, 10, "#2f6b5c"), (68, 58, 10, "#2f6b5c"), (56, 44, 9, "#3c8a74")])
         + "".join(f'<circle cx="{x}" cy="{y}" r="3.2" fill="{_C["gold"]}" stroke="#8a6a2a" stroke-width=".8"/>' for x, y in [(50, 50), (62, 47), (57, 58), (46, 60), (66, 57)])
         + f'<text x="110" y="88" font-size="8" fill="{_C["cream"]}" font-family="Arial" opacity=".85">years &#8594;</text>' + _sparkle(140, 26, 5))
    return _svg(160, 100, b)


def _art_active():        # long vs short: bull arrow up, bear arrow down, option payoff hockey stick
    b = _monitor(
        f'<path d="M16 80 L40 56 L52 64 L76 30" stroke="{_C["up"]}" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M70 28 L78 28 L77 36" stroke="{_C["up"]}" stroke-width="3" fill="none" stroke-linecap="round"/>'
        f'<text x="20" y="34" font-size="9" font-weight="800" fill="{_C["up"]}" font-family="Arial">LONG</text>'
        f'<path d="M86 30 L104 50 L114 44 L140 78" stroke="{_C["down"]}" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M134 78 L141 79 L141 71" stroke="{_C["down"]}" stroke-width="3" fill="none" stroke-linecap="round"/>'
        f'<text x="108" y="34" font-size="9" font-weight="800" fill="{_C["down"]}" font-family="Arial">SHORT</text>'
        f'<path d="M60 88 L92 88 L118 66" stroke="{_C["gold"]}" stroke-width="1.8" fill="none" stroke-dasharray="3 2"/>'
        f'<text x="96" y="94" font-size="6.5" fill="{_C["gold"]}" font-family="Arial">call payoff</text>')
    return _svg(160, 100, b)


def _art_sims():          # play money + a controller-style practice screen
    b = _monitor(
        "".join(_cand(x, o, c, 6, 3) for x, o, c in [(16, 60, 52), (26, 52, 56), (36, 56, 46), (46, 46, 50), (56, 50, 40)])
        + f'<rect x="80" y="30" width="62" height="34" rx="6" fill="#2f5a4c" stroke="{_C["up"]}" stroke-width="1.2"/>'
          f'<circle cx="111" cy="47" r="10" fill="none" stroke="{_C["cream"]}" stroke-width="1.2" opacity=".8"/>'
          f'<text x="111" y="51" font-size="11" font-weight="800" fill="{_C["cream"]}" font-family="Arial" text-anchor="middle">$</text>'
          f'<text x="111" y="78" font-size="8" font-weight="800" fill="{_C["tan"]}" font-family="Arial" text-anchor="middle">PAPER $100K</text>'
          f'<rect x="18" y="72" width="22" height="10" rx="5" fill="{_C["up"]}"/><text x="29" y="79.5" font-size="6.5" font-weight="800" fill="{_C["ink"]}" font-family="Arial" text-anchor="middle">BUY</text>'
          f'<rect x="44" y="72" width="22" height="10" rx="5" fill="{_C["down"]}"/><text x="55" y="79.5" font-size="6.5" font-weight="800" fill="{_C["ink"]}" font-family="Arial" text-anchor="middle">SELL</text>')
    return _svg(160, 100, b)


def _art_videos():
    b = _monitor(f'<circle cx="80" cy="54" r="22" fill="{_C["rose"]}" opacity=".9"/><path d="M73 42 L93 54 L73 66Z" fill="{_C["ink"]}"/>'
                 f'<rect x="14" y="84" width="132" height="4" rx="2" fill="{_C["grid"]}"/><rect x="14" y="84" width="52" height="4" rx="2" fill="{_C["gold"]}"/>'
                 f'<circle cx="66" cy="86" r="4" fill="{_C["cream"]}"/>')
    return _svg(160, 100, b)


def _art_favorites():
    b = (f'<rect x="2" y="2" width="156" height="96" rx="12" fill="{_C["panel2"]}" stroke="#0e1113" stroke-width="3"/>'
         + _brain(80, 54, 1.9)
         + "".join(_sparkle(x, y, r) for x, y, r in [(32, 30, 7), (128, 28, 6), (40, 76, 4), (124, 74, 5), (80, 18, 4)])
         + f'<path d="M50 54 C30 40 30 70 50 54" stroke="{_C["up"]}" stroke-width="1" fill="none" opacity=".5"/>')
    return _svg(160, 100, b)


def _art_help():          # shield with check
    b = (f'<rect x="2" y="2" width="156" height="96" rx="12" fill="{_C["panel2"]}" stroke="#0e1113" stroke-width="3"/>'
         f'<path d="M80 16 L110 26 C110 58 98 76 80 86 C62 76 50 58 50 26Z" fill="#2f5a4c" stroke="{_C["up"]}" stroke-width="2.5"/>'
         f'<path d="M66 50 L77 61 L96 40" stroke="{_C["cream"]}" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
         + _sparkle(120, 30, 5) + _sparkle(40, 70, 4, _C["rose"]))
    return _svg(160, 100, b)


INFO_ART = {"start": _art_start, "candles": _art_candles, "signals": _art_signals, "passive": _art_passive, "active": _art_active,
            "sims": _art_sims, "videos": _art_videos, "favorites": _art_favorites, "help": _art_help}

# small glyphs for each card's corner (24 x 24)
_G = {
    "start": f'<path d="M3 14h18" stroke="{_C["cream"]}" stroke-dasharray="2 2"/><path d="M3 18 9 11l4 3 8-9" stroke="{_C["gold"]}" stroke-width="2" fill="none"/>',
    "candles": _cand(4, 16, 9, 5, 3) + _cand(10, 9, 13, 5, 3) + _cand(16, 13, 5, 5, 3),
    "signals": f'<path d="M4 18a8 8 0 0 1 16 0" stroke="{_C["up"]}" stroke-width="3" fill="none"/><path d="M12 18 16 11" stroke="{_C["gold"]}" stroke-width="2"/>',
    "passive": f'<path d="M3 20C10 19 15 14 21 4" stroke="{_C["up"]}" stroke-width="2.4" fill="none"/><circle cx="21" cy="4" r="2.5" fill="{_C["gold"]}"/>',
    "active": f'<path d="M3 17 9 9l4 4 8-9" stroke="{_C["up"]}" stroke-width="2.2" fill="none"/><path d="M3 7l6 6 4-2 8 9" stroke="{_C["down"]}" stroke-width="2.2" fill="none" opacity=".8"/>',
    "sims": f'<rect x="3" y="6" width="18" height="12" rx="3" fill="#2f5a4c" stroke="{_C["up"]}"/><text x="12" y="15.5" font-size="9" font-weight="800" fill="{_C["cream"]}" text-anchor="middle" font-family="Arial">$</text>',
    "videos": f'<circle cx="12" cy="12" r="9" fill="{_C["rose"]}"/><path d="M10 8l6 4-6 4z" fill="{_C["ink"]}"/>',
    "favorites": _sparkle(12, 12, 9),
    "help": f'<path d="M12 3l7 3c0 7-3 12-7 15-4-3-7-8-7-15z" fill="#2f5a4c" stroke="{_C["up"]}" stroke-width="1.5"/><path d="M8.5 12l2.5 2.5 4.5-5" stroke="{_C["cream"]}" stroke-width="2" fill="none"/>',
}

# video covers: each topic gets its own 16:9 illustrated thumbnail (the links open live YouTube results, so a fixed real thumbnail
# would misrepresent what opens - these covers describe the topic instead)
def _cover(kind, title):
    w, h = 320, 180
    sky = (f'<defs><linearGradient id="v{kind}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_C["sky"]}"/>'
           f'<stop offset=".7" stop-color="#4a3540"/><stop offset="1" stop-color="{_C["dusk"]}"/></linearGradient></defs>'
           f'<rect width="{w}" height="{h}" fill="url(#v{kind})"/>'
           + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" opacity="{o}"/>' for x, y, r, o in
                     [(30, 20, 1, .7), (80, 34, .8, .5), (150, 14, 1.1, .8), (210, 30, .8, .5), (270, 18, 1, .7), (300, 44, .8, .4), (120, 46, .7, .4)])
           + f'<path d="M0 150 C40 120 70 130 110 112 C150 96 180 118 220 104 C260 92 290 110 320 98 L320 180 L0 180Z" fill="#2c3d3a" opacity=".85"/>'
           + f'<path d="M0 164 C60 150 120 160 180 150 C240 142 280 152 320 146 L320 180 L0 180Z" fill="#1e2b29"/>')
    if kind == "candles":
        art = "".join(_cand(x, o, c, 12, 8) for x, o, c in
                      [(40, 110, 92), (60, 92, 100), (80, 100, 76), (100, 76, 84), (120, 84, 60), (140, 60, 70), (160, 70, 46), (180, 46, 56)])
    elif kind == "short":
        art = (f'<path d="M30 120 L70 100 L100 112 L140 80 L170 90 L200 60 L240 70 L280 40" stroke="{_C["gold"]}" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
               + "".join(f'<circle cx="{x}" cy="{y}" r="5" fill="{_C["cream"]}"/>' for x, y in [(140, 80), (200, 60), (280, 40)])
               + f'<text x="290" y="34" font-size="13" font-weight="800" fill="{_C["cream"]}" font-family="Arial" text-anchor="end">1m &middot; 15m</text>')
    elif kind == "levels":
        art = (f'<line x1="20" y1="60" x2="300" y2="60" stroke="{_C["down"]}" stroke-width="2" stroke-dasharray="8 5"/>'
               f'<line x1="20" y1="118" x2="300" y2="118" stroke="{_C["up"]}" stroke-width="2" stroke-dasharray="8 5"/>'
               f'<path d="M24 110 L60 66 L96 114 L132 64 L168 116 L204 62 L240 112 L276 66" stroke="{_C["cream"]}" stroke-width="3" fill="none" stroke-linejoin="round"/>'
               f'<text x="300" y="54" font-size="11" font-weight="800" fill="{_C["down"]}" font-family="Arial" text-anchor="end">RESISTANCE</text>'
               f'<text x="300" y="134" font-size="11" font-weight="800" fill="{_C["up"]}" font-family="Arial" text-anchor="end">SUPPORT</text>')
    elif kind == "bagel":
        art = (f'<circle cx="160" cy="88" r="40" fill="{_C["tan"]}"/><circle cx="160" cy="88" r="13" fill="#4a3540"/>'
               f'<path d="M128 74 q32 -18 64 0" stroke="#b38a5c" stroke-width="3" fill="none"/>'
               + "".join(f'<circle cx="{x}" cy="{y}" r="1.6" fill="{_C["cream"]}"/>' for x, y in [(140, 70), (152, 64), (170, 66), (182, 74), (146, 104), (176, 106)])
               + f'<rect x="220" y="60" width="60" height="50" rx="6" fill="{_C["panel2"]}"/><path d="M228 100 L246 86 L258 92 L274 70" stroke="{_C["up"]}" stroke-width="3" fill="none"/>')
    elif kind == "options":
        art = (f'<line x1="40" y1="120" x2="290" y2="120" stroke="{_C["cream"]}" stroke-width="1.5" opacity=".7"/>'
               f'<path d="M40 136 L170 136 L280 46" stroke="{_C["up"]}" stroke-width="4.5" fill="none" stroke-linejoin="round"/>'
               f'<path d="M40 46 L150 136 L280 136" stroke="{_C["down"]}" stroke-width="4.5" fill="none" stroke-linejoin="round" opacity=".85"/>'
               f'<text x="276" y="40" font-size="13" font-weight="800" fill="{_C["up"]}" font-family="Arial" text-anchor="end">CALL</text>'
               f'<text x="44" y="40" font-size="13" font-weight="800" fill="{_C["down"]}" font-family="Arial">PUT</text>')
    else:   # prediction markets
        art = (f'<rect x="70" y="58" width="80" height="70" rx="10" fill="{_C["up"]}"/><rect x="170" y="88" width="80" height="40" rx="10" fill="{_C["down"]}"/>'
               f'<text x="110" y="100" font-size="20" font-weight="900" fill="{_C["ink"]}" font-family="Arial" text-anchor="middle">YES</text>'
               f'<text x="210" y="114" font-size="20" font-weight="900" fill="{_C["ink"]}" font-family="Arial" text-anchor="middle">NO</text>'
               f'<text x="110" y="52" font-size="13" font-weight="800" fill="{_C["cream"]}" font-family="Arial" text-anchor="middle">68&cent;</text>'
               f'<text x="210" y="82" font-size="13" font-weight="800" fill="{_C["cream"]}" font-family="Arial" text-anchor="middle">32&cent;</text>')
    play = (f'<g transform="translate(286 150)"><circle r="17" fill="{_C["ink"]}" opacity=".85"/><path d="M-6 -9 L11 0 L-6 9Z" fill="{_C["rose"]}"/></g>')
    brainm = _brain(30, 150, 1.05)
    return _svg(w, h, sky + art + brainm + play + _sparkle(36, 30, 6), "cover")


_VIDEO_COVER = {"How to read candlestick charts": "candles", "Trading 15-minute and 1-minute charts": "short",
                "Rayner Teo: price action": "levels", "The Plain Bagel: investing explained": "bagel",
                "Khan Academy: options, calls and puts": "options", "Prediction markets explained": "prediction"}

INFO_CSS = r"""
body{background:#17121a;
  background-image:radial-gradient(1200px 600px at 85% -10%,rgba(233,165,187,.16),transparent 60%),
  radial-gradient(900px 500px at -10% 30%,rgba(67,205,183,.10),transparent 60%),
  radial-gradient(800px 600px at 50% 110%,rgba(229,184,92,.10),transparent 60%),
  linear-gradient(180deg,#1b1a26 0%,#211b1e 45%,#1a1416 100%);background-attachment:fixed}
.ic-stars{position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.55;
  background-image:radial-gradient(1.2px 1.2px at 12% 18%,#fff,transparent),radial-gradient(1px 1px at 28% 8%,#fff,transparent),
  radial-gradient(1px 1px at 46% 22%,#fff,transparent),radial-gradient(1.4px 1.4px at 63% 12%,#fff,transparent),
  radial-gradient(1px 1px at 78% 28%,#fff,transparent),radial-gradient(1.2px 1.2px at 91% 9%,#fff,transparent),
  radial-gradient(1px 1px at 8% 44%,#fff,transparent),radial-gradient(1px 1px at 36% 52%,#fff,transparent),
  radial-gradient(1.1px 1.1px at 70% 48%,#fff,transparent),radial-gradient(1px 1px at 88% 62%,#fff,transparent),
  radial-gradient(1px 1px at 20% 78%,#fff,transparent),radial-gradient(1.2px 1.2px at 55% 84%,#fff,transparent)}
.ic-fire{position:fixed;width:4px;height:4px;border-radius:50%;background:#e5b85c;box-shadow:0 0 10px 3px rgba(229,184,92,.55);
  pointer-events:none;z-index:0;opacity:0;animation:icFloat 9s ease-in-out infinite}
@keyframes icFloat{0%{opacity:0;transform:translateY(0)}20%{opacity:.9}80%{opacity:.6}100%{opacity:0;transform:translateY(-120px) translateX(20px)}}
@media (prefers-reduced-motion:reduce){.ic-fire{display:none}}
.ic{position:relative;z-index:1;max-width:1120px;margin:0 auto;padding:10px 16px 70px;font-family:var(--sans)}
.ic-hero{position:relative;border-radius:26px;overflow:hidden;min-height:330px;display:flex;align-items:flex-end;
  border:1px solid rgba(240,214,200,.16);box-shadow:0 30px 80px rgba(0,0,0,.45);margin-top:6px}
.ic-hero picture,.ic-hero img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 62%}
.ic-hero:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(23,18,26,.05) 0%,rgba(23,18,26,.35) 45%,rgba(23,18,26,.93) 100%)}
.ic-hero .txt{position:relative;z-index:1;padding:26px 26px 22px}
.ic-hero .kick{font:800 11px Montserrat,Arial,sans-serif;letter-spacing:2.4px;color:var(--gold);text-transform:uppercase}
.ic-hero h1{font-family:var(--serif);font-weight:700;color:var(--cream);margin:4px 0 6px;font-size:46px;line-height:1.02;
  font-variation-settings:"SOFT" 100;text-shadow:0 4px 30px rgba(0,0,0,.6)}
.ic-hero h1 em{font-style:normal;background:linear-gradient(90deg,#f7bfd2,#f0d3a8);-webkit-background-clip:text;background-clip:text;color:transparent}
.ic-hero p{margin:0;color:#efe3d8;max-width:560px;font-size:16px}
.ic-jump{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 4px;position:sticky;top:0;z-index:4;padding:10px 0;
  background:linear-gradient(180deg,rgba(23,18,26,.92),rgba(23,18,26,.75));backdrop-filter:blur(8px)}
.ic-jump a{display:inline-flex;align-items:center;gap:6px;font:700 11.5px Montserrat,Arial,sans-serif;letter-spacing:.6px;text-decoration:none;color:var(--tan);
  border:1px solid rgba(220,187,145,.32);border-radius:999px;padding:6px 12px 6px 8px;background:rgba(48,38,43,.7)}
.ic-jump a svg{width:16px;height:16px}
.ic-jump a:hover{background:rgba(233,165,187,.16);color:var(--cream);border-color:var(--rose)}
.ic-sec{margin-top:34px;scroll-margin-top:64px}
.ic-head{display:grid;grid-template-columns:200px 1fr;gap:20px;align-items:center;margin-bottom:14px}
.ic-head .art{width:200px;filter:drop-shadow(0 14px 26px rgba(0,0,0,.45))}
.ic-head .art svg{width:100%;height:auto;display:block}
.ic-head h2{font-family:var(--serif);font-weight:700;color:var(--cream);font-size:26px;margin:0 0 4px;line-height:1.1}
.ic-head .n{font:800 11px Montserrat,Arial,sans-serif;letter-spacing:2px;color:var(--rose)}
.ic-head .sub{color:var(--mute);font-size:15px;margin:0}
.ic-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.ic-card{position:relative;display:flex;gap:12px;text-decoration:none;background:linear-gradient(160deg,rgba(56,45,50,.92),rgba(36,30,34,.92));
  border:1px solid rgba(240,214,200,.13);border-radius:16px;padding:14px 14px 13px;transition:border-color .18s,transform .18s,box-shadow .18s;overflow:hidden}
.ic-card:before{content:"";position:absolute;inset:0 0 auto 0;height:2px;background:linear-gradient(90deg,var(--rose),var(--tan),var(--up));opacity:0;transition:opacity .18s}
.ic-card:hover{border-color:rgba(233,165,187,.55);transform:translateY(-2px);box-shadow:0 14px 30px rgba(0,0,0,.35)}
.ic-card:hover:before{opacity:1}
.ic-card .g{flex:0 0 36px;height:36px;border-radius:11px;background:rgba(20,15,18,.65);display:grid;place-items:center;border:1px solid rgba(240,214,200,.1)}
.ic-card .g svg{width:24px;height:24px}
.ic-card b{display:block;color:var(--cream);font-size:15.5px;line-height:1.25}
.ic-card .src{display:inline-block;font:800 9.5px Montserrat,Arial,sans-serif;letter-spacing:1px;color:var(--up);margin:4px 0 5px;text-transform:uppercase}
.ic-card .src.yt{color:#ff8f8f}
.ic-card span.d{display:block;color:#e2d4c9;font-size:13.5px;line-height:1.42}
.ic-card .go{position:absolute;right:12px;top:12px;color:var(--mute);font-size:13px;opacity:.6}
.ic-vgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.ic-vid{display:block;text-decoration:none;border-radius:16px;overflow:hidden;background:rgba(36,30,34,.95);border:1px solid rgba(240,214,200,.13);
  transition:transform .18s,box-shadow .18s,border-color .18s}
.ic-vid:hover{transform:translateY(-3px);box-shadow:0 18px 36px rgba(0,0,0,.45);border-color:rgba(233,165,187,.55)}
.ic-vid svg.cover{display:block;width:100%;height:auto;aspect-ratio:16/9}
.ic-vid .meta{padding:11px 14px 13px}
.ic-vid b{display:block;color:var(--cream);font-size:15.5px}
.ic-vid span{display:block;color:#e2d4c9;font-size:13.5px;margin-top:2px}
.ic-fav .ic-card{border-color:rgba(229,184,92,.42);background:linear-gradient(160deg,rgba(70,56,40,.85),rgba(36,30,34,.92))}
.ic-note{margin-top:40px;padding:16px 18px;border-radius:18px;border:1px dashed rgba(240,214,200,.25);color:var(--mute);font-size:13.5px;
  display:flex;gap:14px;align-items:center;background:rgba(20,15,18,.45)}
.ic-note svg{flex:0 0 46px;width:46px;height:46px}
@media(max-width:640px){.ic-jump{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin-left:-16px;margin-right:-16px;padding:10px 16px}
  .ic-jump::-webkit-scrollbar{display:none}.ic-jump a{flex:0 0 auto}
  .ic-hero{min-height:260px;border-radius:20px}.ic-hero h1{font-size:34px}.ic-hero .txt{padding:18px}
  .ic-head{grid-template-columns:110px 1fr;gap:12px}.ic-head .art{width:110px}.ic-head h2{font-size:21px}
  .ic-grid,.ic-vgrid{grid-template-columns:1fr}}
"""


def info_center_page(user=None):
    jump = "".join(f'<a href="#{k}">{_svg(24, 24, _G[k])}{E(t.split(":")[0].split("(")[0].strip())}</a>' for k, t, _s, _i in INFO_SECTIONS)
    secs = []
    for n, (key, title, sub, items) in enumerate(INFO_SECTIONS, 1):
        if key == "videos":
            grid = '<div class="ic-vgrid">' + "".join(
                f'<a class="ic-vid" href="{E(u)}" target="_blank" rel="noopener noreferrer">{_cover(_VIDEO_COVER.get(nm, "prediction"), nm)}'
                f'<div class="meta"><b>{E(nm)}</b><span>{E(d)}</span></div></a>' for nm, u, _src, d in items) + '</div>'
        else:
            grid = '<div class="ic-grid">' + "".join(
                f'<a class="ic-card" href="{E(u)}" target="_blank" rel="noopener noreferrer"><span class="g">{_svg(24, 24, _G[key])}</span>'
                f'<span><b>{E(nm)}</b><span class="src{" yt" if "youtube.com" in u else ""}">{"&#9654; " if "youtube.com" in u else ""}{E(src)}</span>'
                f'<span class="d">{E(d)}</span></span><span class="go">&#8599;</span></a>' for nm, u, src, d in items) + '</div>'
        secs.append(f'<section class="ic-sec{" ic-fav" if key == "favorites" else ""}" id="{key}"><div class="ic-head">'
                    f'<div class="art">{INFO_ART[key]()}</div><div><div class="n">{n:02d} &middot; {len(items)} LINKS</div>'
                    f'<h2>{E(title)}</h2><p class="sub">{E(sub)}</p></div></div>{grid}</section>')
    tabs = app_tabs(user, "info") if user else (
        '<div class="top"><a class="brand" href="/">' + brain_logo(34, "t") + '<b>BRAIN</b></a>'
        '<a class="btn pink" style="padding:8px 16px;font-size:13px" href="/pricing">Get BRAIN</a></div>')
    fire = "".join(f'<i class="ic-fire" style="left:{x}%;top:{y}%;animation-delay:{dl}s"></i>' for x, y, dl in
                   [(8, 70, 0), (22, 85, 2.5), (40, 75, 5), (61, 88, 1.2), (78, 72, 3.8), (92, 82, 6.3), (15, 40, 4.4), (85, 35, 7.1)])
    body = ('<div class="ic-stars"></div>' + fire + tabs + '<div class="ic"><div class="ic-hero">' + hero_img("pic")
            + '<div class="txt"><div class="kick">BRAIN &middot; Info Center</div><h1>Learn the market <em>BRAIN reads</em></h1>'
              '<p>Free, trusted places to learn candles, 15-minute charts, investing and trading &mdash; hand-picked and sorted for you.</p></div></div>'
            f'<nav class="ic-jump" aria-label="Sections">{jump}</nav>' + "".join(secs)
            + '<div class="ic-note">' + _svg(48, 48, _brain(24, 26, 1.25))
            + '<span>Every link goes to an outside site BRAIN doesn&rsquo;t own or control, and none of them pay us. This page is for learning only '
              '&mdash; not financial advice. Trading and event contracts can lose money fast; practice on a simulator first and never trade money '
              'you can&rsquo;t afford to lose. <a href="/terms">Terms</a></span></div></div>')
    return page("Info Center - BRAIN", body, INFO_CSS)
