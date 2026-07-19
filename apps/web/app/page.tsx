"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Empty, ErrorState, Loading } from "@/components/DataState";

type Dashboard = { kpis: Record<string, number>; alerts_by_severity: Record<string, number>; recent_alerts: Array<{id:string; severity:string; status:string; timestamp_seconds:number; confidence:number}>; recent_jobs:Array<{id:string;status:string;progress:number;detector_backend:string}>; aviation_disclaimer:string };

export default function Page() {
  const [data,setData]=useState<Dashboard|null>(null); const [error,setError]=useState("");
  useEffect(()=>{api<Dashboard>("/api/v1/dashboard").then(setData).catch(e=>setError(e.message))},[]);
  if(error) return <ErrorState message={error}/>; if(!data) return <Loading/>;
  const cards=[['Active turnarounds',data.kpis.active_turnarounds],['Active alerts',data.kpis.active_alerts],['High severity',data.kpis.high_severity_alerts],['Cameras degraded',data.kpis.offline_or_degraded_cameras],['Jobs in flight',data.kpis.processing_jobs_in_flight]];
  return <><div className="grid kpi-grid">{cards.map(([label,value])=><div className={`panel kpi ${String(label).includes('alert')||String(label).includes('severity')?'alert':''}`} key={String(label)}><div className="label">{label}</div><div className="value">{value}</div></div>)}</div><div className="grid two-col section"><section className="panel"><div className="section-head"><h2>Recent safety alerts</h2><Link className="table-link" href="/alerts">Open alert center →</Link></div>{data.recent_alerts.length?<table><thead><tr><th>Severity</th><th>Status</th><th>Video time</th><th>Confidence</th></tr></thead><tbody>{data.recent_alerts.map(x=><tr key={x.id}><td><span className={`badge ${x.severity}`}>{x.severity}</span></td><td>{x.status}</td><td>{x.timestamp_seconds.toFixed(1)}s</td><td>{Math.round(x.confidence*100)}%</td></tr>)}</tbody></table>:<Empty message="No alerts have been generated from processed video."/>}</section><section className="panel"><h2>Processing queue</h2>{data.recent_jobs.length?<div className="grid">{data.recent_jobs.map(job=><div key={job.id} className="panel"><div className="section-head"><span>{job.detector_backend}</span><span className={`badge ${job.status}`}>{job.status}</span></div><div className="muted">{Math.round(job.progress*100)}% complete</div></div>)}</div>:<Empty message="No processing jobs yet."/>}</section></div><div className="disclaimer">{data.aviation_disclaimer}</div></>;
}
