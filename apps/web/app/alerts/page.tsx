"use client";

import { useEffect, useState } from "react";

import { Empty, ErrorState, Loading } from "@/components/DataState";
import { SecureMedia } from "@/components/SecureMedia";
import { api } from "@/lib/api";

type Alert = {
  id: string;
  severity: string;
  status: string;
  timestamp_seconds: number;
  confidence: number;
  event_metadata: Record<string, unknown>;
  review_notes?: string | null;
};

type Incident = { id: string; title: string; status: string };

export default function Alerts() {
  const [items, setItems] = useState<Alert[] | null>(null);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [selected, setSelected] = useState<Alert | null>(null);

  const load = () =>
    api<Alert[]>("/api/v1/alerts")
      .then(setItems)
      .catch((caught: Error) => setError(caught.message));

  useEffect(() => {
    void load();
  }, []);

  async function review(status: string) {
    if (!selected) return;
    setActionMessage("");
    try {
      await api(`/api/v1/alerts/${selected.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status,
          notes: `Reviewed in operations console: ${status}`,
          resolution_reason:
            status === "false_positive"
              ? "Human review determined the candidate was not a reportable event"
              : null,
        }),
      });
      setActionMessage(`Alert marked ${status.replaceAll("_", " ")}.`);
      setSelected(null);
      await load();
    } catch (caught) {
      setActionMessage(caught instanceof Error ? caught.message : "Review action failed");
    }
  }

  async function escalate() {
    if (!selected) return;
    setActionMessage("");
    try {
      const incident = await api<Incident>("/api/v1/incidents", {
        method: "POST",
        body: JSON.stringify({
          alert_id: selected.id,
          title: `Ramp-safety review at ${selected.timestamp_seconds.toFixed(1)}s`,
          severity: selected.severity,
        }),
      });
      setActionMessage(`Incident created: ${incident.title}`);
      await load();
    } catch (caught) {
      setActionMessage(caught instanceof Error ? caught.message : "Incident escalation failed");
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!items) return <Loading />;

  return (
    <div className="grid two-col">
      <section className="panel">
        <div className="section-head">
          <h2>Alert queue</h2>
          <span className="muted">{items.length} records</span>
        </div>
        {actionMessage ? <p className="muted">{actionMessage}</p> : null}
        {items.length ? (
          <table>
            <thead>
              <tr>
                <th>Severity</th>
                <th>Status</th>
                <th>Time</th>
                <th>Confidence</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((alert) => (
                <tr key={alert.id}>
                  <td>
                    <span className={`badge ${alert.severity}`}>{alert.severity}</span>
                  </td>
                  <td>{alert.status}</td>
                  <td>{alert.timestamp_seconds.toFixed(1)}s</td>
                  <td>{Math.round(alert.confidence * 100)}%</td>
                  <td>
                    <button className="ghost-button" onClick={() => setSelected(alert)}>
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="No alerts are available." />
        )}
      </section>

      <aside className="panel">
        <h2>Incident review</h2>
        {selected ? (
          <div className="grid">
            <SecureMedia kind="image" path={`/api/v1/evidence/${selected.id}/snapshot`} />
            <SecureMedia kind="video" path={`/api/v1/evidence/${selected.id}/clip`} />
            <div>
              <span className={`badge ${selected.severity}`}>{selected.severity}</span>{" "}
              <span className={`badge ${selected.status}`}>{selected.status}</span>
            </div>
            <p className="muted">
              This is a vision-generated candidate requiring human review. It is not a
              definitive safety determination.
            </p>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
              {JSON.stringify(selected.event_metadata, null, 2)}
            </pre>
            <div className="toolbar">
              <button className="primary-button" onClick={() => void review("confirmed")}>
                Confirm
              </button>
              <button className="ghost-button" onClick={() => void review("acknowledged")}>
                Acknowledge
              </button>
              <button className="ghost-button" onClick={() => void escalate()}>
                Escalate incident
              </button>
              <button className="danger-button" onClick={() => void review("false_positive")}>
                False positive
              </button>
            </div>
          </div>
        ) : (
          <Empty message="Select an alert to review synchronized evidence and record a decision." />
        )}
      </aside>
    </div>
  );
}
