import React, { useEffect, useMemo, useState } from "react";
import { Download, Search, ChevronLeft, ChevronRight, Loader2, ExternalLink } from "lucide-react";

type EventItem = { EventCode: string; Gender?: string; Discipline?: string; Age?: string };
type RankingRow = {
  EventCode: string;
  Rank: number;
  PlayerID: number;
  FirstName: string;
  LastName: string;
  TotalPoints: number;
  SelectedTop4Vector: number[];
  MostRecentDate?: string;
  CountedTournaments: number;
};
type RankingsResp = { event: string; count: number; items: RankingRow[]; last_evaluated_key?: any };
type ResultRow = {
  PlayerEvent: string;
  TournamentName: string;
  TournamentType?: string;
  FinishingPosition?: string;
  PositionPoints?: number;
  TournamentEndDate?: string;
  InWindow?: boolean;
  PlayerID: number;
  EventCode: string;
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8008";

const formatName = (r: RankingRow) => `${r.LastName || ""}, ${r.FirstName || ""}`.replace(/^,\s*/, "");
const fmt = (n?: number) => (typeof n === "number" ? n.toLocaleString() : "");
const cls = (...s: (string | false | null | undefined)[]) => s.filter(Boolean).join(" ");

export default function App() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventCode, setEventCode] = useState<string>("");
  const [loadingEvents, setLoadingEvents] = useState<boolean>(false);

  const [pageSize, setPageSize] = useState<number>(50);
  const [startRank, setStartRank] = useState<number>(1);
  const [rankings, setRankings] = useState<RankingRow[]>([]);
  const [loadingRanks, setLoadingRanks] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const [q, setQ] = useState<string>("");

  const [drawer, setDrawer] = useState<{ open: boolean; player?: { id: number; name: string } }>({ open: false });
  const [playerResults, setPlayerResults] = useState<ResultRow[] | null>(null);
  const [loadingResults, setLoadingResults] = useState<boolean>(false);

  useEffect(() => {
    const load = async () => {
      setLoadingEvents(true);
      try {
        const r = await fetch(`${API_BASE}/events`);
        const items: EventItem[] = await r.json();
        items.sort((a, b) => (a.EventCode || "").localeCompare(b.EventCode || ""));
        setEvents(items);
        if (!eventCode && items.length) setEventCode(items[0].EventCode);
      } catch (e: any) {
        console.error(e);
      } finally {
        setLoadingEvents(false);
      }
    };
    load();
  }, []);

  useEffect(() => {
    if (!eventCode) return;
    const load = async () => {
      setLoadingRanks(true);
      setError("");
      try {
        const url = new URL(`${API_BASE}/rankings`);
        url.searchParams.set("event", eventCode);
        url.searchParams.set("limit", String(pageSize));
        url.searchParams.set("start_rank", String(startRank));
        const r = await fetch(url.toString());
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        const data: RankingsResp = await r.json();
        setRankings(data.items || []);
      } catch (e: any) {
        console.error(e);
        setError(e.message || "Failed to load rankings");
      } finally {
        setLoadingRanks(false);
      }
    };
    load();
  }, [eventCode, pageSize, startRank]);

  const filtered = useMemo(() => {
    if (!q.trim()) return rankings;
    const needle = q.trim().toLowerCase();
    return rankings.filter((r) => formatName(r).toLowerCase().includes(needle));
  }, [q, rankings]);

  const nextPage = () => setStartRank((r) => r + pageSize);
  const prevPage = () => setStartRank((r) => Math.max(1, r - pageSize));

  const openPlayer = async (row: RankingRow) => {
    setDrawer({ open: true, player: { id: row.PlayerID, name: formatName(row) } });
    setPlayerResults(null);
    setLoadingResults(true);
    try {
      const url = new URL(`${API_BASE}/player-results`);
      url.searchParams.set("playerId", String(row.PlayerID));
      url.searchParams.set("event", eventCode);
      url.searchParams.set("limit", "500");
      const r = await fetch(url.toString());
      const data = await r.json();
      setPlayerResults(data.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingResults(false);
    }
  };

  const exportCsv = () => {
    const a = document.createElement("a");
    a.href = `${API_BASE}/events/${encodeURIComponent(eventCode)}/export.csv`;
    a.setAttribute("download", `${eventCode.replace(/\s+/g, "_")}_rankings.csv`);
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="min-h-full bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-7xl p-4 flex items-center gap-3">
          <div className="rounded-xl bg-indigo-600 text-white px-3 py-1 text-sm font-semibold">USAB</div>
          <h1 className="text-xl font-semibold">Junior Rankings</h1>
          <div className="ml-auto flex items-center gap-2">
            <a className="text-sm text-slate-500 hover:text-slate-700 inline-flex items-center gap-1"
               href={`${API_BASE}/health`} target="_blank" rel="noreferrer">
              API <ExternalLink size={14}/>
            </a>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="col-span-1">
          <label className="block text-xs font-medium text-slate-500 mb-1">Event</label>
          <div className="relative">
            <select
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              value={eventCode} onChange={(e) => { setEventCode(e.target.value); setStartRank(1); }}>
              {loadingEvents && <option>Loading…</option>}
              {!loadingEvents && events.map(ev => (
                <option key={ev.EventCode} value={ev.EventCode}>{ev.EventCode}</option>
              ))}
            </select>
            {loadingEvents && <Loader2 className="absolute right-3 top-2.5 animate-spin text-slate-400" size={18} />}
          </div>
        </div>

        <div className="col-span-1">
          <label className="block text-xs font-medium text-slate-500 mb-1">Search on this page</label>
          <div className="relative">
            <input
              className="w-full rounded-xl border border-slate-300 bg-white px-9 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Type a name…"
              value={q} onChange={(e) => setQ(e.target.value)}
            />
            <Search className="absolute left-3 top-2.5 text-slate-400" size={18}/>
          </div>
        </div>

        <div className="col-span-1 flex items-end gap-2">
          <button
            onClick={prevPage}
            className="inline-flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-2 hover:bg-slate-100 disabled:opacity-50"
            disabled={startRank === 1 || loadingRanks}>
            <ChevronLeft size={16}/> Prev
          </button>
          <button
            onClick={nextPage}
            className="inline-flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-2 hover:bg-slate-100 disabled:opacity-50"
            disabled={loadingRanks || rankings.length < pageSize}>
            Next <ChevronRight size={16}/>
          </button>

          <select
            className="ml-auto rounded-xl border border-slate-300 bg-white px-3 py-2"
            value={pageSize} onChange={(e) => { setPageSize(parseInt(e.target.value)); setStartRank(1); }}>
            {[25,50,100].map(n => <option key={n} value={n}>{n} / page</option>)}
          </select>

          <button
            onClick={exportCsv}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 text-white px-4 py-2 hover:bg-indigo-700">
            <Download size={16}/> Export CSV
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-7xl p-4">
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-600 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left">Rank</th>
                  <th className="px-3 py-2 text-left">Player</th>
                  <th className="px-3 py-2 text-right">Total</th>
                  <th className="px-3 py-2 text-left">Top-4</th>
                  <th className="px-3 py-2 text-left">Recent</th>
                  <th className="px-3 py-2 text-right">Cnt</th>
                </tr>
              </thead>
              <tbody>
                {loadingRanks && (
                  <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-500">
                    <Loader2 className="inline-block animate-spin mr-2" /> Loading rankings…
                  </td></tr>
                )}
                {!loadingRanks && error && (
                  <tr><td colSpan={6} className="px-3 py-6 text-center text-red-600">{error}</td></tr>
                )}
                {!loadingRanks && !error && filtered.length === 0 && (
                  <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-500">No rows.</td></tr>
                )}
                {!loadingRanks && !error && filtered.map((r) => (
                  <tr key={`${r.EventCode}-${r.Rank}-${r.PlayerID}`}
                      className="hover:bg-indigo-50 cursor-pointer"
                      onClick={() => openPlayer(r)}>
                    <td className="px-3 py-2">{r.Rank}</td>
                    <td className="px-3 py-2">{formatName(r)}</td>
                    <td className="px-3 py-2 text-right font-medium">{fmt(r.TotalPoints)}</td>
                    <td className="px-3 py-2">
                      {r.SelectedTop4Vector?.length
                        ? r.SelectedTop4Vector.map((p, i) => (
                            <span key={i} className={cls("inline-block mr-1 px-2 py-0.5 rounded-full",
                              i===0 && "bg-emerald-100 text-emerald-800",
                              i===1 && "bg-blue-100 text-blue-800",
                              i===2 && "bg-violet-100 text-violet-800",
                              i===3 && "bg-amber-100 text-amber-800"
                            )}>{fmt(p)}</span>
                          ))
                        : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-3 py-2">{r.MostRecentDate || ""}</td>
                    <td className="px-3 py-2 text-right">{r.CountedTournaments}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between px-3 py-2 border-t bg-slate-50">
            <div className="text-xs text-slate-500">Event: <span className="font-medium">{eventCode || "—"}</span></div>
            <div className="text-xs text-slate-500">Page starting at rank {startRank}</div>
          </div>
        </div>
      </div>

      {drawer.open && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDrawer({ open: false })}/>
          <div className="absolute right-0 top-0 h-full w-full sm:w-[520px] bg-white shadow-2xl p-4 overflow-auto">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-semibold">Player Results</h2>
              <button className="text-slate-500 hover:text-slate-700" onClick={() => setDrawer({ open: false })}>Close</button>
            </div>
            <div className="text-sm text-slate-600 mb-4">
              <div><span className="font-medium">Player:</span> {drawer.player?.name}</div>
              <div><span className="font-medium">Event:</span> {eventCode}</div>
            </div>

            {loadingResults && <div className="text-slate-500"><Loader2 className="inline-block animate-spin mr-2"/> Loading…</div>}
            {!loadingResults && playerResults && playerResults.length === 0 && <div className="text-slate-500">No results.</div>}
            {!loadingResults && playerResults && playerResults.length > 0 && (
              <div className="overflow-hidden rounded-xl border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="px-3 py-2 text-left">Tournament</th>
                      <th className="px-3 py-2 text-left">Type</th>
                      <th className="px-3 py-2 text-left">Finish</th>
                      <th className="px-3 py-2 text-right">Points</th>
                      <th className="px-3 py-2 text-left">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {playerResults.map((it) => (
                      <tr key={`${it.PlayerEvent}-${it.TournamentName}`} className="hover:bg-slate-50">
                        <td className="px-3 py-2">{it.TournamentName}</td>
                        <td className="px-3 py-2">{it.TournamentType || ""}</td>
                        <td className="px-3 py-2">{it.FinishingPosition || ""}</td>
                        <td className="px-3 py-2 text-right">{fmt(it.PositionPoints)}</td>
                        <td className="px-3 py-2">{it.TournamentEndDate || ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
