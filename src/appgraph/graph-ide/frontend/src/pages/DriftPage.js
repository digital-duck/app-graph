const DIMS = ['intent', 'behavior', 'structural', 'interface', 'implementation']
const MODES = [
  { value: 'semantic', label: 'Semantic', hint: 'LLM-as-judge — needs LLM adapter, default' },
  { value: 'edit-dist', label: 'Edit-distance', hint: 'character-level Levenshtein — free' },
  { value: 'jaccard', label: 'Jaccard', hint: 'exact-match set overlap — free' },
]

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

export function renderDriftPage(container, ctx) {
  container.innerHTML = `
    <div class="gide__page">
      <div class="gide__form">
        <div class="gide__form-row">
          <label class="gide__field">
            <span class="gide__field-label">Path A</span>
            <input type="text" id="drift-graph-a" placeholder="apps/todo/blueprint/backend.graph.yaml" value="apps/todo/blueprint/backend.graph.yaml" />
          </label>
          <label class="gide__field">
            <span class="gide__field-label">Path B</span>
            <input type="text" id="drift-graph-b" placeholder="apps/todo1/blueprint/backend.graph.yaml" value="apps/todo1/blueprint/backend.graph.yaml" />
          </label>
        </div>
        <div class="gide__form-row">
          <label class="gide__field">
            <span class="gide__field-label">LLM adapter</span>
            <input type="text" id="drift-llm" placeholder="ADAPTER:MODEL (optional — needed for semantic mode)" value="claude_cli:claude-sonnet-4-6" />
          </label>
          <label class="gide__field">
            <span class="gide__field-label">Max output tokens</span>
            <input type="number" id="drift-llm-max-tokens" placeholder="4096" value="4096" min="1" />
          </label>
        </div>
        <div class="gide__form-row">
          <div class="gide__field">
            <span class="gide__field-label">Dimensions</span>
            <div class="gide__field-row">
              ${DIMS.map(d => `<label><input type="checkbox" class="drift-dim" value="${d}" checked /> ${d}</label>`).join('')}
            </div>
          </div>
          <div class="gide__field">
            <span class="gide__field-label">Compare method</span>
            <div class="gide__field-row">
              ${MODES.map((m, i) => `
                <label title="${m.hint}">
                  <input type="radio" name="drift-mode" class="drift-mode" value="${m.value}" ${i === 0 ? 'checked' : ''} /> ${m.label}
                </label>
              `).join('')}
            </div>
          </div>
        </div>
        <div class="gide__field gide__field-row">
          <button id="drift-run-btn">Compute Drift</button>
          <span class="gide__page-status" id="drift-status"></span>
        </div>
      </div>
      <div class="gide__page-body" id="drift-results">
        <p class="gide__hint">Jaccard/edit-distance are free, computed locally for all 5 dimensions (intent included). Semantic uses the LLM adapter above to judge each selected dimension instead.</p>
      </div>
    </div>
  `

  const graphA = container.querySelector('#drift-graph-a')
  const graphB = container.querySelector('#drift-graph-b')
  const llmInput = container.querySelector('#drift-llm')
  const llmMaxTokensInput = container.querySelector('#drift-llm-max-tokens')
  const statusEl = container.querySelector('#drift-status')
  const resultsEl = container.querySelector('#drift-results')
  const dimBoxes = [...container.querySelectorAll('.drift-dim')]
  const modeBoxes = [...container.querySelectorAll('.drift-mode')]

  async function run() {
    const a = graphA.value.trim()
    const b = graphB.value.trim()
    if (!a || !b) {
      statusEl.textContent = 'both graph paths are required'
      return
    }
    const dims = dimBoxes.filter(c => c.checked).map(c => c.value).join(',')
    const mode = (modeBoxes.find(r => r.checked) || {}).value || 'semantic'
    // Defensive: the field only holds the adapter value (e.g.
    // "claude_cli:claude-sonnet-4-6"), not the raw CLI flag — strip a
    // leading "--llm " if someone pastes/types it in anyway, since typing
    // it verbatim otherwise produces a confusing "Unknown adapter '--llm
    // claude_cli'" error from spl3 with no obvious cause.
    const llm = llmInput.value.trim().replace(/^--llm\s+/, '')
    if (mode === 'semantic' && !llm) {
      statusEl.textContent = 'semantic mode needs an LLM adapter'
      return
    }
    const llmMaxTokens = llmMaxTokensInput.value.trim()
    statusEl.textContent = mode === 'semantic' ? 'computing… (this can take a while with an LLM judge)' : 'computing…'
    resultsEl.innerHTML = ''
    try {
      const res = await fetch('/api/drift', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ graph_a: a, graph_b: b, llm, dims, mode, llm_max_output_tokens: llmMaxTokens }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || res.statusText)

      statusEl.textContent = 'done'
      const rows = Object.entries(data.report)
        .map(([k, v]) => {
          // overall is a genuine two-vector comparison (1 - cosine similarity
          // over combined dimension text), independent of the selected mode —
          // unlike the other rows, it won't change between jaccard/edit-dist/semantic.
          const label = k === 'overall' ? 'overall (cosine-distance)' : k
          return `<tr><td>${escapeHtml(label)}</td><td>${v === null ? 'null' : escapeHtml(v)}</td></tr>`
        })
        .join('')
      resultsEl.innerHTML = `
        <table class="gide__table">
          <thead><tr><th>Component</th><th>Value</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `
    } catch (err) {
      statusEl.textContent = 'error — see below'
      resultsEl.innerHTML = `<pre class="gide__log">${escapeHtml(err.message)}</pre>`
    }
  }

  container.querySelector('#drift-run-btn').addEventListener('click', run)
}
