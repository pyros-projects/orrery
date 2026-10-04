// Local language models, one task per run (#171): a text encoder in ComfyUI answers once per run, and a small model
// does better with one task at a time. So with one, the language model's work of a run goes into mini-runs before
// it, one task each (Orrery Ask): Roll asks the server for the run's tasks and queues them ahead of it, and the run
// takes their answers. Write now (#176) and the takes at the line (#178) queue theirs at the queue's front.

// Whether the language model is a text encoder in ComfyUI: chosen in the gear, or wired into the node's clip (an
// API endpoint wins over both).
export function llmLocal(app) {
  return !app.llmApi() && (app.data.llm?.active?.kind === "comfy" || !!app.bridge.wired?.("clip"));
}

// Before each run Generate queues: a mini-run for each of its tasks, in the server's order (libraries, the rewrites,
// each slot). When the plan cannot be had, the run asks in itself, as before.
export async function queueTasks(app) {
  if (!llmLocal(app)) return 0;
  const b = app.bridge;
  let tasks;
  try {
    ({ tasks } = await app.api.plan({ template: b.getText(), target: b.getTarget(), params: b.getParams(),
      seed: Number(b.getSeed()) || 0, segment: Number(b.getSegment?.() ?? 0) || 0, sweep: b.getSweep?.() || "" }));
  } catch { return 0; }
  for (const t of tasks) await b.ask(t.task, t.what, "", { wait: false });
  return tasks.length;
}
