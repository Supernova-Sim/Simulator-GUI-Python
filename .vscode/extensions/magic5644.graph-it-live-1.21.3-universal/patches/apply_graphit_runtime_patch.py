#!/usr/bin/env python3
"""Aplica (ou apenas valida) os patches de runtime V2 do Graph-It-Live 1.21.3.

Uso:
    python apply_graphit_runtime_patch.py --check-only   # valida ancoras
    python apply_graphit_runtime_patch.py                # aplica (idempotente)

Alvos:
    dist/extension.js  -> modo estatico/dinamico/diff + tracer + rotulo multifuncoes
    dist/webview.js    -> botoes de modo/play + card de detalhes ao clicar na aresta

Idempotente: se o bundle contem /*__AGY_RUNTIME_V2__*/, considera aplicado.
Se contiver V1 antiga, restaura o backup e reaplica V2 limpo.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_LOCAL_DIST = Path(__file__).resolve().parent.parent / "dist"
DIST = (
    _LOCAL_DIST
    if _LOCAL_DIST.exists()
    else Path("/home/icaro/.positron/extensions/magic5644.graph-it-live-1.21.3-universal/dist")
)
EXT = DIST / "extension.js"
WEB = DIST / "webview.js"
MARKER = "/*__AGY_RUNTIME_V2__*/"

EXT_BAK = Path("/home/icaro/.local/share/agy-aux/backups/extension.js.20261102_011845.a5b4ce8b.bak")
WEB_BAK = Path("/home/icaro/.local/share/agy-aux/backups/webview.js.20261102_011809.90e2288d.bak")


@dataclass(frozen=True)
class Patch:
    name: str
    old: str
    new: str


# ---------------------------------------------------------------------------
# Patches legados (cluster src e .graphitignore no crawl)
# ---------------------------------------------------------------------------
EXT_LEGACY: list[Patch] = [
    Patch(
        "fBe: guarda de indice em cadeia de heranca",
        "function fBe(a,n){let o=n;for(let c=n;c<a.length;c++)Aln.has(a[c])&&(o=c+1);return o}",
        "function fBe(a,n){let o=n;for(let c=n;c<a.length;c++)Aln.has(a[c])&&c+1<a.length&&(o=c+1);return o}",
    ),
    Patch(
        "DG: injeta _makeIgnoreFilter no crawler",
        "DG=class{constructor(n,o){this.dependencyAnalyzer=n;this.getConfig=o}dependencyAnalyzer;getConfig;async crawl(n,o){let c=new Set,",
        "DG=class{constructor(n,o){this.dependencyAnalyzer=n;this.getConfig=o}dependencyAnalyzer;getConfig;"
        '_makeIgnoreFilter(n){try{Ame();let o=new Set;this.getConfig()?.rootDir&&o.add(VW.resolve(this.getConfig().rootDir));'
        "if(n){let l=VW.dirname(VW.resolve(n));for(;l&&l!==VW.dirname(l);l=VW.dirname(l))"
        'if(iyt.existsSync(VW.join(l,".graphitignore"))||iyt.existsSync(VW.join(l,".gitignore"))){o.add(l);break}}'
        "let c=[...o].map(l=>({root:l,ig:xme(l)}));return l=>{if(!l)return!1;let p=VW.resolve(l);"
        "return c.some(({root:g,ig:b})=>{let I=VW.relative(g,p);return!I||I.startsWith(\"..\")||VW.isAbsolute(I)?!1:b(I,!1)})}}catch{return()=>!1}}"
        "async crawl(n,o){let _ig=this._makeIgnoreFilter(n),c=new Set,",
    ),
    Patch(
        "DG.crawl: aplica filtro por arquivo",
        "for(let pe of ae){w(),c.add(pe.path);",
        "for(let pe of ae){if(_ig(pe.path)){nL.debug(`Skipping ${pe.path}: matched .graphitignore`);continue}w(),c.add(pe.path);",
    ),
    Patch(
        "DG.crawlFrom: injeta _makeIgnoreFilter",
        "async crawlFrom(n,o,c=10,l){let p=new Set,",
        "async crawlFrom(n,o,c=10,l){let _ig=this._makeIgnoreFilter(n),p=new Set,",
    ),
    Patch(
        "DG.crawlFrom: aplica filtro no loop",
        "for(let Tr of Sr)Kt(Tr,Yn),UN(Tr.path)||await Un(Tr.path,Dt+1);",
        "for(let Tr of Sr){if(_ig(Tr.path))continue;Kt(Tr,Yn),UN(Tr.path)||await Un(Tr.path,Dt+1)}",
    ),
]


# ---------------------------------------------------------------------------
# extension.js V2: metodos de runtime com rotulo inteligente de multifuncoes
# ---------------------------------------------------------------------------
_GET_WS_ROOT = (
    '_getWorkspaceRoot(n){let _fs=require("node:fs"),_p=require("node:path"),_d="";'
    'if(n&&_p.isAbsolute(String(n)))_d=_p.dirname(String(n));'
    "else{let _f=Wp.workspace.workspaceFolders;_f&&_f.length&&(_d=_f[0].uri.fsPath)}"
    "for(; _d; _d=_p.dirname(_d)){try{if(_fs.existsSync(_p.join(_d,\".git\"))||_fs.existsSync(_p.join(_d,\"pyproject.toml\")))return _d}catch{}"
    "if(_p.dirname(_d)===_d)break}"
    "let _f=Wp.workspace.workspaceFolders;return _f&&_f.length?_f[0].uri.fsPath:process.cwd()}"
)
_MAKE_WS_IGNORE = '_makeWsIgnore(n){try{Ame();return xme(n)}catch{return()=>!1}}'
_LOAD_TRACE = (
    '_loadRuntimeTrace(n){try{let _fs=require("node:fs"),_p=require("node:path"),'
    '_ws=this._getWorkspaceRoot(n),_file=_p.join(_ws,".graph-it","dynamic_trace.json");'
    "if(!_fs.existsSync(_file))return null;"
    'let _t=JSON.parse(_fs.readFileSync(_file,"utf8"));if(!_t||!Array.isArray(_t.nodes))return null;'
    'let _root=String(_t.workspace||_ws).replace(/\\\\/g,"/"),_ig=this._makeWsIgnore(_root),'
    "_norm=_x=>wt(String(_x)),"
    '_in=_x=>{let _r=String(_x||"").replace(/\\\\/g,"/");'
    'return _r.startsWith(_root+"/")&&!_ig(_r.slice(_root.length+1))};'
    "_t.nodes=_t.nodes.map(_norm).filter(_in);let _set=new Set(_t.nodes);"
    "_t.edges=(Array.isArray(_t.edges)?_t.edges:[])"
    ".map(_e=>({..._e,source:_norm(_e.source),target:_norm(_e.target)}))"
    ".filter(_e=>_set.has(_e.source)&&_set.has(_e.target));"
    "_t.entrypoint=_t.entrypoint&&_set.has(_norm(_t.entrypoint))?_norm(_t.entrypoint):null;"
    "_t.workspace=_root;return _t}catch{return null}}"
)
_STATE_PAYLOAD = (
    '_getRuntimeStatePayload(n){let _i="";if(n){let _c=n.total_calls||0,'
    '_d=Math.round(n.duration_ms||0);_i=`${n.target_display||"trace"} \\xB7 ${_c} chamadas \\xB7 ${_d}ms'
    '${n.truncated?" (truncado)":""}`}'
    "return{mode:this._runtimeMode,running:this._runtimeRunning,info:_i}}"
)
_RT_LABEL = (
    '_rtLabel(e){let _f=e.funcs?Object.entries(e.funcs).filter(([_n])=>_n).sort((_a,_b)=>_b[1]-_a[1]).map(([_n])=>_n):[];'
    '_f.length===0&&e.top_func&&(_f=[e.top_func]);'
    'let _s=_n=>_n.length>28?_n.slice(0,27)+"\u2026":_n,'
    '_n=_f.length===0?"call":_f.length<=3?_f.map(_s).join(", "):`${_s(_f[0])}, ${_s(_f[1])} (+${_f.length-2} fns)`,'
    '_ms=e.time_ms<1?"<1":Math.round(e.time_ms||0);'
    'return `${_n} \xB7 ${Number(e.calls)||0}x \xB7 ${_ms}ms`}'
)
_BUILD_GRAPH = (
    "_buildRuntimeGraphData(n,o,c){let _nodes=Array.isArray(n.nodes)?n.nodes.slice():[],_pc={},"
    "_edges=(Array.isArray(n.edges)?n.edges:[]).map(_e=>{"
    "_pc[_e.target]=(_pc[_e.target]||0)+1;"
    'return{source:_e.source,target:_e.target,relationType:"call",rtCalls:_e.calls,'
    "rtLabel:this._rtLabel(_e),rtFuncs:_e.funcs}}),"
    "_data={nodes:_nodes,edges:_edges,parentCounts:_pc,rtShowAll:!0};"
    "try{GG(_data,o,c)}catch{}return _data}"
)
_APPLY_DIFF = (
    "_applyRuntimeDiff(n,o,c,l){try{let _base=n||{},_nodes=Array.isArray(_base.nodes)?_base.nodes.slice():[],"
    '_seen=new Set(_nodes.map(_x=>wt(typeof _x==="string"?_x:_x&&_x.id||""))),_pc={},_trace=new Map;'
    "for(let _e of Array.isArray(o.edges)?o.edges:[]){"
    "_pc[_e.target]=(_pc[_e.target]||0)+1,_trace.set(`${wt(_e.source)}->${wt(_e.target)}`,_e)}"
    "for(let _x of Array.isArray(o.nodes)?o.nodes:[]){let _id=wt(_x);_seen.has(_id)||(_seen.add(_id),_nodes.push(_x))}"
    "_edges=(Array.isArray(_base.edges)?_base.edges:[]).map(_e=>{"
    "let _k=`${wt(_e.source)}->${wt(_e.target)}`,_hit=_trace.get(_k);"
    "return _hit?(_trace.delete(_k),{..._e,rtCalls:_hit.calls,rtLabel:this._rtLabel(_hit),rtFuncs:_hit.funcs}):{..._e,rtDim:!0}});"
    "for(let _e of _trace.values())_edges.push({source:_e.source,target:_e.target,"
    'relationType:"call",rtCalls:_e.calls,rtLabel:this._rtLabel(_e),rtFuncs:_e.funcs});'
    "let _data={..._base,nodes:_nodes,edges:_edges,parentCounts:_pc};"
    "try{GG(_data,c,l)}catch{}return _data}catch{return n}}"
)
_CYCLE_MODE = (
    'async cycleRuntimeMode(){let n=this._runtimeMode==="static"?"runtime":'
    'this._runtimeMode==="runtime"?"diff":"static";'
    'if(this._runtimeMode=n,n==="runtime"){'
    'let o=require("node:path").join(this._getWorkspaceRoot(this._lastFileGraphRoot||""),".graph-it","dynamic_trace.json");'
    'if(!require("node:fs").existsSync(o)){'
    'Wp.window.showInformationMessage("Nenhum trace dinamico encontrado. Escolha um alvo para executar o trace."),'
    "await this.runRuntimeTrace({pickTarget:!0});return}}"
    'this._view?.webview.postMessage({command:"runtimeState",...this._getRuntimeStatePayload(null)}),'
    'await this.updateGraph(!0,"runtime-toggle")}'
)
_RUN_TRACE = (
    "async runRuntimeTrace(n){"
    'if(this._runtimeRunning){Wp.window.showWarningMessage("Ja existe um trace dinamico em execucao.");return}'
    'let _fs=require("node:fs"),_p=require("node:path"),_ws=this._getWorkspaceRoot(this._lastFileGraphRoot||""),'
    '_active=Wp.window.activeTextEditor?.document,'
    '_activeRel=_active&&_active.uri.scheme==="file"&&_active.fileName.startsWith(_ws)'
    '?_p.relative(_ws,_active.fileName).replace(/\\\\/g,"/"):"",'
    '_state=this._extContext?.workspaceState,_target=_state?.get("graphit.runtimeTarget");'
    "if(!_target||n?.pickTarget){let _files=[];try{"
    'let _skip=new Set([".venv","venv","__pycache__",".git",".graph-it","node_modules"]),_ig=this._makeWsIgnore(_ws),'
    "_walk=(_d,_rel)=>{let _ents;try{_ents=_fs.readdirSync(_d,{withFileTypes:!0})}catch{return}"
    "for(let _e of _ents){let _r=_rel?_rel+\"/\"+_e.name:_e.name,_abs=_p.join(_d,_e.name);"
    "if(_e.isDirectory()){if(!_skip.has(_e.name)&&!_ig(_r))_walk(_abs,_r)}"
    'else if(_e.isFile()&&_e.name.endsWith(".py")&&!_ig(_r))_files.push(_r)}};_walk(_ws,"")}catch{}'
    'let _rank=_r=>_r.startsWith("centralControle/")||_r.startsWith("scripts/")||!_r.includes("/")?0:1;'
    "_files.sort((_a,_b)=>_rank(_a)-_rank(_b)||_a.localeCompare(_b));"
    'let _items=[{label:"$(beaker) pytest (suite de testes)",description:"uv run python ... -m pytest",'
    'target:{kind:"pytest",label:"pytest"}},'
    '{label:"$(file-code) Arquivo Python aberto atualmente",description:_activeRel||"",'
    'target:{kind:"active",label:"arquivo ativo"}}];'
    'for(let _r of _files)_items.push({label:"$(play) "+_r,target:{kind:"script",relPath:_r,label:_r}});'
    'let _pick=await Wp.window.showQuickPick(_items,{placeHolder:"Escolha o alvo do trace dinamico",matchOnDescription:!0});'
    "if(!_pick)return;_target=_pick.target,await _state?.update?.(\"graphit.runtimeTarget\",_target)}"
    'if(_target.kind==="active"){if(!_activeRel){Wp.window.showWarningMessage("Nenhum arquivo Python ativo no workspace.");return}'
    '_target={kind:"script",relPath:_activeRel,label:_activeRel}}'
    "try{let _ex=_p.join(_ws,\".git\",\"info\",\"exclude\");"
    "if(_fs.existsSync(_p.join(_ws,\".git\",\"info\"))){"
    'let _txt=_fs.existsSync(_ex)?_fs.readFileSync(_ex,"utf8"):"";'
    '_txt.includes(".graph-it")||_fs.appendFileSync(_ex,(_txt.endsWith("\\n")||!_txt?"":"\\n")+".graph-it/\\n")}}catch{}'
    'let _tracer=_p.resolve(this.extensionUri.fsPath,"tracer","py_trace.py"),_out=_p.join(_ws,".graph-it","dynamic_trace.json");'
    "try{_fs.mkdirSync(_p.dirname(_out),{recursive:!0})}catch{}"
    'let _args=["--workspace",_ws,"--out",_out,"--"];'
    '_target.kind==="pytest"?_args.push("-m","pytest"):_args.push(_target.relPath||"");'
    'let _useUv=_fs.existsSync(_p.join(_ws,"pyproject.toml")),_cmd=_useUv?"uv":"python3",'
    "_cmdArgs=_useUv?[\"run\",\"python\",_tracer,..._args]:[_tracer,..._args],_runLabel=_target.label||\"trace\";"
    "this._runtimeRunning=!0,"
    'this._view?.webview.postMessage({command:"runtimeState",mode:this._runtimeMode,running:!0,'
    'info:"Executando "+_runLabel+"..."});'
    'let _cp=require("node:child_process"),_err="";'
    "await new Promise(_resolve=>{try{let _child=_cp.spawn(_cmd,_cmdArgs,{cwd:_ws,env:process.env}),"
    '_timer=setTimeout(()=>{try{_child.kill("SIGTERM")}catch{}},90000);'
    '_child.stderr&&_child.stderr.on("data",_b=>{_err=(_err+_b.toString()).split("\\n").slice(-40).join("\\n")});'
    "_child.on(\"error\",_e=>{_err+=String(_e&&_e.message||_e)});"
    "_child.on(\"close\",()=>{clearTimeout(_timer),_resolve()})}catch(_e){_err+=String(_e&&_e.message||_e),_resolve()}});"
    "this._runtimeRunning=!1;if(_fs.existsSync(_out)){"
    'this._runtimeMode==="static"&&(this._runtimeMode="runtime"),'
    'this._view?.webview.postMessage({command:"runtimeState",...this._getRuntimeStatePayload(this._loadRuntimeTrace(this._lastFileGraphRoot||""))}),'
    'await this.updateGraph(!0,"runtime-complete")}'
    'else Wp.window.showWarningMessage("Falha ao executar o trace dinamico. "+_err.trim().split("\\n").slice(-5).join(" | "))}'
)

EXT_RUNTIME: list[Patch] = [
    Patch(
        "router l_e: comandos cycleRuntimeMode/runRuntimeTrace",
        "refreshGraph:async()=>{await n.refreshGraph()},",
        "refreshGraph:async()=>{await n.refreshGraph()},"
        "cycleRuntimeMode:async()=>{await n.cycleRuntimeMode?.()},"
        "runRuntimeTrace:async o=>{await n.runRuntimeTrace?.(o)},",
    ),
    Patch(
        "register j0t: repassa novos callbacks",
        "refreshGraph:a.callbacks.refreshGraph,",
        "refreshGraph:a.callbacks.refreshGraph,"
        "cycleRuntimeMode:a.callbacks.cycleRuntimeMode,"
        "runRuntimeTrace:a.callbacks.runRuntimeTrace,",
    ),
    Patch(
        "DJ: estado de runtime no construtor",
        "DJ=class{constructor(n,o){this.extensionUri=n;",
        "DJ=class{"
        + MARKER
        + '_runtimeMode="static";_runtimeRunning=!1;_extContext;'
        "constructor(n,o){this.extensionUri=n,this._extContext=o;",
    ),
    Patch(
        "DJ: bind de cycleRuntimeMode/runRuntimeTrace",
        "refreshGraph:this.refreshGraph.bind(this),",
        "refreshGraph:this.refreshGraph.bind(this),"
        "cycleRuntimeMode:this.cycleRuntimeMode.bind(this),"
        "runRuntimeTrace:this.runRuntimeTrace.bind(this),",
    ),
    Patch(
        "performUpdateGraph: trava navegacao no modo dinamico",
        'async performUpdateGraph(n,o){if(!this._view||!this.spider||!this.graphViewService){Fl.debug("View or Spider not initialized");return}if(this._stateManager.viewMode==="architecture"){await this._view.webview.postMessage({command:"switchViewMode",mode:"architecture"});return}',
        'async performUpdateGraph(n,o){if(!this._view||!this.spider||!this.graphViewService){Fl.debug("View or Spider not initialized");return}if(this._stateManager.viewMode==="architecture"){await this._view.webview.postMessage({command:"switchViewMode",mode:"architecture"});return}'
        'if(this._runtimeMode==="runtime"&&o==="navigation"){Fl.debug("Runtime mode: keep dynamic graph fixed");return}'
        "if(this._runtimeMode===\"runtime\"&&!Wp.window.activeTextEditor?.document.fileName?.match(hI)&&this._loadRuntimeTrace(n)){"
        'await this._sendGraphUpdate(this._lastFileGraphRoot||"",n,o);return}',
    ),
    Patch(
        "_sendGraphUpdate: resolve trace e atalho do modo runtime",
        'async _sendGraphUpdate(n,o,c="unknown"){if(!(!this.graphViewService||!this._view))try{'
        "let l=this._stateManager.getUnusedFilterActive(),",
        'async _sendGraphUpdate(n,o,c="unknown"){if(!this.graphViewService||!this._view)return;'
        "let _rtTrace=null;"
        'if(this._runtimeMode!=="static"){let _rtWs=this._getWorkspaceRoot(n);'
        'if(_rtTrace=this._loadRuntimeTrace(n),_rtTrace&&this._runtimeMode==="runtime"){'
        "let _rtData=this._buildRuntimeGraphData(_rtTrace,_rtWs,this._configSnapshot.communityMode),"
        "_rtRoot=_rtTrace.entrypoint||_rtTrace.nodes[0]||n,"
        '_rtMsg={command:"updateGraph",filePath:_rtRoot,data:_rtData,expandAll:!0,isRefresh:o,'
        'refreshReason:c==="indexing"?"runtime":c,unusedDependencyMode:"none",filterUnused:!1,'
        "showCommunities:this._configSnapshot.showCommunities,"
        "communityMode:this._configSnapshot.communityMode,"
        "runtimeState:this._getRuntimeStatePayload(_rtTrace)};"
        "if(this._view.webview.postMessage(_rtMsg),this._lastFileGraphMetadata=_rtData.nodeMetadata,"
        "this._lastFileGraphRoot=_rtRoot,_rtTrace)return}}"
        "try{"
        "let l=this._stateManager.getUnusedFilterActive(),",
    ),
    Patch(
        "_sendGraphUpdate: aplica diff no grafo estatico",
        'F=await this.graphViewService.buildGraphData(n,!1,void 0,w),$=this._stateManager.getExpandAll(),U={command:"updateGraph",filePath:n,data:F,',
        'F=await this.graphViewService.buildGraphData(n,!1,void 0,w);'
        '_rtTrace&&this._runtimeMode==="diff"&&(F=this._applyRuntimeDiff(F,_rtTrace,this._getWorkspaceRoot(n),this._configSnapshot.communityMode));'
        'let $=this._stateManager.getExpandAll(),U={command:"updateGraph",filePath:n,data:F,',
    ),
    Patch(
        "_sendGraphUpdate: runtimeState na mensagem principal",
        "communityMode:this._configSnapshot.communityMode};if(this._view.webview.postMessage(U)",
        "communityMode:this._configSnapshot.communityMode,"
        "runtimeState:this._getRuntimeStatePayload(_rtTrace)};if(this._view.webview.postMessage(U)",
    ),
    Patch(
        "_sendGraphUpdate: runtimeState e diff na mensagem de usage-analysis",
        'let ue=await this.graphViewService.buildGraphData(n,!0,F,w),ae={command:"updateGraph",filePath:n,data:ue,expandAll:$,isRefresh:!0,refreshReason:"usage-analysis",unusedDependencyMode:g,filterUnused:l,showCommunities:this._configSnapshot.showCommunities,communityMode:this._configSnapshot.communityMode};this._view.webview.postMessage(ae)',
        'let ue=await this.graphViewService.buildGraphData(n,!0,F,w);'
        '_rtTrace&&this._runtimeMode==="diff"&&(ue=this._applyRuntimeDiff(ue,_rtTrace,this._getWorkspaceRoot(n),this._configSnapshot.communityMode));'
        'let ae={command:"updateGraph",filePath:n,data:ue,expandAll:$,isRefresh:!0,refreshReason:"usage-analysis",unusedDependencyMode:g,filterUnused:l,showCommunities:this._configSnapshot.showCommunities,communityMode:this._configSnapshot.communityMode,runtimeState:this._getRuntimeStatePayload(_rtTrace)};this._view.webview.postMessage(ae)',
    ),
    Patch(
        "DJ: metodos de runtime V2 (trace, modos, rotulo multifuncoes)",
        "};LGe();wJ();VGe();",
        _GET_WS_ROOT
        + _MAKE_WS_IGNORE
        + _LOAD_TRACE
        + _STATE_PAYLOAD
        + _RT_LABEL
        + _BUILD_GRAPH
        + _APPLY_DIFF
        + _CYCLE_MODE
        + _RUN_TRACE
        + "};LGe();wJ();VGe();",
    ),
]


# ---------------------------------------------------------------------------
# webview.js V2: API global, estilo de arestas, card de detalhes e toolbar
# ---------------------------------------------------------------------------
_COLLAPSE_BUTTON = (
    'Ne.default.createElement("button",{onClick:()=>o(!d),style:{background:"var(--vscode-button-secondaryBackground)",'
    'color:"var(--vscode-button-secondaryForeground)",border:"1px solid var(--vscode-button-border)",borderRadius:4,'
    'padding:"6px 12px",cursor:"pointer",fontSize:12}},d?"\\u229F Collapse All":"\\u229E Expand All")'
)
_MODE_BUTTON = (
    ',k==="file"&&Ne.default.createElement("button",{'
    'onClick:()=>globalThis.__graphItApi?.postMessage({command:"cycleRuntimeMode"}),'
    'title:_rtSt.info||"Alternar modo estatico / dinamico / diff",'
    "style:{background:_rtSt.mode===\"runtime\"?\"#14532d\":_rtSt.mode===\"diff\"?\"var(--vscode-button-background)\":\"var(--vscode-button-secondaryBackground)\","
    "color:_rtSt.mode===\"runtime\"?\"#dcfce7\":_rtSt.mode===\"diff\"?\"var(--vscode-button-foreground)\":\"var(--vscode-button-secondaryForeground)\","
    "border:_rtSt.mode===\"runtime\"?\"1px solid #4ade80\":\"1px solid var(--vscode-button-border)\","
    "borderRadius:4,padding:\"6px 12px\",cursor:\"pointer\",fontSize:12}},"
    '_rtSt.mode==="runtime"?"\\u26A1 Din\\u00E2mico":_rtSt.mode==="diff"?"\\u{1F50D} Diff":"\\u{1F4C4} Est\\u00E1tico")'
)
_PLAY_BUTTON = (
    ',k==="file"&&Ne.default.createElement("button",{'
    "onClick:Z=>globalThis.__graphItApi?.postMessage({command:\"runRuntimeTrace\",pickTarget:!!Z.shiftKey}),"
    "disabled:_rtSt.running,"
    'title:"Executar trace din\\u00E2mico via uv run (Shift+Clique para escolher outro script ou pytest)",'
    "style:{background:\"var(--vscode-button-background)\",color:\"var(--vscode-button-foreground)\","
    "border:\"1px solid var(--vscode-button-border)\",borderRadius:4,padding:\"6px 12px\","
    "cursor:_rtSt.running?\"progress\":\"pointer\",fontSize:12,opacity:_rtSt.running?.6:1}},"
    '_rtSt.running?"\\u23F3":"\\u25B6")'
)

_DECL_DETAIL_CARD = (
    'let W=(0,Ne.useCallback)((Z,ae)=>{let de=ae.data?.line;V.current(ae.id,de)},[]);'
    'let _selE=Ce&&k==="file"?Le.edges.find(_e=>_e.id===Ce):null,'
    '_selF=_selE&&!_selE.hidden&&_selE.rtFuncs?Object.entries(_selE.rtFuncs).sort((_a,_b)=>_b[1]-_a[1]):[];'
    'return Ne.default.createElement("div",{ref:y,onKeyDownCapture:k==="file"?X:void 0,style:{width:"100%",height:"100vh",position:"relative"}},'
    '_selF.length>0&&Ne.default.createElement("div",{role:"dialog","aria-label":"Fun\u00E7\u00F5es chamadas",'
    'style:{position:"absolute",bottom:56,right:16,zIndex:30,maxWidth:380,maxHeight:"50vh",overflow:"auto",'
    'background:"var(--vscode-editorWidget-background, var(--vscode-editor-background))",'
    'border:"1px solid var(--vscode-widget-border, #555)",borderRadius:6,padding:"8px 10px",fontSize:11,'
    'color:"var(--vscode-editor-foreground)",boxShadow:"0 4px 16px rgba(0,0,0,.35)"}},'
    'Ne.default.createElement("div",{style:{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,marginBottom:6}},'
    'Ne.default.createElement("strong",null,_selE.label||"Fun\u00E7\u00F5es chamadas"),'
    'Ne.default.createElement("button",{type:"button",onClick:oe,"aria-label":"Fechar",'
    'style:{background:"transparent",border:"none",color:"inherit",cursor:"pointer",fontSize:14,lineHeight:1}},"\xD7")),'
    '_selF.map(([_n,_c])=>Ne.default.createElement("div",{key:_n,style:{display:"flex",justifyContent:"space-between",gap:12,padding:"2px 0"}},'
    'Ne.default.createElement("span",{title:_n,style:{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontFamily:"monospace"}},_n),'
    'Ne.default.createElement("span",{style:{opacity:.8,flexShrink:0,fontWeight:600}},_c+"x")))),'
)

WEB_RUNTIME: list[Patch] = [
    Patch(
        "webview: expoe a API do VS Code em globalThis",
        'var Bt=(function(){try{return typeof acquireVsCodeApi=="function"?acquireVsCodeApi():null}catch{return null}})()',
        MARKER
        + 'var Bt=(function(){try{let _v=typeof acquireVsCodeApi=="function"?acquireVsCodeApi():null;'
        "return globalThis.__graphItApi=_v,_v}catch{return null}})()",
    ),
    Patch(
        "Bq: estilo/precedencia de arestas dinamicas + rtFuncs",
        "function Bq(e,t,n,a,r,i){let c=new Set,b=new Set(a),d=r===\"dim\"&&i;"
        "return e.map(({source:o,target:s,relationType:u})=>({source:Ye(o),target:Ye(s),relationType:u}))"
        ".filter(({source:o,target:s})=>t.has(o)&&t.has(s))"
        ".flatMap(({source:o,target:s,relationType:u})=>{let l=`${o}->${s}`;if(c.has(l))return[];c.add(l);"
        "let f=b.has(l),h=n.has(l),v=EI(h),w={};return d&&f?",
        "function Bq(e,t,n,a,r,i){let c=new Set,b=new Set(a),d=r===\"dim\"&&i;"
        "return e.map(({source:o,target:s,relationType:u,rtCalls:_rc,rtLabel:_rl,rtDim:_rd,rtFuncs:_rf})=>"
        "({source:Ye(o),target:Ye(s),relationType:u,rtCalls:_rc,rtLabel:_rl,rtDim:_rd,rtFuncs:_rf}))"
        ".filter(({source:o,target:s})=>t.has(o)&&t.has(s))"
        ".flatMap(({source:o,target:s,relationType:u,rtCalls:_rc,rtLabel:_rl,rtDim:_rd,rtFuncs:_rf})=>"
        "{let l=`${o}->${s}`;if(c.has(l))return[];c.add(l);"
        "let f=b.has(l),h=n.has(l),v=EI(h),w={};return _rc>0?"
        'w={style:{...v.style,stroke:h?"#ff4d4d":"#4ade80",'
        "strokeWidth:Math.min(3.6,1.9+Math.log10(_rc+1)*.65)},animated:!1,label:_rl,"
        'labelStyle:{fill:"#86efac",fontSize:10,fontWeight:600},'
        'labelBgStyle:{fill:"var(--vscode-editor-background)",fillOpacity:.88}}:_rd?'
        'w={style:{...v.style,opacity:.22,strokeDasharray:"4 4"},animated:!1,label:"n\\u00E3o rodou",'
        'labelStyle:{fill:"var(--vscode-descriptionForeground)",opacity:.45,fontSize:9},'
        "labelBgStyle:{fill:\"transparent\"}}:d&&f?",
    ),
    Patch(
        "Bq: preserva rtFuncs no objeto de aresta",
        'u==="call"&&(w={style:{...v.style,strokeWidth:2},animated:!0}),[{id:l,source:o,target:s,animated:!0,...v,...w}]',
        'u==="call"&&(w={style:{...v.style,strokeWidth:2},animated:!0}),[{id:l,source:o,target:s,animated:!0,...v,...w,rtFuncs:_rf}]',
    ),
    Patch(
        "kI: exibe todos os nos executados no modo runtime (rtShowAll)",
        "i&&(x=Lq(N,T,Er.MAX_RENDER_NODES));let{visibleNodes:E,truncated:y}=Mq(w,S,r,N,Er.MAX_RENDER_NODES);",
        "i&&(x=Lq(N,T,Er.MAX_RENDER_NODES)),t.rtShowAll&&Lq(N,t.nodes.map(Ye),Er.MAX_RENDER_NODES);let{visibleNodes:E,truncated:y}=Mq(w,S,r,N,Er.MAX_RENDER_NODES);",
    ),
    Patch(
        "ReactFlowGraph: estado runtimeState + listener",
        "Jq({containerRef:y,nodesInitialized:E,nodeCount:H.length,fitView:Ke}),"
        "Ne.default.useEffect(()=>{let Z=ae=>{let de=ae.data;"
        'de.command==="refreshing"&&(bt.debug("ReactFlowGraph: Received refreshing message"),I(!0)),'
        'de.command==="updateGraph"&&(bt.debug("ReactFlowGraph: Received updateGraph message, clearing loading state"),I(!1))};'
        'return window.addEventListener("message",Z),()=>window.removeEventListener("message",Z)},[]);',
        "Jq({containerRef:y,nodesInitialized:E,nodeCount:H.length,fitView:Ke});"
        'let[_rtSt,_setRtSt]=Ne.default.useState({mode:"static",running:!1,info:""});'
        "Ne.default.useEffect(()=>{let Z=ae=>{let de=ae.data;"
        'de.command==="refreshing"&&(bt.debug("ReactFlowGraph: Received refreshing message"),I(!0)),'
        'de.command==="runtimeState"&&_setRtSt({mode:de.mode||"static",running:!!de.running,info:de.info||""}),'
        'de.command==="updateGraph"&&(bt.debug("ReactFlowGraph: Received updateGraph message, clearing loading state"),'
        "I(!1),de.runtimeState&&_setRtSt(de.runtimeState))};"
        'return window.addEventListener("message",Z),()=>window.removeEventListener("message",Z)},[]);',
    ),
    Patch(
        "ReactFlowGraph: botoes de modo e play na toolbar",
        _COLLAPSE_BUTTON,
        _COLLAPSE_BUTTON + _MODE_BUTTON + _PLAY_BUTTON,
    ),
    Patch(
        "ReactFlowGraph: card flutuante de detalhes ao clicar na aresta",
        'let W=(0,Ne.useCallback)((Z,ae)=>{let de=ae.data?.line;V.current(ae.id,de)},[]);return Ne.default.createElement("div",{ref:y,onKeyDownCapture:k==="file"?X:void 0,style:{width:"100%",height:"100vh",position:"relative"}},',
        _DECL_DETAIL_CARD,
    ),
]


# ---------------------------------------------------------------------------
# Motor de aplicacao
# ---------------------------------------------------------------------------
def apply_patch(text: str, patch: Patch) -> str:
    """Aplica um patch uma unica vez (ou confirma que ja esta aplicado)."""
    if patch.new in text:
        return text
    count = text.count(patch.old)
    if count != 1:
        raise RuntimeError(f"ancora encontrada {count}x (esperado 1x)")
    return text.replace(patch.old, patch.new, 1)


def process(path: Path, bak: Path, patches: list[Patch], check_only: bool) -> int:
    """Retorna 0 em sucesso; levanta RuntimeError em ancora invalida."""
    if not path.is_file():
        raise RuntimeError(f"arquivo nao encontrado: {path}")
    text = path.read_text(encoding="utf-8")

    if MARKER in text:
        missing = [p.name for p in patches if p.new not in text]
        if missing:
            raise RuntimeError(
                "marcador presente mas patches ausentes: " + ", ".join(missing)
            )
        print(f"[ok] {path.name}: ja aplicado (marcador V2 encontrado)")
        return 0

    # Se contiver versao antiga V1, comeca a partir do backup limpo
    if "/*__AGY_RUNTIME_V1__*/" in text and bak.is_file():
        print(f"[upgrade] {path.name}: atualizando de V1 para V2 a partir do backup limpo...")
        text = bak.read_text(encoding="utf-8")

    pending = 0
    for patch in patches:
        try:
            new_text = apply_patch(text, patch)
        except RuntimeError as exc:
            raise RuntimeError(f"{path.name} :: {patch.name} -> {exc}") from exc
        if new_text != text:
            pending += 1
            print(f"[{'validado' if check_only else 'aplicado'}] {path.name}: {patch.name}")
        else:
            print(f"[ja aplicado] {path.name}: {patch.name}")
        text = new_text

    if pending and not check_only:
        path.write_text(text, encoding="utf-8")
    return pending


def node_check(path: Path) -> None:
    result = subprocess.run(
        ["node", "--check", str(path)], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"node --check falhou em {path}:\n{result.stderr}")
    print(f"[node --check] {path.name}: OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="apenas valida as ancoras (nao escreve nada)",
    )
    args = parser.parse_args()

    try:
        ext_pending = process(EXT, EXT_BAK, EXT_LEGACY + EXT_RUNTIME, args.check_only)
        web_pending = process(WEB, WEB_BAK, WEB_RUNTIME, args.check_only)
    except RuntimeError as exc:
        print(f"[erro] {exc}", file=sys.stderr)
        return 1

    # Auditoria de sintaxe tanto no modo normal quanto no --check-only.
    for path in (EXT, WEB):
        try:
            node_check(path)
        except RuntimeError as exc:
            print(f"[erro] {exc}", file=sys.stderr)
            return 1

    if args.check_only:
        print(f"\nCheck-only concluido: {ext_pending + web_pending} patch(es) pendente(s).")
    else:
        print(f"\nConcluido: {ext_pending + web_pending} patch(es) aplicado(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
