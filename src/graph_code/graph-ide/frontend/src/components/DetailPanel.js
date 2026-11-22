// graph-code's form.nodes `kind:` vocabulary is richer than the old GDW
// schema's fixed primitive/concept/application set (see
// docs/DEV/BUILD/blueprint-schema-v2.2.md) — concept/module/doc/step all
// carry the same spec.interface/contract + verification shape, so they
// share one field set below; component nodes (e.g. `<app>_app_shell`) are
// structural-only, closer to a primitive (just `defines`).
const KIND_COLOR = {
  primitive: { background: '#fffde7', color: '#795548' },
  concept: { background: '#e8f5e9', color: '#2e7d32' },
  module: { background: '#e0f2f1', color: '#00695c' },
  doc: { background: '#eceff1', color: '#455a64' },
  step: { background: '#ede7f6', color: '#5e35b1' },
  component: { background: '#fff3e0', color: '#e65100' },
  application: { background: '#fce4ec', color: '#c62828' },
}

// Fields editable via PATCH /api/graphs/nodes/{id}.
const EDITABLE_FIELDS = {
  primitive: [
    { key: 'defines', label: 'Defines', path: ['defines'] },
  ],
  component: [
    { key: 'defines', label: 'Defines', path: ['defines'] },
  ],
  concept: [
    { key: 'defines', label: 'Defines', path: ['defines'] },
    { key: 'spec.interface', label: 'Interface', path: ['spec', 'interface'] },
    { key: 'spec.contract', label: 'Contract', path: ['spec', 'contract'] },
    { key: 'verification.node', label: 'Verification — node', path: ['verification', 'node'] },
    { key: 'verification.edge', label: 'Verification — edge', path: ['verification', 'edge'] },
    { key: 'docs', label: 'Docs', path: ['docs'] },
  ],
  application: [
    { key: 'defines', label: 'Defines', path: ['defines'] },
    { key: 'spec.user_story', label: 'User story', path: ['spec', 'user_story'] },
    { key: 'spec.contract', label: 'Contract', path: ['spec', 'contract'] },
    { key: 'verification.node', label: 'Verification — node', path: ['verification', 'node'] },
    { key: 'verification.edge', label: 'Verification — edge', path: ['verification', 'edge'] },
    { key: 'docs', label: 'Docs', path: ['docs'] },
  ],
}
EDITABLE_FIELDS.module = EDITABLE_FIELDS.concept
EDITABLE_FIELDS.doc = EDITABLE_FIELDS.concept
EDITABLE_FIELDS.step = EDITABLE_FIELDS.concept

function field(title, value) {
  if (!value) return ''
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return `<h3>${title}</h3><pre>${text}</pre>`
}

function getPath(obj, path) {
  return path.reduce((o, k) => (o && o[k] !== undefined ? o[k] : ''), obj)
}

function renderReadOnly(fieldsEl, node) {
  const spec = node.spec || {}
  const verification = node.verification || {}
  fieldsEl.innerHTML = `
    ${field('Defines', node.defines)}
    ${field('Interface', spec.interface)}
    ${field('Contract', spec.contract)}
    ${field('User story', spec.user_story)}
    ${field('Verification — node', verification.node)}
    ${field('Verification — edge', verification.edge)}
    ${field('Docs', node.docs)}
  `
}

// Direct "what you see is what's saved" editor: textareas are pre-filled
// with the field's raw stored text (already `- bullet` formatted where
// applicable) and Save PATCHes exactly what's typed, verbatim — no
// re-bulleting. See scripts/graph_yaml_style.edited_text_to_scalar.
function renderEditable(fieldsEl, node, root, onSaved, rerender) {
  const fieldDefs = EDITABLE_FIELDS[node.kind] || EDITABLE_FIELDS.concept
  const entries = fieldDefs.map(def => {
    const wrap = document.createElement('div')
    const h3 = document.createElement('h3')
    h3.textContent = def.label
    const ta = document.createElement('textarea')
    ta.className = 'edit-field'
    ta.rows = 4
    ta.value = getPath(node, def.path)
    wrap.append(h3, ta)
    fieldsEl.appendChild(wrap)
    return { def, ta, original: ta.value }
  })

  const actions = document.createElement('div')
  actions.className = 'edit-actions'
  const saveBtn = document.createElement('button')
  saveBtn.textContent = 'Save'
  const cancelBtn = document.createElement('button')
  cancelBtn.textContent = 'Cancel'
  cancelBtn.className = 'secondary'
  const msg = document.createElement('span')
  msg.className = 'edit-msg'
  actions.append(saveBtn, cancelBtn, msg)
  fieldsEl.appendChild(actions)

  cancelBtn.addEventListener('click', () => rerender())

  saveBtn.addEventListener('click', async () => {
    const patch = {}
    let changed = false
    for (const { def, ta, original } of entries) {
      if (ta.value === original) continue
      changed = true
      if (def.path.length === 1) {
        patch[def.path[0]] = ta.value
      } else {
        patch[def.path[0]] = patch[def.path[0]] || {}
        patch[def.path[0]][def.path[1]] = ta.value
      }
    }
    if (!changed) {
      msg.textContent = 'no changes'
      msg.className = 'edit-msg'
      return
    }

    saveBtn.disabled = true
    cancelBtn.disabled = true
    msg.textContent = 'saving…'
    msg.className = 'edit-msg'

    try {
      const res = await fetch(`/api/graphs/nodes/${encodeURIComponent(node.id)}?root=${encodeURIComponent(root)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(body.detail || res.statusText)
      onSaved(body)
    } catch (err) {
      msg.textContent = `error: ${err.message}`
      msg.className = 'edit-msg edit-msg--error'
      saveBtn.disabled = false
      cancelBtn.disabled = false
    }
  })
}

export function renderDetail(el, node, opts = {}) {
  const { editable = false, root = null, onSaved = () => {} } = opts

  if (!node) {
    el.innerHTML = '<div class="empty-hint">Click a node to see its spec, contract, and verification.</div>'
    return
  }

  const badge = KIND_COLOR[node.kind] || KIND_COLOR.concept

  el.innerHTML = `
    <h2>${node.label}</h2>
    <span class="kind-badge" style="background:${badge.background};color:${badge.color}">${node.kind}</span>
    <div class="source-file">${node.source_file}${node.component ? ' · ' + node.component : ''}</div>
    <div id="detail-fields"></div>
  `

  const fieldsEl = el.querySelector('#detail-fields')

  if (editable && root) {
    renderEditable(fieldsEl, node, root, onSaved, () => renderDetail(el, node, opts))
  } else {
    renderReadOnly(fieldsEl, node)
  }
}
