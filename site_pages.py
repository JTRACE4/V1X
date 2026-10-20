"""Welcome page, account pages, admin and the How-to-use guide for BRAIN (added 2026-10-20).
Plain HTML/CSS/JS strings - no build step. The island-town art is an original inline SVG (bold-outline cartoon look,
sunset 'vice city' palette) drawn for this page."""
import html as _html
import time

E = _html.escape

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght,SOFT@0,9..144,400..900,0..100;1,9..144,400..900,0..100&family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">')


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
--serif:'Fraunces',Georgia,'Times New Roman',serif;--sans:'Nunito',-apple-system,'Segoe UI',sans-serif;color-scheme:dark}
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


def page(title, body, extra_css="", extra_head="", scripts=""):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>{E(title)}</title><meta name="theme-color" content="#211b1e">'
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
  chart=LightweightCharts.createChart(el,{autoSize:true,layout:{background:{type:'solid',color:'rgba(20,15,18,0)'},textColor:'#bcaaa1',fontFamily:'Nunito'},
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
        cta = '<a class="btn pink" href="/app">Open BRAIN</a><a class="btn teal" href="/logout">Log out</a>'
        hello = f'<p>Welcome back, {E(user["username"])}.</p>'
    else:
        cta = '<a class="btn pink" href="/login">Log in</a><a class="btn teal" href="/signup">Sign up</a>'
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
        '<div class="strip"><span id="line">Round line --</span><span id="cd">round closes in --</span>'
        '<span id="avg">60s avg --</span><span id="hl">24h --</span></div></section>'
        '<aside class="side"><section class="card"><h3>Smart money habits</h3><div id="tips"></div></section>'
        '<section class="card"><h3>Fear &amp; Greed</h3><div id="fng"><span class="mute">loading...</span></div></section>'
        '<section class="card"><h3><span id="nm">BTC</span> news</h3><div class="news" id="news"><span class="mute">loading...</span></div></section>'
        '</aside></div></main>'
        '<footer>For informational and educational use only &middot; not financial advice &middot; '
        '<a href="/terms">Terms &amp; conditions</a></footer>')
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
.adm form{display:inline}.adm .b{padding:6px 12px;border-radius:999px;border:0;font-weight:800;cursor:pointer}
.b.ok{background:var(--up);color:var(--ink)}.b.no{background:var(--down);color:#fff}.b.n{background:#3a2e3c;color:var(--text)}
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
.guide h2{font:600 12px Nunito,sans-serif;color:#dcbb91;letter-spacing:1.6px;margin:24px 0 8px}
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
            + '<b>BRAIN</b></a></div><h1 style="font-family:Fraunces,Georgia,serif;font-weight:700;color:#fbf4ec;margin:6px 0 2px">'
            'Terms &amp; conditions</h1><p class="mute">Last updated October 20, 2026.</p>' + items
            + '<p style="margin-top:18px"><a class="btn cream" href="/">Back home</a></p></div>')
    return page("Terms - BRAIN", body, GUIDE_CSS)
