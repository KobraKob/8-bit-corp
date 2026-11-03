import React from 'react';
import { Activity, Building2, MessageCircle, Play, Radio, Send, Users, Workflow } from 'lucide-react';
import { apiClient } from '../api/client';
import { useAppStore } from '../state/useAppStore';
import { TaskTreeNode } from '../api/types';

type Tab = 'people' | 'rooms' | 'timeline';

function flatten(nodes: TaskTreeNode[]): TaskTreeNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children || [])]);
}

const eventLabel = (event: { type: string; payload: Record<string, any> }) => {
  const name = event.payload?.agent_name || event.payload?.from_name || 'Employee';
  const target = event.payload?.to_name ? ` → ${event.payload.to_name}` : '';
  const title = event.payload?.task_title ? `: ${event.payload.task_title}` : '';
  return `${name}${target} · ${event.type.replaceAll('.', ' ')}${title}`;
};

export const OfficeControlPanel: React.FC = () => {
  const { agents, taskTree, events, selectedRoom, setSelectedRoom, replayEventId, setReplayEvent } = useAppStore();
  const [tab, setTab] = React.useState<Tab>('people');
  const [department, setDepartment] = React.useState('All departments');
  const [actorId, setActorId] = React.useState('');
  const [targetId, setTargetId] = React.useState('');
  const [taskId, setTaskId] = React.useState('');
  const [message, setMessage] = React.useState('');
  const [meetingActive, setMeetingActive] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [feedback, setFeedback] = React.useState('');
  const [timelineIndex, setTimelineIndex] = React.useState(0);

  const employees = React.useMemo(() => agents.filter((agent) => agent.status === 'active'), [agents]);
  const departments = React.useMemo(() => ['All departments', ...Array.from(new Set(employees.map((a) => a.department))).sort()], [employees]);
  const visibleEmployees = department === 'All departments' ? employees : employees.filter((a) => a.department === department);
  const tasks = React.useMemo(() => flatten(taskTree).filter((task) => !['done', 'failed', 'cancelled'].includes(task.status)), [taskTree]);
  const chronologicalEvents = React.useMemo(() => [...events].sort((a, b) => a.id - b.id), [events]);
  const selectedEvent = chronologicalEvents[timelineIndex];

  React.useEffect(() => {
    if (!actorId && employees[0]) setActorId(employees[0].id);
    if (!targetId && employees[1]) setTargetId(employees[1].id);
  }, [employees, actorId, targetId]);

  React.useEffect(() => {
    if (selectedRoom) setTab('rooms');
  }, [selectedRoom]);

  const act = async (action: 'meeting_start' | 'meeting_end' | 'meeting_join' | 'meeting_leave' | 'message' | 'handoff', extra: { target_agent_id?: string; task_id?: string; message?: string } = {}) => {
    if (!actorId) return;
    setBusy(true);
    setFeedback('');
    try {
      await apiClient.officeAction({ action, agent_id: actorId, room: selectedRoom || 'Boardroom', ...extra });
      if (action === 'meeting_start') setMeetingActive(true);
      if (action === 'meeting_end') setMeetingActive(false);
      if (action === 'message') setMessage('');
      setFeedback(action === 'handoff' ? 'Task reassigned.' : action === 'message' ? 'Message delivered.' : 'Office updated.');
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  const replay = (index: number) => {
    setTimelineIndex(index);
    const event = chronologicalEvents[index];
    if (event) setReplayEvent(event.id);
  };

  return (
    <section className="absolute z-20 top-[112px] right-2 w-[min(360px,calc(100%-1rem))] max-h-[calc(100%-132px)] flex flex-col overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950/95 text-slate-100 shadow-2xl backdrop-blur-xl">
      <header className="flex items-center justify-between gap-3 border-b border-slate-800 px-3 py-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-cyan-400/10 text-cyan-300"><Building2 size={15} /></span>
          <div className="min-w-0"><div className="text-xs font-semibold tracking-wide">VIRTUAL OFFICE</div><div className="text-[10px] text-slate-500">{employees.length} employees online</div></div>
        </div>
        <span className="flex items-center gap-1 text-[10px] text-emerald-300"><Radio size={11} className="animate-pulse" /> LIVE</span>
      </header>
      <nav className="grid grid-cols-3 border-b border-slate-800 p-1">
        {([
          ['people', Users, 'People'],
          ['rooms', Building2, 'Rooms'],
          ['timeline', Activity, 'Timeline'],
        ] as const).map(([id, Icon, label]) => (
          <button key={id} onClick={() => setTab(id)} className={`flex items-center justify-center gap-1.5 rounded-md py-2 text-[11px] ${tab === id ? 'bg-slate-800 text-white' : 'text-slate-500 hover:text-slate-200'}`}>
            <Icon size={13} />{label}
          </button>
        ))}
      </nav>
      <div className="min-h-0 overflow-y-auto p-3">
        {tab === 'people' && (
          <div className="space-y-3">
            <label className="block text-[10px] uppercase tracking-wider text-slate-500">Department</label>
            <select value={department} onChange={(e) => setDepartment(e.target.value)} className="w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs outline-none focus:border-cyan-500">
              {departments.map((name) => <option key={name}>{name}</option>)}
            </select>
            <div className="grid grid-cols-2 gap-2">
              {visibleEmployees.map((agent) => {
                const active = events.find((event) => event.agent_id === agent.id);
                const fresh = active && Date.now() - new Date(active.ts).getTime() < 120000;
                const status = !fresh ? 'Idle' : active.type === 'agent.thinking' ? 'Thinking' : active.type === 'task.review_requested' || active.type === 'task.submitted' ? 'Reviewing' : active.type === 'task.blocked' || active.type === 'task.failed' ? 'Blocked' : active.type === 'task.done' || active.type === 'task.approved' ? 'Idle' : active.type === 'agent.tool_call' || active.type === 'task.started' ? 'Working' : 'Idle';
                return <button key={agent.id} onClick={() => setActorId(agent.id)} className={`rounded-lg border p-2 text-left ${actorId === agent.id ? 'border-cyan-500/70 bg-cyan-500/10' : 'border-slate-800 bg-slate-900/70'}`}>
                  <div className="truncate text-xs font-medium">{agent.display_name}</div><div className="mt-1 truncate text-[10px] text-slate-500">{agent.department}</div>
                  <div className="mt-2 flex items-center gap-1.5 text-[10px]"><span className={`h-1.5 w-1.5 rounded-full ${status === 'Blocked' ? 'bg-rose-400' : status === 'Idle' ? 'bg-slate-500' : 'bg-emerald-400'}`} />{status}</div>
                </button>;
              })}
            </div>
            <div className="border-t border-slate-800 pt-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold"><MessageCircle size={13} /> Employee conversation</div>
              <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="mb-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs">
                {employees.filter((a) => a.id !== actorId).map((a) => <option key={a.id} value={a.id}>{a.display_name} · {a.department}</option>)}
              </select>
              <div className="flex gap-2">
                <input value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && message.trim()) void act('message', { target_agent_id: targetId, message: message.trim() }); }} placeholder="Send a message…" className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs outline-none focus:border-cyan-500" />
                <button disabled={busy || !message.trim() || !targetId} onClick={() => void act('message', { target_agent_id: targetId, message: message.trim() })} className="rounded-lg bg-cyan-500 px-3 text-slate-950 disabled:opacity-40"><Send size={14} /></button>
              </div>
            </div>
          </div>
        )}
        {tab === 'rooms' && (
          <div className="space-y-3">
            <div><div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">Choose a room</div>
              <div className="grid grid-cols-2 gap-2">{['Boardroom', 'Engineering', 'Design', 'Marketing', 'Research', 'Breakroom'].map((room) => <button key={room} onClick={() => setSelectedRoom(room)} className={`rounded-lg border px-2 py-2.5 text-left text-xs ${(selectedRoom || 'Boardroom') === room ? 'border-cyan-500 bg-cyan-500/10 text-cyan-200' : 'border-slate-800 bg-slate-900 text-slate-300'}`}>{room}<div className="mt-1 text-[10px] text-slate-500">{room === 'Boardroom' ? 'Formal meeting space' : room === 'Breakroom' ? 'Informal conversations' : 'Department workspace'}</div></button>)}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold"><Users size={13} /> {selectedRoom || 'Boardroom'} session</div>
              <div className="mb-3 text-[10px] text-slate-500">Host: {employees.find((a) => a.id === actorId)?.display_name || 'Select employee'}</div>
              <div className="grid grid-cols-4 gap-1.5">
                <button disabled={busy || !actorId || meetingActive} onClick={() => void act('meeting_start')} className="rounded-lg bg-emerald-500/15 px-2 py-2 text-[11px] text-emerald-300 disabled:opacity-40">Start</button>
                <button disabled={busy || !actorId || !meetingActive} onClick={() => void act('meeting_join')} className="rounded-lg bg-cyan-500/15 px-2 py-2 text-[11px] text-cyan-300 disabled:opacity-40">Join</button>
                <button disabled={busy || !actorId || !meetingActive} onClick={() => void act('meeting_leave')} className="rounded-lg bg-amber-500/15 px-2 py-2 text-[11px] text-amber-300 disabled:opacity-40">Leave</button>
                <button disabled={busy || !meetingActive} onClick={() => void act('meeting_end')} className="rounded-lg bg-rose-500/15 px-2 py-2 text-[11px] text-rose-300 disabled:opacity-40">End</button>
              </div>
            </div>
            <div className="border-t border-slate-800 pt-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold"><Workflow size={13} /> Task handoff</div>
              <select value={taskId} onChange={(e) => setTaskId(e.target.value)} className="mb-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs">
                <option value="">Select active task</option>{tasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}
              </select>
              <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="mb-2 w-full rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs">
                {employees.filter((a) => a.id !== actorId).map((a) => <option key={a.id} value={a.id}>{a.display_name} · {a.department}</option>)}
              </select>
              <button disabled={busy || !taskId || !targetId} onClick={() => void act('handoff', { target_agent_id: targetId, task_id: taskId })} className="w-full rounded-lg bg-cyan-500 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-40">Transfer task</button>
            </div>
          </div>
        )}
        {tab === 'timeline' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between"><div className="text-xs font-semibold">Office event replay</div><span className="text-[10px] text-slate-500">{chronologicalEvents.length} events</span></div>
            {selectedEvent ? <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-3">
              <div className="text-[10px] text-cyan-300">EVENT {selectedEvent.id} / {chronologicalEvents.length}</div>
              <div className="mt-1 text-xs">{eventLabel(selectedEvent)}</div>
              <div className="mt-1 text-[10px] text-slate-500">{new Date(selectedEvent.ts).toLocaleString()}</div>
            </div> : <div className="rounded-lg border border-slate-800 p-3 text-xs text-slate-500">No office events yet.</div>}
            <input aria-label="Timeline event" type="range" min={0} max={Math.max(0, chronologicalEvents.length - 1)} value={Math.min(timelineIndex, Math.max(0, chronologicalEvents.length - 1))} onChange={(e) => setTimelineIndex(Number(e.target.value))} className="w-full accent-cyan-400" />
            <div className="flex gap-2"><button disabled={!selectedEvent} onClick={() => replay(timelineIndex)} className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-cyan-500 px-3 py-2 text-xs font-semibold text-slate-950 disabled:opacity-40"><Play size={13} /> Replay event</button><button onClick={() => { setTimelineIndex(Math.max(0, chronologicalEvents.length - 1)); setReplayEvent(chronologicalEvents[chronologicalEvents.length - 1]?.id || null); }} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">Latest</button></div>
            <div className="max-h-48 space-y-1 overflow-y-auto">{chronologicalEvents.slice(-30).reverse().map((event, index) => <button key={event.id} onClick={() => replay(chronologicalEvents.length - 1 - index)} className={`w-full rounded-md px-2 py-2 text-left text-[10px] ${replayEventId === event.id ? 'bg-cyan-500/10 text-cyan-200' : 'text-slate-400 hover:bg-slate-900'}`}><span className="mr-2 text-slate-600">#{event.id}</span>{eventLabel(event)}</button>)}</div>
          </div>
        )}
        {feedback && <div role="status" className="mt-3 rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-2 text-[10px] text-slate-300">{feedback}</div>}
      </div>
    </section>
  );
};
