"use client";

import { MouseEvent, useEffect, useMemo, useState } from "react";
import { Empty, ErrorState, Loading } from "@/components/DataState";
import { api } from "@/lib/api";

type Camera = {
  id: string;
  name: string;
  status: string;
  calibration_state: string;
  resolution_width: number;
  resolution_height: number;
  stand_id?: string;
};

type Zone = {
  id: string;
  camera_id: string;
  name: string;
  zone_type: string;
  polygon: number[][];
  severity: string;
  forbidden_classes: string[];
  rule_configuration: Record<string, unknown>;
  version: number;
};

type Rule = {
  id: string;
  camera_id: string;
  zone_id?: string;
  name: string;
  rule_type: string;
  severity: string;
  debounce_seconds: number;
  cooldown_seconds: number;
};

const zoneOptions = [
  ["restricted_zone", "Restricted zone"],
  ["aircraft_safety_envelope", "Aircraft safety envelope"],
  ["pushback_path", "Pushback path"],
  ["service_zone", "Service zone"],
  ["vehicle_lane", "Vehicle lane"],
  ["personnel_walkway", "Personnel walkway"],
  ["emergency_access_route", "Emergency access route"],
  ["privacy_mask", "Privacy mask"],
  ["ignore_zone", "Ignore zone"],
] as const;

const ruleByZone: Record<string, string | undefined> = {
  restricted_zone: "person_in_restricted_zone",
  pushback_path: "pushback_path_obstruction",
  service_zone: "equipment_left_behind",
  vehicle_lane: "wrong_way_movement",
};

function splitClasses(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function Cameras() {
  const [cameras, setCameras] = useState<Camera[] | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [selected, setSelected] = useState<string>();
  const [points, setPoints] = useState<number[][]>([]);
  const [name, setName] = useState("Review Zone");
  const [zoneType, setZoneType] = useState("restricted_zone");
  const [severity, setSeverity] = useState("medium");
  const [forbiddenClasses, setForbiddenClasses] = useState("person, moving_object");
  const [minimumPresence, setMinimumPresence] = useState(1);
  const [createRule, setCreateRule] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const selectedCamera = useMemo(
    () => cameras?.find((camera) => camera.id === selected),
    [cameras, selected],
  );

  useEffect(() => {
    api<Camera[]>("/api/v1/cameras")
      .then((data) => {
        setCameras(data);
        if (data[0]) setSelected(data[0].id);
      })
      .catch((caught: Error) => setError(caught.message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    Promise.all([
      api<Zone[]>(`/api/v1/zones?camera_id=${selected}`),
      api<Rule[]>(`/api/v1/safety-rules?camera_id=${selected}`),
    ])
      .then(([zoneData, ruleData]) => {
        setZones(zoneData);
        setRules(ruleData);
      })
      .catch((caught: Error) => setError(caught.message));
  }, [selected]);

  function addPoint(event: MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const width = selectedCamera?.resolution_width || 640;
    const height = selectedCamera?.resolution_height || 360;
    setPoints((current) => [
      ...current,
      [
        ((event.clientX - rect.left) / rect.width) * width,
        ((event.clientY - rect.top) / rect.height) * height,
      ],
    ]);
  }

  async function save() {
    if (!selected || points.length < 3 || !name.trim()) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const forbidden = splitClasses(forbiddenClasses);
      const zone = await api<Zone>("/api/v1/zones", {
        method: "POST",
        body: JSON.stringify({
          camera_id: selected,
          stand_id: selectedCamera?.stand_id || null,
          name: name.trim(),
          zone_type: zoneType,
          polygon: points,
          severity,
          forbidden_classes: forbidden,
          rule_configuration: { minimum_presence_seconds: minimumPresence },
        }),
      });

      const ruleType = ruleByZone[zoneType];
      if (createRule && ruleType) {
        await api<Rule>("/api/v1/safety-rules", {
          method: "POST",
          body: JSON.stringify({
            camera_id: selected,
            zone_id: zone.id,
            name: `${name.trim()} rule`,
            rule_type: ruleType,
            severity,
            debounce_seconds: minimumPresence,
            cooldown_seconds: 15,
            config: {
              forbidden_classes: forbidden,
              minimum_presence_seconds: minimumPresence,
            },
          }),
        });
      }

      const [zoneData, ruleData] = await Promise.all([
        api<Zone[]>(`/api/v1/zones?camera_id=${selected}`),
        api<Rule[]>(`/api/v1/safety-rules?camera_id=${selected}`),
      ]);
      setZones(zoneData);
      setRules(ruleData);
      setPoints([]);
      setNotice(
        createRule && ruleType
          ? "Zone and linked safety rule saved."
          : "Zone saved without an automatic safety rule.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save the zone.");
    } finally {
      setBusy(false);
    }
  }

  if (!cameras) return <Loading />;

  return (
    <div className="grid two-col">
      <section className="panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">Configuration</p>
            <h2>Camera inventory</h2>
          </div>
          <span className="badge">{cameras.length} cameras</span>
        </div>
        {cameras.length ? (
          <div className="grid">
            {cameras.map((camera) => (
              <button
                key={camera.id}
                className={`panel camera-choice ${selected === camera.id ? "selected" : ""}`}
                onClick={() => {
                  setSelected(camera.id);
                  setPoints([]);
                  setNotice("");
                }}
              >
                <div className="section-head">
                  <strong>{camera.name}</strong>
                  <span className={`badge ${camera.status}`}>{camera.status}</span>
                </div>
                <div className="muted">
                  {camera.resolution_width}×{camera.resolution_height} · {camera.calibration_state}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <Empty message="No cameras configured." />
        )}
      </section>

      <section className="panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">Image-space calibration</p>
            <h2>Zone and rule editor</h2>
          </div>
          <button className="ghost-button" onClick={() => setPoints([])} disabled={!points.length}>
            Clear draft
          </button>
        </div>
        <p className="muted">
          Click the reference canvas to add polygon vertices. Coordinates are scaled to the selected
          camera resolution. Metric speed or distance still requires a validated homography.
        </p>

        <svg
          viewBox={`0 0 ${selectedCamera?.resolution_width || 640} ${selectedCamera?.resolution_height || 360}`}
          className="zone-canvas"
          onClick={addPoint}
          role="img"
          aria-label="Camera reference canvas for drawing safety and privacy zones"
        >
          <rect
            x="0"
            y="0"
            width={selectedCamera?.resolution_width || 640}
            height={selectedCamera?.resolution_height || 360}
            className="canvas-background"
          />
          {zones.map((zone) => (
            <polygon
              key={zone.id}
              className={`zone-shape ${zone.zone_type}`}
              points={zone.polygon.map((point) => point.join(",")).join(" ")}
            />
          ))}
          {points.length > 1 && (
            <polyline
              points={points.map((point) => point.join(",")).join(" ")}
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
            />
          )}
          {points.map((point, index) => (
            <circle key={`${point[0]}-${point[1]}-${index}`} cx={point[0]} cy={point[1]} r="6" />
          ))}
        </svg>

        <div className="form-grid section">
          <label>
            Zone name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Zone type
            <select value={zoneType} onChange={(event) => setZoneType(event.target.value)}>
              {zoneOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Severity
            <select value={severity} onChange={(event) => setSeverity(event.target.value)}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </label>
          <label>
            Forbidden classes
            <input
              value={forbiddenClasses}
              onChange={(event) => setForbiddenClasses(event.target.value)}
              placeholder="person, moving_object"
            />
          </label>
          <label>
            Minimum presence (seconds)
            <input
              type="number"
              min="0"
              step="0.25"
              value={minimumPresence}
              onChange={(event) => setMinimumPresence(Number(event.target.value))}
            />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={createRule}
              onChange={(event) => setCreateRule(event.target.checked)}
              disabled={!ruleByZone[zoneType]}
            />
            Create linked rule when supported
          </label>
        </div>

        {notice && <p className="success-note">{notice}</p>}
        {error && <ErrorState message={error} />}
        <button
          className="primary-button"
          disabled={busy || points.length < 3 || !selected || !name.trim()}
          onClick={save}
        >
          {busy ? "Saving…" : `Save ${zoneOptions.find(([value]) => value === zoneType)?.[1] || "zone"}`}
        </button>

        <div className="section">
          <div className="section-head">
            <h3>Active configuration</h3>
            <span className="muted">{zones.length} zones · {rules.length} rules</span>
          </div>
          {zones.length ? (
            <div className="config-list">
              {zones.map((zone) => {
                const linkedRule = rules.find((rule) => rule.zone_id === zone.id);
                return (
                  <article key={zone.id} className="config-row">
                    <div>
                      <strong>{zone.name}</strong>
                      <div className="muted">
                        {zone.zone_type.replaceAll("_", " ")} · version {zone.version} · {zone.polygon.length} points
                      </div>
                    </div>
                    <div className="config-badges">
                      <span className={`badge ${zone.severity}`}>{zone.severity}</span>
                      <span className={`badge ${linkedRule ? "active" : ""}`}>
                        {linkedRule ? linkedRule.rule_type.replaceAll("_", " ") : "zone only"}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <Empty message="No active zones for this camera." />
          )}
        </div>
      </section>
    </div>
  );
}
