#!/usr/bin/env python3
"""CyberDeck: an offline arena shooter and a local, read-only Git dashboard.

Run: python3 cyberdeck.py [path/to/repository] [--port 8765] [--no-browser]
Only the Python standard library and the Git command-line program are used.
"""

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def run_git(folder, *args, optional=False):
    """Use argument lists, bounded execution time, and no shell interpolation."""
    result = subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.quotePath=false", "-C", str(folder), *args],
        capture_output=True, encoding="utf-8", errors="replace", timeout=12,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"},
    )
    if result.returncode and not optional:
        raise ValueError(result.stderr.strip() or "Git kon deze map niet uitlezen.")
    return result.stdout if result.returncode == 0 else ""


def repository_snapshot(folder):
    """Read real working-tree state, including staged changes and unborn HEAD."""
    if not shutil.which("git"):
        raise ValueError("Git is niet gevonden. Installeer Git en start CyberDeck opnieuw.")
    folder = Path(folder).expanduser().resolve()
    root = run_git(folder, "rev-parse", "--show-toplevel").strip()
    branch = run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD", optional=True).strip()
    head = run_git(root, "rev-parse", "--short", "HEAD", optional=True).strip()
    branch = branch or ("detached @ " + head if head else "nog geen commits")

    # NUL separators preserve filenames containing spaces, tabs, or newlines.
    records = iter(run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=normal").split("\0"))
    files = []
    for record in records:
        if not record:
            continue
        status, name = record[:2], record[3:]
        previous = next(records, "") if "R" in status or "C" in status else ""
        files.append({"status": status, "name": name, "previous": previous})

    log = run_git(root, "log", "-18", "--format=%h%x00%s%x00%an%x00%ar", optional=True)
    commits = []
    for line in log.splitlines():
        parts = line.split("\0", 3)
        if len(parts) == 4:
            commits.append(dict(zip(("hash", "subject", "author", "time"), parts)))

    def diff(staged=False):
        args = ["diff", "--no-ext-diff", "--no-textconv", "--no-color"]
        if staged:
            args.append("--cached")
        return run_git(root, *args, "--", optional=True)[:120000]

    return {
        "root": root, "name": Path(root).name, "branch": branch,
        "files": files, "commits": commits,
        "branches": run_git(root, "for-each-ref", "--format=%(HEAD) %(refname:short)", "refs/heads", optional=True).splitlines(),
        "graph": run_git(root, "log", "--graph", "--all", "--oneline", "--decorate", "-25", optional=True),
        "diff": diff(), "staged_diff": diff(True),
    }


PAGE = r'''<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CyberDeck / Neon Siege</title><style>
:root{--bg:#0b0e13;--panel:#131820;--line:#29313c;--muted:#8d9bad;--text:#eef2f6;--lime:#d0ff71;--red:#ff697f;--blue:#86baff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px 'Segoe UI',system-ui,sans-serif}button,input{font:inherit}button{cursor:pointer;color:inherit;background:#1d2530;border:1px solid var(--line);border-radius:8px;padding:10px 14px;transition:.18s}button:hover{border-color:var(--lime);transform:translateY(-1px)}button:focus-visible,input:focus-visible{outline:2px solid var(--lime);outline-offset:3px}button:disabled{opacity:.5;cursor:wait}input{min-width:0;background:#0b1017;border:1px solid var(--line);border-radius:8px;padding:11px;color:var(--text)}.primary{background:var(--lime);color:#142008;border-color:var(--lime);font-weight:800}.muted{color:var(--muted)}.mono{font-family:Consolas,'Liberation Mono',monospace}.tiny{font-size:11px;letter-spacing:1.4px;text-transform:uppercase}.green{color:var(--lime)}
header{height:82px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 32px}.brand{display:flex;align-items:center;gap:12px;font-weight:850;font-size:23px;letter-spacing:-1px}.mark{background:var(--lime);color:#142008;border-radius:10px;padding:6px 10px;font-size:21px;letter-spacing:-4px;padding-right:14px}.brand small{font-size:10px;letter-spacing:2px;font-weight:500;display:block;color:var(--muted);margin-top:3px}.system{display:flex;gap:22px;align-items:center}.dot{display:inline-block;width:7px;height:7px;background:var(--lime);border-radius:50%;margin-right:7px;box-shadow:0 0 12px #d0ff7160}
main{max-width:1640px;margin:auto;padding:28px 32px}.intro{display:flex;align-items:end;justify-content:space-between;margin-bottom:22px}.intro h1{font-size:28px;letter-spacing:-1px;margin:5px 0}.intro p{margin:0;color:var(--muted)}.layout{display:grid;grid-template-columns:minmax(0,1fr) 390px;gap:22px}.panel{border:1px solid var(--line);border-radius:14px;background:var(--panel);overflow:hidden}.panel-head{display:flex;align-items:center;justify-content:space-between;padding:18px 20px;border-bottom:1px solid var(--line)}h2{font-size:16px;margin:4px 0}.tag{font-size:10px;border:1px solid #52623d;color:var(--lime);padding:4px 7px;border-radius:4px;letter-spacing:1px}.stats{display:grid;grid-template-columns:1.7fr 1fr 1fr 1fr;gap:15px;padding:17px 20px}.stat strong{display:block;font:700 22px Consolas,monospace;margin-top:5px}.health{height:5px;margin-top:8px;border-radius:4px;background:#303747;overflow:hidden}.health span{display:block;background:var(--lime);height:100%;transition:width .2s}.arena{position:relative;margin:0 14px;border:1px solid #303b45;border-radius:9px;overflow:hidden;background:#090e15;aspect-ratio:960/620}canvas{width:100%;height:100%;display:block;touch-action:none;cursor:crosshair}.overlay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;padding:16px;background:#0a1018b8;backdrop-filter:blur(4px)}.overlay[hidden]{display:none}.overlay h3{font-size:clamp(27px,3.5vw,54px);line-height:1.02;letter-spacing:-2px;margin:15px 0}.overlay p{color:#b1bece;line-height:1.7;max-width:400px;margin:14px auto 22px}.overlay .primary{padding:13px 26px}.choices{display:flex;gap:10px;margin:20px 0}.choices button{flex:1;padding:15px 9px;max-width:180px}.choices b{display:block;color:var(--lime);margin-bottom:8px}.controls{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;padding:17px 20px;color:var(--muted);font-size:12px}kbd{font:11px Consolas,monospace;color:var(--text);border:1px solid #3b4656;background:#1f2835;border-radius:4px;padding:3px 5px}.game-actions{display:flex;gap:7px}.game-actions button{padding:7px 9px;font-size:12px}.footnote{display:flex;justify-content:space-between;margin-top:13px;font-size:11px;color:var(--muted)}
.repo-controls{padding:16px;display:flex;gap:8px}.repo-controls input{flex:1;font:12px Consolas,monospace}.repo-controls button{padding:8px 11px}.repo-summary{margin:0 16px 14px;padding:14px;background:#0d1219;border:1px solid var(--line);border-radius:8px}.repo-summary strong{display:block;font-size:16px;margin-bottom:8px}.repo-summary .branch{font:12px Consolas,monospace;color:var(--lime);overflow-wrap:anywhere}.repo-summary p{margin:10px 0 0;font-size:12px;line-height:1.6;color:var(--muted)}.tabs{display:flex;padding:0 16px;border-bottom:1px solid var(--line);gap:14px}.tabs button{padding:11px 0;border:0;border-bottom:2px solid transparent;border-radius:0;background:none;font-size:12px;color:var(--muted)}.tabs button.active{border-bottom-color:var(--lime);color:var(--lime)}.repo-content{padding:17px;height:480px;overflow:auto}.empty{color:var(--muted);line-height:1.8;font-size:13px}.section-title{margin:0 0 14px;font-size:11px;color:var(--muted);letter-spacing:1.3px;text-transform:uppercase}.commit{position:relative;border-left:1px solid #3a4651;padding:0 0 21px 17px;margin-left:5px}.commit:before{content:'';position:absolute;left:-4px;top:5px;width:7px;height:7px;background:var(--lime);border-radius:50%}.commit strong{font-size:13px;font-weight:600;display:block;overflow-wrap:anywhere}.commit small{display:block;color:var(--muted);font-size:11px;margin-top:7px}.hash{color:var(--lime);font:11px Consolas,monospace;margin-right:6px}.file{display:flex;gap:10px;align-items:baseline;padding:11px 0;border-bottom:1px solid var(--line);font:12px Consolas,monospace;overflow-wrap:anywhere}.file code{flex-shrink:0;white-space:pre;color:var(--lime);background:#d0ff7110;padding:4px;border-radius:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.7 Consolas,monospace;color:#bed0df;margin:0}.diff-add{color:var(--lime)}.diff-del{color:var(--red)}.diff-head{color:var(--blue)}.subtabs{display:flex;gap:7px;margin-bottom:15px}.subtabs button{font-size:11px;padding:7px 9px}.note{border-top:1px solid var(--line);padding:13px 17px;font-size:11px;color:var(--muted);line-height:1.7}.error{color:var(--red);white-space:pre-wrap;overflow-wrap:anywhere}.counter{display:flex;gap:8px;margin:15px 0}.counter div{flex:1;padding:12px;border:1px solid var(--line);border-radius:8px;text-align:center}.counter b{font:700 22px Consolas,monospace;display:block}.counter small{color:var(--muted);font-size:10px}
@media(max-width:1050px){.layout{grid-template-columns:minmax(0,1fr) 335px}main{padding:20px}.system span:last-child{display:none}.choices{gap:5px}.choices button{font-size:11px}}@media(max-width:800px){.layout{grid-template-columns:1fr}header{padding:0 20px}.intro p{max-width:260px;font-size:12px}.system{font-size:10px}.repo-content{height:360px}.intro .tiny{display:none}.overlay h3{font-size:34px}.overlay p{font-size:12px;margin:10px auto}.choices{margin:10px}.choices button{padding:10px 7px}.stats{padding:13px;gap:10px}.stat strong{font-size:18px}.footnote{flex-wrap:wrap;gap:8px}}
.pilot-mode{display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:12px 20px;border-bottom:1px solid var(--line);color:var(--muted);font-size:12px}.pilot-mode button{padding:7px 10px;font-size:12px}.pilot-mode button[aria-pressed="true"]{color:var(--lime);border-color:#52623d;background:#d0ff7110}
</style></head><body>
<header><div class="brand"><span class="mark">//</span><div>CYBERDECK<small>PLAY. BUILD. COMMIT.</small></div></div><div class="system tiny mono"><span><i class="dot"></i>LOCAL SYSTEM ONLINE</span><span id="clock" class="muted"></span></div></header>
<main><div class="intro"><div><div class="tiny muted mono">YOUR PERSONAL COMMAND CENTER / 01</div><h1>Welkom terug, piloot.</h1><p>Verdedig de arena. Houd je code onder controle.</p></div><div class="tiny mono muted">OFFLINE READY <span class="green">↗</span></div></div>
<div class="layout"><section><div class="panel"><div class="panel-head"><div><div class="tiny muted mono">ARCADE / SURVIVAL</div><h2>NEON SIEGE <span class="tag">ENDLESS</span></h2></div><div class="game-actions"><button id="sound" aria-pressed="false">Geluid uit</button><button id="pause">Pauze</button><button id="restart">Opnieuw</button></div></div>
<div class="pilot-mode"><button id="assist" aria-pressed="true">Laptopmodus aan · F</button><span id="aimHelp">Richt en schiet automatisch. Jij ontwijkt.</span></div>
<div class="stats"><div class="stat"><span class="tiny muted">HULL / <span id="hp">100</span></span><div class="health"><span id="health" style="width:100%"></span></div><small id="dash" class="mono green">DASH READY · SHIELD 0</small></div><div class="stat"><span class="tiny muted">Wave</span><strong id="wave">01</strong></div><div class="stat"><span class="tiny muted">Score</span><strong id="score">0000</strong></div><div class="stat"><span class="tiny muted">Record</span><strong id="best">0000</strong></div></div>
<div class="arena"><canvas id="game" width="960" height="620" aria-label="Neon Siege: WASD of pijltjes bewegen, automatisch richten en schieten in laptopmodus, spatie dash"></canvas><div class="overlay" id="overlay"></div></div>
<div class="controls"><span><kbd>W A S D</kbd> / <kbd>↑ ← ↓ →</kbd> bewegen</span><span><kbd>SPATIE</kbd> dash · <kbd>P</kbd> pauze</span><span><kbd>ENTER</kbd> start / hervat · <kbd>F</kbd> laptopmodus</span></div></div><div class="footnote mono"><span>03 ENEMY CLASSES / RANDOM LOOT / CHOOSE YOUR UPGRADES</span><span>LAPTOP READY</span></div></section>
<aside class="panel"><div class="panel-head"><div><div class="tiny muted mono">DEVELOPER TOOLS</div><h2>Git control</h2></div><span class="tag">READ ONLY</span></div><form class="repo-controls" id="repoForm"><input id="repoPath" aria-label="Pad naar je lokale Git-repository" placeholder="Pad naar je lokale repository" spellcheck="false"><button id="refresh" title="Repository laden / vernieuwen" aria-label="Repository laden of vernieuwen">↻</button></form><div id="repoSummary" class="repo-summary"><strong>Verbind je project</strong><p>Plak hierboven het pad naar een lokale Git-repository.</p></div><nav class="tabs" aria-label="Git weergave"><button type="button" data-tab="overview" class="active">Overzicht</button><button type="button" data-tab="files">Bestanden</button><button type="button" data-tab="commits">Commits</button><button type="button" data-tab="diff">Diff</button></nav><div class="repo-content" id="repoContent" aria-live="polite"></div><div class="note">Lokale Git-data. Klik ↻ om te vernieuwen.<br>Pushen naar GitHub doe je zelf vanuit je terminal.</div></aside></div></main>
<script>
'use strict';
const CONFIG = __CONFIG__;
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let repo = null, repoTab = 'overview', staged = false;
$('repoPath').value = CONFIG.repo;
function drawRepo() {
  const el = $('repoContent');
  if (!repo) {el.innerHTML = '<p class="empty">Open een lokale repository om branches, bestanden, commits en diffs te bekijken.</p>'; return;}
  if (repoTab === 'overview') {
    const tracked = repo.files.filter(f => f.status !== '??');
    const untracked = repo.files.length - tracked.length;
    el.innerHTML = `<p class="section-title">Working tree</p><div class="counter"><div><b>${tracked.length}</b><small>GEWIJZIGD</small></div><div><b>${untracked}</b><small>NIEUW</small></div><div><b>${repo.branches.length}</b><small>BRANCHES</small></div></div><p class="empty">${repo.files.length ? 'Er staan wijzigingen klaar in je project.' : 'Alles bijgewerkt. Je working tree is schoon.'}</p><p class="section-title">Lokale branches</p><pre>${escapeHTML(repo.branches.join('\n') || 'Nog geen branch met een commit.')}</pre><p class="section-title" style="margin-top:24px">Commit graph</p><pre>${escapeHTML(repo.graph || 'Maak je eerste commit om de graph te zien.')}</pre>`;
  } else if (repoTab === 'files') {
    el.innerHTML = '<p class="section-title">XY = INDEX / WORKING TREE</p>' + (repo.files.map(f => `<div class="file"><code>${escapeHTML(f.status)}</code><span>${escapeHTML(f.previous ? f.previous + ' → ' + f.name : f.name)}</span></div>`).join('') || '<p class="empty">Geen gewijzigde bestanden.</p>') + '<p class="empty">M gewijzigd · A toegevoegd · D verwijderd · R hernoemd · ?? nieuw</p>';
  } else if (repoTab === 'commits') {
    el.innerHTML = '<p class="section-title">Laatste 18 commits / huidige branch</p>' + (repo.commits.map(c => `<div class="commit"><strong>${escapeHTML(c.subject)}</strong><small><span class="hash">${escapeHTML(c.hash)}</span>${escapeHTML(c.author)} · ${escapeHTML(c.time)}</small></div>`).join('') || '<p class="empty">Nog geen commits. Hier begint jouw project.</p>');
  } else {
    const text = staged ? repo.staged_diff : repo.diff;
    el.innerHTML = `<div class="subtabs"><button id="unstaged" ${!staged ? 'class="primary"' : ''}>Working tree</button><button id="staged" ${staged ? 'class="primary"' : ''}>Staged</button></div><pre>${text ? text.split('\n').map(line => `<span class="${line.startsWith('+') ? 'diff-add' : line.startsWith('-') ? 'diff-del' : /^(diff|@@|index)/.test(line) ? 'diff-head' : ''}">${escapeHTML(line)}</span>`).join('\n') : 'Geen diff. Nieuwe bestanden verschijnen hier na git add.'}</pre><p class="empty">Weergave beperkt tot 120.000 tekens per diff.</p>`;
    $('unstaged').onclick = () => {staged = false; drawRepo();}; $('staged').onclick = () => {staged = true; drawRepo();};
  }
}
async function loadRepo(event) {
  if (event) event.preventDefault();
  $('refresh').disabled = true; $('repoSummary').textContent = 'Repository uitlezen…';
  try {
    const response = await fetch('/api/repo', {method:'POST', headers:{'Content-Type':'application/json','X-CyberDeck-Token':CONFIG.token}, body:JSON.stringify({path:$('repoPath').value})});
    const result = await response.json(); if (!response.ok) throw new Error(result.error);
    repo = result; $('repoPath').value = repo.root;
    $('repoSummary').innerHTML = `<strong>${escapeHTML(repo.name)}</strong><span class="branch">⑂ ${escapeHTML(repo.branch)}</span><p>${repo.files.length ? repo.files.length + ' gewijzigde / nieuwe bestanden' : '● Working tree schoon'}</p>`;
    drawRepo();
  } catch (error) {
    repo = null; drawRepo(); $('repoSummary').innerHTML = `<strong>Repository niet geladen</strong><p class="error">${escapeHTML(error.message)}</p>`;
  } finally {$('refresh').disabled = false;}
}
$('repoForm').addEventListener('submit', loadRepo);
document.querySelectorAll('[data-tab]').forEach(button => button.onclick = () => {repoTab = button.dataset.tab; document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('active', b === button)); drawRepo();});
drawRepo(); loadRepo();
setInterval(() => {$('clock').textContent = new Date().toLocaleTimeString('nl-NL');}, 1000);

// Game model: all movement uses seconds, so frame rate does not change speed.
const canvas = $('game'), ctx = canvas.getContext('2d'), W = 960, H = 620;
const keys = new Set(), mouse = {x:W/2,y:H/2,down:false};
let phase = 'menu', player, enemies = [], bullets = [], sparks = [], loot = [];
let wave = 1, score = 0, pending = 0, spawnTimer = 0, fireTimer = 0, elapsed = 0;
let best = 0, sound = false, audio = null, assist = true;
try {best = Number(localStorage.getItem('cyberdeck-best')) || 0;} catch (_) {}
$('best').textContent = String(best).padStart(4,'0');
const random = (a,b) => a + Math.random() * (b-a);
const distance = (a,b) => Math.hypot(a.x-b.x,a.y-b.y);
function toggleAssist() {
  assist = !assist;
  mouse.down = false;
  $('assist').textContent = assist ? 'Laptopmodus aan · F' : 'Laptopmodus uit · F';
  $('assist').setAttribute('aria-pressed', String(assist));
  $('aimHelp').textContent = assist ? 'Richt en schiet automatisch. Jij ontwijkt.' : 'Richt met de muis. Houd links ingedrukt om te schieten.';
  $('assist').blur();
}
function nearestEnemy() {
  return enemies.reduce((nearest, enemy) => {
    if (enemy.hp <= 0) return nearest;
    return !nearest || distance(player, enemy) < distance(player, nearest) ? enemy : nearest;
  }, null);
}
function tone(freq, length=.05) {
  if (!sound || !audio) return;
  const oscillator = audio.createOscillator(), gain = audio.createGain();
  oscillator.type = 'triangle'; oscillator.frequency.value = freq;
  gain.gain.setValueAtTime(.035,audio.currentTime); gain.gain.exponentialRampToValueAtTime(.001,audio.currentTime+length);
  oscillator.connect(gain); gain.connect(audio.destination); oscillator.start(); oscillator.stop(audio.currentTime+length);
}
function burst(x,y,color,amount=14) {for(let i=0;i<amount;i++){const a=random(0,Math.PI*2), speed=random(40,200);sparks.push({x,y,vx:Math.cos(a)*speed,vy:Math.sin(a)*speed,life:random(.2,.6),color});}}
function showOverlay(html) {$('overlay').innerHTML = `<div>${html}</div>`; $('overlay').hidden = false; mouse.down = false; keys.clear();}
function hideOverlay() {$('overlay').hidden = true;}
function launch() {
  document.activeElement.blur();
  player = {x:W/2,y:H/2,r:13,hp:100,maxHP:100,shield:0,inv:0,dash:0,dashTime:0,rate:.20,shots:1,angle:-Math.PI/2};
  enemies=[];bullets=[];sparks=[];loot=[];wave=1;score=0;elapsed=0;fireTimer=0;keys.clear();mouse.down=false;
  phase='playing';hideOverlay();startWave();
}
function startWave() {pending=5+wave*2;spawnTimer=.8;tone(400,.12);}
function spawnEnemy() {
  const side=Math.floor(random(0,4));
  const x=side===0?22:side===1?W-22:random(30,W-30), y=side===2?22:side===3?H-22:random(30,H-30);
  const type=wave>2 && Math.random()<.25?'shooter':wave>1 && Math.random()<.3?'tank':'chaser';
  enemies.push({x,y,type,r:type==='tank'?22:15,hp:(type==='tank'?4:2)+Math.floor(wave/5),shot:random(.8,2),speed:(type==='tank'?47:type==='shooter'?62:85)+Math.min(wave*3,55)});
}
function upgradeScreen() {
  phase='upgrade';showOverlay(`<div class="tiny green mono">WAVE ${String(wave).padStart(2,'0')} CLEARED</div><h3>UPGRADE YOUR EDGE.</h3><p>Kies één upgrade voor de volgende golf.<br>Je krijgt ook 15 hull terug.</p><div class="choices"><button data-up="0"><b>1 / OVERCLOCK</b>18% sneller schieten</button><button data-up="1"><b>2 / REINFORCE</b>+25 max hull & herstel</button><button data-up="2"><b>3 / SPLIT SHOT</b>${player.shots<5?'+1 projectiel':'Max bereikt: +40 hull'}</button></div>`);
  document.querySelectorAll('[data-up]').forEach(b=>b.onclick=()=>chooseUpgrade(Number(b.dataset.up)));
}
function chooseUpgrade(choice) {
  if(phase!=='upgrade')return;
  if(choice===0)player.rate=Math.max(.065,player.rate*.82);
  if(choice===1){player.maxHP+=25;player.hp+=25;}
  if(choice===2){if(player.shots<5)player.shots++;else player.hp+=40;}
  player.hp=Math.min(player.maxHP,player.hp+15);wave++;bullets=[];loot=[];phase='playing';keys.clear();document.activeElement.blur();hideOverlay();startWave();
}
function damage(amount) {
  if(player.inv>0||player.dashTime>0)return;
  if(player.shield>0)player.shield--;else player.hp=Math.max(0,player.hp-amount);
  player.inv=.7;burst(player.x,player.y,'#ff697f',20);tone(110,.12);
  if(player.hp<=0){
    phase='over';best=Math.max(best,score);try{localStorage.setItem('cyberdeck-best',String(best));}catch(_){}
    showOverlay(`<div class="tiny mono" style="color:var(--red)">SIGNAL LOST / WAVE ${wave}</div><h3>ONE MORE RUN?</h3><p>Score <b class="green">${score}</b> · Record ${best}<br>${Math.floor(elapsed)} seconden overleefd. De arena wacht.</p><button class="primary" id="again">Opnieuw lanceren · Enter</button>`);$('again').onclick=launch;
  }
}
function togglePause() {
  if(phase==='playing'){phase='paused';showOverlay('<div class="tiny mono green">SYSTEM ON HOLD</div><h3>EVEN ADEMHALEN.</h3><p>Je Git-overzicht blijft beschikbaar.</p><button class="primary" id="resume">Verder spelen · Enter</button>');$('resume').onclick=togglePause;}
  else if(phase==='paused'){phase='playing';keys.clear();document.activeElement.blur();hideOverlay();}
}
function update(dt) {
  elapsed+=dt;player.inv=Math.max(0,player.inv-dt);player.dash=Math.max(0,player.dash-dt);player.dashTime=Math.max(0,player.dashTime-dt);
  let dx=Number(keys.has('d')||keys.has('arrowright'))-Number(keys.has('a')||keys.has('arrowleft'));
  let dy=Number(keys.has('s')||keys.has('arrowdown'))-Number(keys.has('w')||keys.has('arrowup'));
  if(dx||dy){const n=Math.hypot(dx,dy), speed=player.dashTime>0?850:235;player.x=Math.max(18,Math.min(W-18,player.x+dx/n*speed*dt));player.y=Math.max(18,Math.min(H-18,player.y+dy/n*speed*dt));}
  fireTimer-=dt;
  const target = assist ? nearestEnemy() : null;
  if (target) player.angle = Math.atan2(target.y-player.y,target.x-player.x);
  else if (!assist) player.angle = Math.atan2(mouse.y-player.y,mouse.x-player.x);
  if((assist ? target !== null : mouse.down) && fireTimer<=0){
    const aim=player.angle;
    for(let i=0;i<player.shots;i++){const a=aim+(i-(player.shots-1)/2)*.13;bullets.push({x:player.x,y:player.y,vx:Math.cos(a)*620,vy:Math.sin(a)*620,r:4,enemy:false,life:1.6});}
    fireTimer=player.rate;tone(650);
  }
  spawnTimer-=dt;if(pending>0 && spawnTimer<=0){spawnEnemy();pending--;spawnTimer=Math.max(.25,.9-wave*.035);}
  for(const enemy of enemies){
    const angle=Math.atan2(player.y-enemy.y,player.x-enemy.x), dist=distance(player,enemy);
    const direction=enemy.type==='shooter'&&dist<235?-0.3:1;
    enemy.x+=Math.cos(angle)*enemy.speed*dt*direction;enemy.y+=Math.sin(angle)*enemy.speed*dt*direction;
    if(enemy.type==='shooter'){enemy.shot-=dt;if(enemy.shot<=0){bullets.push({x:enemy.x,y:enemy.y,vx:Math.cos(angle)*205,vy:Math.sin(angle)*205,r:6,enemy:true,life:4});enemy.shot=1.7;}}
    if(dist<player.r+enemy.r)damage(enemy.type==='tank'?25:14);
    if(phase!=='playing')return;
  }
  for(const bullet of bullets){
    bullet.x+=bullet.vx*dt;bullet.y+=bullet.vy*dt;bullet.life-=dt;
    if(bullet.enemy){if(distance(bullet,player)<bullet.r+player.r){bullet.life=0;damage(18);}}
    else for(const enemy of enemies){if(enemy.hp>0 && distance(bullet,enemy)<bullet.r+enemy.r){enemy.hp--;bullet.life=0;burst(bullet.x,bullet.y,'#d0ff71',4);if(enemy.hp<=0){score+=enemy.type==='tank'?35:enemy.type==='shooter'?30:20;if(score>best){best=score;try{localStorage.setItem('cyberdeck-best',String(best));}catch(_){}}burst(enemy.x,enemy.y,enemy.type==='tank'?'#b99aff':'#ff697f');if(Math.random()<.18)loot.push({x:enemy.x,y:enemy.y,r:11,life:10,type:Math.random()<.6?'heal':'shield'});}break;}}
    if(phase!=='playing')return;
  }
  bullets=bullets.filter(b=>b.life>0&&b.x>-30&&b.x<W+30&&b.y>-30&&b.y<H+30);enemies=enemies.filter(e=>e.hp>0);
  for(const item of loot){item.life-=dt;if(distance(player,item)<player.r+item.r){if(item.type==='heal')player.hp=Math.min(player.maxHP,player.hp+25);else player.shield=Math.min(3,player.shield+1);item.life=0;tone(900,.12);}}
  loot=loot.filter(item=>item.life>0);
  if(pending===0&&enemies.length===0)upgradeScreen();
}
function render() {
  ctx.fillStyle='#090e15';ctx.fillRect(0,0,W,H);ctx.strokeStyle='#182331';ctx.lineWidth=1;
  for(let x=0;x<W;x+=40){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}for(let y=0;y<H;y+=40){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
  ctx.strokeStyle='#263748';ctx.strokeRect(20,20,W-40,H-40);
  for(const item of loot){ctx.save();ctx.translate(item.x,item.y);ctx.rotate(Math.PI/4);ctx.fillStyle=item.type==='heal'?'#d0ff71':'#86baff';ctx.fillRect(-8,-8,16,16);ctx.restore();ctx.fillStyle='#09121a';ctx.font='bold 13px monospace';ctx.textAlign='center';ctx.fillText(item.type==='heal'?'+':'S',item.x,item.y+4);}
  for(const e of enemies){ctx.save();ctx.translate(e.x,e.y);ctx.rotate(Math.atan2((player?player.y:H/2)-e.y,(player?player.x:W/2)-e.x));ctx.strokeStyle=e.type==='tank'?'#b99aff':e.type==='shooter'?'#ffbc6b':'#ff697f';ctx.fillStyle=e.type==='tank'?'#30213f':'#331c2b';ctx.lineWidth=2;ctx.beginPath();if(e.type==='tank')ctx.rect(-e.r,-e.r,e.r*2,e.r*2);else{ctx.moveTo(e.r,0);ctx.lineTo(-e.r,-e.r);ctx.lineTo(-e.r*.45,0);ctx.lineTo(-e.r,e.r);ctx.closePath();}ctx.fill();ctx.stroke();ctx.restore();}
  for(const b of bullets){ctx.fillStyle=b.enemy?'#ffbc6b':'#d0ff71';ctx.shadowColor=ctx.fillStyle;ctx.shadowBlur=10;ctx.beginPath();ctx.arc(b.x,b.y,b.r,0,Math.PI*2);ctx.fill();}ctx.shadowBlur=0;
  for(const s of sparks){ctx.globalAlpha=Math.max(0,s.life*1.8);ctx.fillStyle=s.color;ctx.fillRect(s.x,s.y,3,3);}ctx.globalAlpha=1;
  if(player){ctx.save();ctx.translate(player.x,player.y);if(player.shield){ctx.strokeStyle='#86baff';ctx.lineWidth=2;ctx.beginPath();ctx.arc(0,0,23,0,Math.PI*2);ctx.stroke();}ctx.rotate(player.angle);ctx.globalAlpha=player.inv>0?.55:1;ctx.fillStyle=player.dashTime>0?'#ffffff':'#d0ff71';ctx.shadowColor='#d0ff71';ctx.shadowBlur=18;ctx.beginPath();ctx.moveTo(21,0);ctx.lineTo(-13,-13);ctx.lineTo(-7,0);ctx.lineTo(-13,13);ctx.closePath();ctx.fill();ctx.restore();
    $('hp').textContent=Math.ceil(player.hp)+' / '+player.maxHP;$('health').style.width=player.hp/player.maxHP*100+'%';$('dash').textContent=(player.dash<=0?'DASH READY':'DASH '+player.dash.toFixed(1)+'s')+' · SHIELD '+player.shield;
  }
  $('wave').textContent=String(wave).padStart(2,'0');$('score').textContent=String(score).padStart(4,'0');$('best').textContent=String(Math.max(best,score)).padStart(4,'0');
}
canvas.addEventListener('pointermove',event=>{const rect=canvas.getBoundingClientRect();mouse.x=(event.clientX-rect.left)*W/rect.width;mouse.y=(event.clientY-rect.top)*H/rect.height;});
canvas.addEventListener('pointerdown',event=>{if(event.button===0&&phase==='playing'){event.preventDefault();document.activeElement.blur();const rect=canvas.getBoundingClientRect();mouse.x=(event.clientX-rect.left)*W/rect.width;mouse.y=(event.clientY-rect.top)*H/rect.height;mouse.down=true;}});
window.addEventListener('pointerup',()=>mouse.down=false);
window.addEventListener('keydown',event=>{
  if(event.target.matches('input,textarea,button'))return;
  const key=event.key.toLowerCase();
  if([' ','arrowup','arrowdown','arrowleft','arrowright'].includes(key))event.preventDefault();
  if(!event.repeat&&key==='enter'){
    if(phase==='menu'||phase==='over')launch();else if(phase==='paused')togglePause();
    event.preventDefault();return;
  }
  if(!event.repeat&&key==='f')toggleAssist();
  if(!event.repeat&&key==='p')togglePause();
  if(phase==='upgrade'&&['1','2','3'].includes(key))chooseUpgrade(Number(key)-1);
  if(phase==='playing'){keys.add(key);if(key===' '&&player.dash<=0){player.dash=2.5;player.dashTime=.17;tone(300,.08);}}
});
window.addEventListener('keyup',event=>keys.delete(event.key.toLowerCase()));
window.addEventListener('blur',()=>{keys.clear();mouse.down=false;if(phase==='playing')togglePause();});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&phase==='playing')togglePause();});
$('pause').onclick=()=>{togglePause();$('pause').blur();};$('restart').onclick=()=>{if(phase==='menu'||phase==='over'||confirm('Huidige run opnieuw beginnen?'))launch();$('restart').blur();};
$('sound').onclick=()=>{sound=!sound;if(sound){try{audio=audio||new(window.AudioContext||window.webkitAudioContext)();audio.resume();}catch(_){sound=false;}}$('sound').textContent=sound?'Geluid aan':'Geluid uit';$('sound').setAttribute('aria-pressed',String(sound));$('sound').blur();tone(700,.1);};
$('assist').onclick=toggleAssist;
showOverlay('<div class="tiny mono green">THE ARENA IS YOURS</div><h3>ONE PILOT.<br>ENDLESS DRONES.</h3><p>Beweeg met WASD of de pijltjes. Dash met spatie.<br>Laptopmodus richt en schiet voor je.</p><button class="primary" id="launch">Start je run · Enter</button>');
$('launch').onclick=launch;
let previous=performance.now();
function frame(now){const dt=Math.min((now-previous)/1000,.035);previous=now;if(phase==='playing')update(dt);if(phase==='playing'||phase==='over'){for(const s of sparks){s.x+=s.vx*dt;s.y+=s.vy*dt;s.life-=dt;}sparks=sparks.filter(s=>s.life>0);}render();requestAnimationFrame(frame);}
requestAnimationFrame(frame);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def local_host(self):
        return self.headers.get("Host") in {
            f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"
        }

    def do_GET(self):
        if not self.local_host():
            self.reply(403, '{"error":"Alleen lokaal bereikbaar."}')
        elif self.path == "/":
            config = json.dumps({"repo": self.server.repo, "token": self.server.token}, ensure_ascii=True).replace("<", "\\u003c")
            self.reply(200, PAGE.replace("__CONFIG__", config), "text/html; charset=utf-8")
        else:
            self.reply(404, '{"error":"Niet gevonden."}')

    def do_POST(self):
        if not self.local_host() or not secrets.compare_digest(self.headers.get("X-CyberDeck-Token", ""), self.server.token):
            self.reply(403, '{"error":"Ongeldige lokale sessie."}')
            return
        if self.path != "/api/repo":
            self.reply(404, '{"error":"Niet gevonden."}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ValueError("Ongeldige aanvraaggrootte.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or not isinstance(payload.get("path"), str):
                raise ValueError("Geef een geldig pad naar je repository op.")
            self.reply(200, json.dumps(repository_snapshot(payload["path"])))
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            self.reply(400, json.dumps({"error": str(error)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=str(Path.cwd()))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as error:
        parser.exit(1, f"Kan CyberDeck niet starten: {error}\nProbeer --port 8766\n")
    server.repo, server.token = str(Path(args.repo).expanduser().resolve()), secrets.token_hex(24)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"\nCYBERDECK / NEON SIEGE\nOpen {url}\nStoppen: Ctrl+C\n", flush=True)
    if not args.no_browser:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCyberDeck afgesloten.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
