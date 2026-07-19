"use client";

import { useEffect, useState } from "react";

import { Empty, ErrorState, Loading } from "@/components/DataState";
import { api } from "@/lib/api";

type Model = {
  id: string;
  name: string;
  version: string;
  framework: string;
  input_resolution: string;
  class_list: string[];
  deployment_status: string;
  validation_metrics: Record<string, number>;
  safe_serialization: boolean;
};

type Deployment = {
  id: string;
  model_version_id: string;
  camera_id: string | null;
  edge_node_id: string | null;
  backend: string;
  status: string;
  deployed_at: string;
  rollback_of_id: string | null;
};

export default function Models() {
  const [models, setModels] = useState<Model[] | null>(null);
  const [deployments, setDeployments] = useState<Deployment[] | null>(null);
  const [targets, setTargets] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const [modelRows, deploymentRows] = await Promise.all([
        api<Model[]>("/api/v1/models"),
        api<Deployment[]>("/api/v1/model-deployments"),
      ]);
      setModels(modelRows);
      setDeployments(deploymentRows);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Model data could not be loaded");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function rollback(deployment: Deployment) {
    const target = targets[deployment.id];
    if (!target) return;
    setMessage("");
    try {
      await api(`/api/v1/model-deployments/${deployment.id}/rollback`, {
        method: "POST",
        body: JSON.stringify({
          target_model_version_id: target,
          reason: "Rollback requested through the model-governance console",
        }),
      });
      setMessage("Rollback deployment record created and prior assignment marked rolled back.");
      await load();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Rollback failed");
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!models || !deployments) return <Loading />;

  const modelById = new Map(models.map((model) => [model.id, model]));

  return (
    <div className="grid">
      <section className="panel">
        <h2>Model registry</h2>
        <p className="muted">
          Only classes explicitly supported by a registered model are exposed. Generic trucks
          are not relabeled as fuel trucks.
        </p>
        {models.length ? (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Framework</th>
                <th>Resolution</th>
                <th>Classes</th>
                <th>Status</th>
                <th>Serialization</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => (
                <tr key={model.id}>
                  <td>
                    {model.name}
                    <div className="muted">v{model.version}</div>
                  </td>
                  <td>{model.framework}</td>
                  <td>{model.input_resolution}</td>
                  <td>{model.class_list.join(", ")}</td>
                  <td>
                    <span className={`badge ${model.deployment_status}`}>
                      {model.deployment_status}
                    </span>
                  </td>
                  <td>{model.safe_serialization ? "Safe format" : "Requires isolated review"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="No models are registered." />
        )}
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Deployment and rollback history</h2>
          <span className="muted">{deployments.length} records</span>
        </div>
        {message ? <p className="muted">{message}</p> : null}
        {deployments.length ? (
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Target</th>
                <th>Backend</th>
                <th>Status</th>
                <th>Deployed</th>
                <th>Rollback</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((deployment) => {
                const model = modelById.get(deployment.model_version_id);
                return (
                  <tr key={deployment.id}>
                    <td>{model ? `${model.name} v${model.version}` : deployment.model_version_id}</td>
                    <td>{deployment.camera_id ?? deployment.edge_node_id ?? "unknown"}</td>
                    <td>{deployment.backend}</td>
                    <td>
                      <span className={`badge ${deployment.status}`}>{deployment.status}</span>
                    </td>
                    <td>{new Date(deployment.deployed_at).toLocaleString()}</td>
                    <td>
                      {deployment.status === "active" ? (
                        <div className="toolbar">
                          <select
                            value={targets[deployment.id] ?? ""}
                            onChange={(event) =>
                              setTargets((current) => ({
                                ...current,
                                [deployment.id]: event.target.value,
                              }))
                            }
                          >
                            <option value="">Select target</option>
                            {models
                              .filter(
                                (candidate) =>
                                  candidate.safe_serialization &&
                                  candidate.id !== deployment.model_version_id,
                              )
                              .map((candidate) => (
                                <option key={candidate.id} value={candidate.id}>
                                  {candidate.name} v{candidate.version}
                                </option>
                              ))}
                          </select>
                          <button
                            className="ghost-button"
                            disabled={!targets[deployment.id]}
                            onClick={() => void rollback(deployment)}
                          >
                            Roll back
                          </button>
                        </div>
                      ) : (
                        <span className="muted">
                          {deployment.rollback_of_id ? "Rollback replacement" : "No action"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <Empty message="No deployments have been recorded." />
        )}
      </section>
    </div>
  );
}
