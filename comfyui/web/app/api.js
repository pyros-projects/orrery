// Thin client for the /orrery/* routes. Errors carry the server's sentence and status.
import { api } from "../../../scripts/api.js";

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export function client(home) {
  const withHome = (query = {}) => {
    const q = new URLSearchParams({ ...query, ...(home() ? { home: home() } : {}) });
    return q.toString() ? `?${q}` : "";
  };
  async function call(path, { query, body } = {}) {
    const init = body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...body, ...(home() ? { home: home() } : {}) }),
    };
    const res = await api.fetchApi(`/orrery/${path}${withHome(query)}`, init);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(data.error || `orrery: ${path} failed (${res.status})`, res.status, data);
    return data;
  }
  const url = (path, query) => api.apiURL(`/orrery/${path}${withHome(query)}`);
  return {
    completions: () => call("completions"),
    presets: () => call("presets"),
    preset: (name) => call("preset", { query: { name } }),
    savePreset: (body) => call("preset/save", { body }),
    deletePreset: (name) => call("preset/delete", { body: { name } }),
    favorite: (name, on) => call("favorite", { body: { name, on } }),
    recent: (name) => call("recent", { body: { name } }),
    template: (hash) => call("template", { query: { hash } }),
    libraries: () => call("libraries"),
    saveLibrary: (body) => call("library/save", { body }),
    ownLibrary: (name) => call("library/own", { body: { name } }),
    deleteLibrary: (name) => call("library/delete", { body: { name } }),
    renameLibrary: (name, to) => call("library/rename", { body: { name, to } }),
    acceptLibrary: (name) => call("library/accept", { body: { name } }),
    discardLibrary: (name) => call("library/discard", { body: { name } }),
    galaxy: (query = {}) => call("galaxy", { query }),
    rate: (id, rating) => call("galaxy/rate", { body: { id, rating } }),
    roll: (body) => call("roll", { body }),
    frequency: (body) => call("frequency", { body }),
    homeFolder: () => call("home"),
    saveHomeFolder: (path) => call("home", { body: { path } }),
    llm: () => call("llm"),
    saveLlm: (body) => call("llm", { body }),
    thumbURL: (id) => url("galaxy/thumb", { id }),
    onRunDone: (fn) => { api.addEventListener("execution_success", fn); return () => api.removeEventListener("execution_success", fn); },
    onExecuted: (fn) => { api.addEventListener("executed", fn); return () => api.removeEventListener("executed", fn); },
    captureOutputs: (body) => call("galaxy/capture", { body }),
    mediaURL: (id) => url("galaxy/media", { id }),
  };
}
