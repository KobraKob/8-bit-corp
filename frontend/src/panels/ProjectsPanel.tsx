import React, { useMemo, useState } from 'react';
import { useAppStore } from '../state/useAppStore';
import { apiClient } from '../api/client';
import { Project } from '../api/types';
import { Archive, Clock3, Pause, Play, Search, Square, Trash2, FolderOpen } from 'lucide-react';

type Filter = 'all' | 'active' | 'paused' | 'completed' | 'stopped';
const filters: { id: Filter; label: string }[] = [{id:'all',label:'All'},{id:'active',label:'Active'},{id:'paused',label:'Paused'},{id:'completed',label:'Completed'},{id:'stopped',label:'Stopped'}];
const styles: Record<string,string> = {active:'border-sky-500/30 bg-sky-500/10 text-sky-300',paused:'border-amber-500/30 bg-amber-500/10 text-amber-300',completed:'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',stopped:'border-rose-500/30 bg-rose-500/10 text-rose-300'};

export const ProjectsPanel: React.FC = () => {
 const {projects,activeProjectId,fetchProjects,setActiveProject,clearActiveProject,setActiveDrawerTab}=useAppStore();
 const [filter,setFilter]=useState<Filter>('all'),[query,setQuery]=useState(''),[busy,setBusy]=useState<string|null>(null),[error,setError]=useState('');
 const counts=useMemo(()=>({all:projects.length,active:projects.filter(p=>p.status==='active').length,paused:projects.filter(p=>p.status==='paused').length,completed:projects.filter(p=>p.status==='completed').length,stopped:projects.filter(p=>p.status==='stopped').length}),[projects]);
 const visible=useMemo(()=>projects.filter(p=>(filter==='all'||p.status===filter)&&`${p.name} ${p.client_name||''} ${p.brief}`.toLowerCase().includes(query.toLowerCase())),[projects,filter,query]);
 const action=async(p:Project,kind:'pause'|'resume'|'stop'|'delete')=>{
  if(kind==='stop'&&!window.confirm(`Stop "${p.name}"? Queued tasks will be cancelled. This cannot be resumed.`))return;
  if(kind==='delete'&&!window.confirm(`Permanently delete "${p.name}" and its deliverables? This cannot be undone.`))return;
  setBusy(p.id);setError('');
  try{
   if(kind==='pause')await apiClient.pauseProject(p.id);
   if(kind==='resume')await apiClient.resumeProject(p.id);
   if(kind==='stop')await apiClient.stopProject(p.id);
   if(kind==='delete'){await apiClient.deleteProject(p.id);if(activeProjectId===p.id)clearActiveProject();}
   await fetchProjects();
  }catch(e){setError(e instanceof Error?e.message:'Project action failed');}finally{setBusy(null);}
 };
 const open=async(p:Project,tab:'tree'|'artifacts'='tree')=>{await setActiveProject(p.id);setActiveDrawerTab(tab);};
 return <div className="h-full flex flex-col bg-slate-950 text-slate-100">
  <header className="p-4 border-b border-slate-800 space-y-3">
   <div className="flex justify-between gap-3"><div><h2 className="text-sm font-semibold">Project portfolio</h2><p className="mt-1 text-[11px] text-slate-500">Track work from intake through delivery.</p></div><span className="text-[10px] font-mono text-slate-500">{projects.length} TOTAL</span></div>
   <div className="relative"><Search size={13} className="absolute left-3 top-2.5 text-slate-500"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search projects or clients" className="w-full rounded-md border border-slate-800 bg-slate-900 py-2 pl-8 pr-3 text-xs outline-none focus:border-sky-500"/></div>
   <div className="flex gap-1 overflow-x-auto pb-1">{filters.map(f=><button key={f.id} onClick={()=>setFilter(f.id)} className={`shrink-0 rounded-md border px-2.5 py-1.5 text-[10px] ${filter===f.id?'border-sky-500/50 bg-sky-500/10 text-sky-300':'border-slate-800 text-slate-400 hover:bg-slate-900'}`}>{f.label}<span className="ml-1.5 text-slate-500">{counts[f.id]}</span></button>)}</div>
  </header>
  {error&&<div role="alert" className="mx-3 mt-3 rounded border border-rose-500/30 bg-rose-500/10 p-2.5 text-[11px] text-rose-300">{error}</div>}
  <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
   {visible.length===0?<div className="rounded-lg border border-dashed border-slate-800 p-8 text-center"><Archive size={22} className="mx-auto text-slate-600"/><p className="mt-3 text-xs font-medium text-slate-300">{query?'No matching projects':filter==='completed'?'No completed projects yet':'No projects in this view'}</p><p className="mt-1 text-[11px] text-slate-500">{filter==='completed'?'Projects move here after the final deliverable passes review.':'Try another status filter or clear your search.'}</p></div>
   :visible.map(p=>{const status=p.status||'active',loading=busy===p.id;return <article key={p.id} className={`rounded-lg border p-3 ${activeProjectId===p.id?'border-sky-500/50 bg-slate-900':'border-slate-800 bg-slate-900/50 hover:border-slate-700'}`}>
    <div className="flex items-start justify-between gap-2"><div className="min-w-0"><h3 className="truncate text-xs font-semibold">{p.name}</h3><p className="mt-1 truncate text-[10px] text-slate-500">{p.client_name||'No client assigned'}</p></div><span className={`shrink-0 rounded-full border px-2 py-0.5 text-[9px] capitalize ${styles[status]||styles.active}`}>{status}</span></div>
    <p className="mt-2 line-clamp-2 text-[11px] text-slate-400">{p.brief}</p><div className="mt-3 flex items-center gap-3 text-[10px] text-slate-500"><span className="flex items-center gap-1"><Clock3 size={11}/>Created {new Date(p.created_at).toLocaleDateString()}</span>{p.due_at&&<span>Due {new Date(p.due_at).toLocaleDateString()}</span>}</div>
    <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-slate-800 pt-3">
     <button onClick={()=>open(p)} className="inline-flex items-center gap-1 rounded-md bg-sky-600/15 px-2.5 py-1.5 text-[10px] text-sky-300"><FolderOpen size={11}/>Open workspace</button>
     <button onClick={()=>open(p,'artifacts')} className="inline-flex items-center gap-1 rounded-md border border-slate-700 px-2.5 py-1.5 text-[10px] text-slate-300"><Archive size={11}/>Deliverables</button>
     {status==='active'&&<button disabled={loading} onClick={()=>action(p,'pause')} className="inline-flex items-center gap-1 rounded-md border border-amber-500/25 px-2 py-1.5 text-[10px] text-amber-300 disabled:opacity-50"><Pause size={11}/>Pause</button>}
     {status==='paused'&&<button disabled={loading} onClick={()=>action(p,'resume')} className="inline-flex items-center gap-1 rounded-md border border-emerald-500/25 px-2 py-1.5 text-[10px] text-emerald-300 disabled:opacity-50"><Play size={11}/>Resume</button>}
     {(status==='active'||status==='paused')&&<button disabled={loading} onClick={()=>action(p,'stop')} className="inline-flex items-center gap-1 rounded-md border border-rose-500/25 px-2 py-1.5 text-[10px] text-rose-300 disabled:opacity-50"><Square size={10}/>Stop</button>}
     {(status==='completed'||status==='stopped')&&<button disabled={loading} onClick={()=>action(p,'delete')} className="ml-auto inline-flex items-center gap-1 rounded-md border border-rose-500/25 px-2 py-1.5 text-[10px] text-rose-300 disabled:opacity-50"><Trash2 size={11}/>Delete</button>}
    </div></article>})}
  </div>
 </div>;
};
