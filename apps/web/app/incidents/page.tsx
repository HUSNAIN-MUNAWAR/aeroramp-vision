"use client";

import { useEffect, useState } from "react";

import { Empty, ErrorState, Loading } from "@/components/DataState";
import { SecureMedia } from "@/components/SecureMedia";
import { api } from "@/lib/api";

type Incident = {
  id: string;
  alert_id: string;
  title: string;
  severity: string;
  status: string;
  assigned_to_id: string | null;
  classification: string | null;
  resolution: string | null;
  created_at: string;
  updated_at: string;
};

type IncidentNote = {
  id: string;
  author_id: string;
  body: string;
  created_at: string;
};

type Detail = { incident: Incident; notes: IncidentNote[] };

export default function Incidents() {
  const [items, setItems] = useState<Incident[] | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [note, setNote] = useState("");
  const [classification, setClassification] = useState("");
  const [resolution, setResolution] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      setItems(await api<Incident[]>("/api/v1/incidents"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Incidents could not be loaded");
    }
  }

  async function openIncident(id: string) {
    setMessage("");
    const next = await api<Detail>(`/api/v1/incidents/${id}`);
    setDetail(next);
    setClassification(next.incident.classification ?? "");
    setResolution(next.incident.resolution ?? "");
  }

  useEffect(() => {
    void load();
  }, []);

  async function addNote() {
    if (!detail || !note.trim()) return;
    try {
      await api(`/api/v1/incidents/${detail.incident.id}/notes`, {
        method: "POST",
        body: JSON.stringify({ body: note.trim() }),
      });
      setNote("");
      await openIncident(detail.incident.id);
      setMessage("Investigation note added and audited.");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Note could not be saved");
    }
  }

  async function save(status: "under_review" | "resolved" | "false_positive") {
    if (!detail) return;
    try {
      await api(`/api/v1/incidents/${detail.incident.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          classification: classification || null,
          resolution: resolution || null,
        }),
      });
      await Promise.all([load(), openIncident(detail.incident.id)]);
      setMessage(`Incident marked ${status.replaceAll("_", " ")}.`);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Incident could not be updated");
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!items) return <Loading />;

  return (
    <div className="grid two-col">
      <section className="panel">
        <div className="section-head">
          <h2>Incident register</h2>
          <span className="muted">{items.length} records</span>
        </div>
        {items.length ? (
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Title</th>
                <th>Status</th>
                <th>Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((incident) => (
                <tr key={incident.id}>
                  <td>
                    <span className={`badge ${incident.severity}`}>{incident.severity}</span>
                  </td>
                  <td>{incident.title}</td>
                  <td>{incident.status}</td>
                  <td>{new Date(incident.updated_at).toLocaleString()}</td>
                  <td>
                    <button
                      className="ghost-button"
                      onClick={() => void openIncident(incident.id)}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="No incidents have been escalated." />
        )}
      </section>

      <aside className="panel">
        <h2>Investigation workspace</h2>
        {message ? <p className="muted">{message}</p> : null}
        {detail ? (
          <div className="grid">
            <div>
              <span className={`badge ${detail.incident.severity}`}>
                {detail.incident.severity}
              </span>{" "}
              <span className={`badge ${detail.incident.status}`}>
                {detail.incident.status}
              </span>
            </div>
            <h3>{detail.incident.title}</h3>
            <SecureMedia kind="image" path={`/api/v1/evidence/${detail.incident.alert_id}/snapshot`} />
            <SecureMedia kind="video" path={`/api/v1/evidence/${detail.incident.alert_id}/clip`} />
            <label>
              Classification
              <input
                value={classification}
                onChange={(event) => setClassification(event.target.value)}
                placeholder="confirmed event, operational deviation, test fixture..."
              />
            </label>
            <label>
              Resolution
              <textarea
                value={resolution}
                onChange={(event) => setResolution(event.target.value)}
                placeholder="Record the evidence-based resolution"
              />
            </label>
            <div className="toolbar">
              <button className="ghost-button" onClick={() => void save("under_review")}>
                Start review
              </button>
              <button className="primary-button" onClick={() => void save("resolved")}>
                Resolve
              </button>
              <button className="danger-button" onClick={() => void save("false_positive")}>
                False positive
              </button>
            </div>
            <h3>Notes</h3>
            {detail.notes.length ? (
              detail.notes.map((item) => (
                <div className="card" key={item.id}>
                  <div>{item.body}</div>
                  <div className="muted">{new Date(item.created_at).toLocaleString()}</div>
                </div>
              ))
            ) : (
              <Empty message="No investigation notes have been added." />
            )}
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Add an evidence-based investigation note"
            />
            <button className="ghost-button" disabled={!note.trim()} onClick={() => void addNote()}>
              Add note
            </button>
          </div>
        ) : (
          <Empty message="Open an incident to review evidence, notes, classification and resolution." />
        )}
      </aside>
    </div>
  );
}
