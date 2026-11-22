// Live view of the global build job (see ctx.build in main.js) — the job
// itself survives navigating away from this page; this is just its display.
export function renderBuildPage(container, ctx) {
  const requestedRoot = ctx.params.get('root') || ctx.build.state.root || ''

  container.innerHTML = `
    <div class="gide__page">
      <div class="gide__page-toolbar">
        <select id="build-root-select"><option value="">loading apps…</option></select>
        <input type="text" id="build-output-dir" placeholder="output dir (optional — default: writes next to the app's own graph.yaml)" />
        <button id="build-start-btn">Build</button>
        <button id="build-cancel-btn" disabled>Cancel</button>
        <span class="gide__page-status" id="build-status"></span>
      </div>
      <pre class="gide__log" id="build-log">(no build run yet)</pre>
    </div>
  `

  const rootSelect = container.querySelector('#build-root-select')
  const outputDirInput = container.querySelector('#build-output-dir')
  const startBtn = container.querySelector('#build-start-btn')
  const cancelBtn = container.querySelector('#build-cancel-btn')
  const statusEl = container.querySelector('#build-status')
  const logEl = container.querySelector('#build-log')

  async function loadRoots() {
    try {
      const res = await fetch('/api/graphs/roots')
      if (!res.ok) throw new Error(res.statusText)
      const roots = await res.json()
      rootSelect.innerHTML = roots.map(r => `<option value="${r}">${r}</option>`).join('')
      if (requestedRoot && roots.includes(requestedRoot)) rootSelect.value = requestedRoot
    } catch (err) {
      rootSelect.innerHTML = `<option value="">error: ${err.message}</option>`
    }
  }
  loadRoots()

  function render(state) {
    const label = {
      idle: 'idle — pick an app and click Build',
      running: `building ${state.root}…`,
      done: `build ok — ${state.root}`,
      error: `build failed (exit ${state.returncode}) — ${state.root}`,
    }[state.status]
    statusEl.textContent = label
    logEl.textContent = state.output || '(no output yet)'
    logEl.scrollTop = logEl.scrollHeight
    startBtn.disabled = state.status === 'running'
    cancelBtn.disabled = state.status !== 'running'
  }
  render(ctx.build.state)
  ctx.build.subscribe(render)

  startBtn.addEventListener('click', () => {
    const root = rootSelect.value
    if (!root) return
    ctx.build.start(root, outputDirInput.value.trim())
  })
  cancelBtn.addEventListener('click', () => ctx.build.cancel())

  return () => ctx.build.unsubscribe(render)
}
