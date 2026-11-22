// The original Graph IDE view — moved into a page module so it can live
// alongside Build/Drift behind the router, unchanged in behavior.
import { createGraphView } from '../components/GraphView.js'
import { renderDetail } from '../components/DetailPanel.js'

export function renderGraphPage(container, ctx) {
  const requestedRoot = ctx.params.get('root')

  container.innerHTML = `
    <div class="gide__page">
      <div class="gide__page-toolbar">
        <select id="root-select"><option value="">loading apps…</option></select>
        <button id="load-btn">Load</button>
        <span class="gide__page-status" id="graph-info"></span>
        <div class="gide__topbar-center">
          <button id="zoom-out-btn" title="Zoom out">−</button>
          <button id="recenter-btn">Re-Center</button>
          <button id="zoom-in-btn" title="Zoom in">+</button>
        </div>
        <label class="gide__edit-toggle" for="edit-toggle">
          <input type="checkbox" id="edit-toggle" /> Edit
        </label>
      </div>
      <div class="gide__main">
        <div id="graph-canvas"></div>
        <div class="gide__splitter" id="splitter" title="Drag to resize"></div>
        <div class="gide__panel" id="panel"></div>
      </div>
    </div>
  `

  const rootSelect = container.querySelector('#root-select')
  const panel = container.querySelector('#panel')
  const canvas = container.querySelector('#graph-canvas')
  const mainEl = container.querySelector('.gide__main')
  const splitter = container.querySelector('#splitter')
  const graphInfo = container.querySelector('#graph-info')

  const graphView = createGraphView(canvas)

  let currentRoot = null
  let currentNode = null
  let editEnabled = false
  let appsRoot = null

  fetch('/api/settings/apps-root')
    .then(res => res.json())
    .then(data => { appsRoot = data.apps_root })
    .catch(() => {})

  function showNode(node) {
    currentNode = node
    renderDetail(panel, node, {
      editable: editEnabled,
      root: currentRoot,
      onSaved: updated => {
        ctx.setStatus(`saved ${updated.label}`)
        showNode(updated)
      },
    })
  }
  showNode(null)

  async function loadGraph(root) {
    if (!root) return
    ctx.setStatus('loading…')
    try {
      const res = await fetch(`/api/graphs?root=${encodeURIComponent(root)}`)
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || res.statusText)
      }
      const graph = await res.json()
      currentRoot = root
      ctx.onGraphChange(graph, root)
      graphView.render(graph, node => showNode(node))
      showNode(null)
      const fullPath = appsRoot ? `${appsRoot}/${root}` : root
      graphInfo.textContent = `${fullPath} — ${graph.nodes.length} nodes · ${graph.edges.length} edges`
      graphInfo.title = fullPath
      ctx.setStatus(`${graph.nodes.length} nodes · ${graph.edges.length} edges`)
      ctx.replaceRoute('graph', { root })
    } catch (err) {
      ctx.setStatus(`error: ${err.message}`)
    }
  }

  async function loadRoots() {
    try {
      const res = await fetch('/api/graphs/roots')
      if (!res.ok) throw new Error(res.statusText)
      const roots = await res.json()

      rootSelect.innerHTML = roots.map(r => `<option value="${r}">${r}</option>`).join('')

      const initial = requestedRoot && roots.includes(requestedRoot) ? requestedRoot : roots[0]
      if (initial) {
        rootSelect.value = initial
        loadGraph(initial)
      } else {
        ctx.setStatus('no apps found under the configured apps root')
      }
    } catch (err) {
      ctx.setStatus(`error loading app list: ${err.message}`)
    }
  }

  container.querySelector('#load-btn').addEventListener('click', () => loadGraph(rootSelect.value))
  container.querySelector('#recenter-btn').addEventListener('click', () => graphView.recenter())
  container.querySelector('#zoom-in-btn').addEventListener('click', () => graphView.zoomIn())
  container.querySelector('#zoom-out-btn').addEventListener('click', () => graphView.zoomOut())
  container.querySelector('#edit-toggle').addEventListener('change', e => {
    editEnabled = e.target.checked
    showNode(currentNode)
  })
  rootSelect.addEventListener('change', () => loadGraph(rootSelect.value))

  // Drag the splitter to resize graph-canvas vs. detail-panel; panel absorbs
  // whatever's left so it stays correct if the window itself is resized.
  const MIN_PANE = 160
  function currentMaxWidth() {
    return mainEl.getBoundingClientRect().width - splitter.getBoundingClientRect().width - MIN_PANE
  }
  splitter.addEventListener('pointerdown', e => {
    const startX = e.clientX
    const startWidth = canvas.getBoundingClientRect().width
    const maxWidth = currentMaxWidth()
    splitter.setPointerCapture(e.pointerId)
    document.body.style.cursor = 'col-resize'

    function onMove(ev) {
      const w = Math.min(maxWidth, Math.max(MIN_PANE, startWidth + (ev.clientX - startX)))
      canvas.style.flex = `0 0 ${w}px`
    }
    function onUp(ev) {
      splitter.releasePointerCapture(ev.pointerId)
      document.body.style.cursor = ''
      splitter.removeEventListener('pointermove', onMove)
      splitter.removeEventListener('pointerup', onUp)
    }
    splitter.addEventListener('pointermove', onMove)
    splitter.addEventListener('pointerup', onUp)
  })

  // A pixel width dragged at one window size can outgrow a later, narrower
  // window (canvas has flex-shrink: 0, so it won't shrink on its own) —
  // re-clamp on resize so it can never force the shared topbar to overflow.
  function onWindowResize() {
    if (!canvas.style.flex) return
    const maxWidth = currentMaxWidth()
    const current = canvas.getBoundingClientRect().width
    if (current > maxWidth) canvas.style.flex = `0 0 ${Math.max(MIN_PANE, maxWidth)}px`
  }
  window.addEventListener('resize', onWindowResize)

  loadRoots()

  return () => window.removeEventListener('resize', onWindowResize)
}
