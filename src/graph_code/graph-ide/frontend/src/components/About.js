const LEGEND = [
  { label: 'primitive', color: '#795548' },
  { label: 'concept', color: '#2e7d32' },
  { label: 'module', color: '#00695c' },
  { label: 'doc', color: '#455a64' },
  { label: 'step', color: '#5e35b1' },
  { label: 'component', color: '#e65100' },
  { label: 'application', color: '#c62828' },
]

// Node/edge counts are deliberately omitted here — they're already shown in
// the top-bar status text (see main.js's loadGraph).
export function openAbout(graph) {
  const backdrop = document.createElement('div')
  backdrop.className = 'gide__modal-backdrop'

  const legendHtml = LEGEND
    .map(({ label, color }) => `<div class="legend-item"><span class="swatch" style="background:${color}"></span>${label}</div>`)
    .join('')

  const filesHtml = graph?.files?.length
    ? `<h3>Discovered files</h3><ul>${graph.files.map(f => `<li>${f.path}</li>`).join('')}</ul>`
    : ''

  const compEntries = Object.entries(graph?.components || {})
  const compHtml = compEntries.length
    ? `<h3>Components</h3><ul>${compEntries
        .map(([name, info]) => {
          const deps = info.depends_on.length ? ` → depends on ${info.depends_on.join(', ')}` : ''
          return `<li>${name}${deps}</li>`
        })
        .join('')}</ul>`
    : ''

  backdrop.innerHTML = `
    <div class="gide__modal gide__modal--wide">
      <h2>About Graph IDE</h2>

      <h3>What is Graph-Code</h3>
      <p>graph-code models an app as a graph of nodes (primitives, concepts, modules, steps, ...) connected by <code>composed_of</code>/<code>depends_on</code>/<code>needs</code> edges, defined in <code>apps/&lt;app&gt;/blueprint/*.graph.yaml</code>. Each node's prose fields (<code>defines</code>, <code>spec</code>, <code>verification</code>, <code>docs</code>) are the source of truth an LLM-driven build reads from to generate the actual app code — the blueprint is upstream of the implementation, not a diagram of it.</p>

      <p>Graph IDE is a browser <strong>editor</strong> for those blueprints, not just a viewer: click a node to inspect its spec and transitive dependencies, drag to rearrange the layout, and — with the <strong>Edit</strong> toggle on — change a node's prose fields and <strong>Save</strong> straight back to the owning <code>graph.yaml</code>.</p>

      <h3>Node kinds</h3>
      <div class="legend-list">${legendHtml}</div>

      ${filesHtml}
      ${compHtml}

      <div class="settings-actions">
        <button type="button" id="about-close">Close</button>
      </div>
    </div>
  `
  document.body.appendChild(backdrop)

  function close() {
    backdrop.remove()
  }

  backdrop.addEventListener('click', e => {
    if (e.target === backdrop) close()
  })
  backdrop.querySelector('#about-close').addEventListener('click', close)
}
