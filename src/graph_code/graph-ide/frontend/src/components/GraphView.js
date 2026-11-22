// Hand-rolled SVG DAG renderer — no third-party graph library. vis-network's
// CDN bundle triggers "unsafe-eval" under a strict CSP; a plain SVG layout
// avoids that entirely and keeps this frontend dependency-free.

const KIND_COLOR = {
  primitive: { background: '#fffde7', border: '#795548' },
  concept: { background: '#e8f5e9', border: '#2e7d32' },
  module: { background: '#e0f2f1', border: '#00695c' },
  doc: { background: '#eceff1', border: '#455a64' },
  step: { background: '#ede7f6', border: '#5e35b1' },
  component: { background: '#fff3e0', border: '#e65100' },
  application: { background: '#fce4ec', border: '#c62828' },
}

const EDGE_COLOR = {
  composed_of: '#94a3b8',
  needs: '#2563eb',
  // enriched_by / optionally_depends_on — non-mandatory form edges (see
  // graph_code's _OPTIONAL_EDGE_KINDS); styled distinctly from the solid
  // gray mandatory composed_of/depends_on edge.
  optional: '#c084fc',
}

// Highlight styling for the selected node and its transitive dependencies
// (ancestors reachable by walking edges backwards from the selection).
// Edge highlight uses a distinct hue from the node highlight so the path
// reads as "connective tissue" rather than a variant of the node fill.
const HL_TARGET_FILL = '#ffe082'
const HL_PATH_FILL = '#fff9c4'
const HL_BORDER = '#f9a825'
const HL_EDGE_COLOR = '#0284c7'
const DIM_OPACITY = 0.3

const NODE_W = 160
const NODE_H = 40
const H_GAP = 24
const V_GAP = 80
const PADDING = 40

const SVG_NS = 'http://www.w3.org/2000/svg'

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVG_NS, tag)
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v)
  return el
}

function numericTier(node, maxComponentTier) {
  return node.tier === 'system' ? maxComponentTier + 1 : Number(node.tier) || 0
}

function layout(nodes) {
  const maxComponentTier = Math.max(0, ...nodes.filter(n => n.tier !== 'system').map(n => Number(n.tier) || 0))

  const levels = new Map()
  nodes.forEach(n => {
    const level = numericTier(n, maxComponentTier)
    if (!levels.has(level)) levels.set(level, [])
    levels.get(level).push(n)
  })

  const sortedLevels = [...levels.keys()].sort((a, b) => a - b)
  const positions = new Map()
  let maxRowWidth = 0

  sortedLevels.forEach((level, rowIndex) => {
    const rowNodes = levels.get(level).sort((a, b) => (a.component || '').localeCompare(b.component || '') || a.id.localeCompare(b.id))
    const rowWidth = rowNodes.length * NODE_W + (rowNodes.length - 1) * H_GAP
    maxRowWidth = Math.max(maxRowWidth, rowWidth)
    rowNodes.forEach((n, i) => {
      positions.set(n.id, {
        x: i * (NODE_W + H_GAP),
        y: rowIndex * (NODE_H + V_GAP),
        rowWidth,
      })
    })
  })

  // center each row within the widest row, then add padding
  positions.forEach(pos => {
    pos.x += (maxRowWidth - pos.rowWidth) / 2 + PADDING
    pos.y += PADDING
  })

  return {
    positions,
    width: maxRowWidth + PADDING * 2,
    height: sortedLevels.length * (NODE_H + V_GAP) + PADDING,
  }
}

const ZOOM_STEP = 1.2
const ZOOM_MIN = 0.3
const ZOOM_MAX = 3

export function createGraphView(container) {
  container.style.overflow = 'auto'

  // Populated on each render(); recenter()/zoom* read/write these via closure.
  let positions = new Map()
  let originalPositions = new Map()
  let nodeEls = new Map()
  let edgeEls = []
  let svgEl_ = null
  let baseWidth = 0
  let baseHeight = 0
  let originalWidth = 0
  let originalHeight = 0
  let zoom = 1

  function applyZoom() {
    if (!svgEl_) return
    svgEl_.setAttribute('width', baseWidth * zoom)
    svgEl_.setAttribute('height', baseHeight * zoom)
  }

  // SVG clips its own content to width/height/viewBox by default (the UA
  // stylesheet sets overflow: hidden on the root <svg>) — independent of
  // #graph-canvas's own overflow:auto scrolling. Dragging a node past the
  // auto-computed layout bounds would otherwise vanish, invisibly clipped by
  // the SVG itself rather than needing a scroll. Grow the SVG's own box to
  // keep dragged nodes inside it.
  function ensureBounds(x, y) {
    const neededW = x + NODE_W + PADDING
    const neededH = y + NODE_H + PADDING
    let changed = false
    if (neededW > baseWidth) { baseWidth = neededW; changed = true }
    if (neededH > baseHeight) { baseHeight = neededH; changed = true }
    if (!changed || !svgEl_) return
    svgEl_.setAttribute('viewBox', `0 0 ${baseWidth} ${baseHeight}`)
    applyZoom()
  }

  function zoomIn() {
    zoom = Math.min(ZOOM_MAX, zoom * ZOOM_STEP)
    applyZoom()
  }

  function zoomOut() {
    zoom = Math.max(ZOOM_MIN, zoom / ZOOM_STEP)
    applyZoom()
  }

  function edgePath(fromId, toId) {
    const from = positions.get(fromId)
    const to = positions.get(toId)
    const x1 = from.x + NODE_W / 2
    const y1 = from.y + NODE_H
    const x2 = to.x + NODE_W / 2
    const y2 = to.y
    return `M ${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`
  }

  function render(graph, onNodeSelect) {
    container.innerHTML = ''
    nodeEls = new Map()
    edgeEls = []

    if (!graph.nodes.length) {
      container.textContent = 'No nodes found.'
      return
    }

    const layoutResult = layout(graph.nodes)
    positions = layoutResult.positions
    originalPositions = new Map([...positions].map(([id, pos]) => [id, { ...pos }]))
    const { width, height } = layoutResult
    baseWidth = width
    baseHeight = height
    originalWidth = width
    originalHeight = height
    zoom = 1

    const svg = svgEl('svg', { width, height, viewBox: `0 0 ${width} ${height}` })
    svgEl_ = svg

    const defs = svgEl('defs')
    Object.entries(EDGE_COLOR).forEach(([type, color]) => {
      const marker = svgEl('marker', {
        id: `arrow-${type}`, viewBox: '0 0 10 10', refX: 9, refY: 5,
        markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse',
      })
      marker.appendChild(svgEl('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: color }))
      defs.appendChild(marker)
    })
    svg.appendChild(defs)

    const edgeLayer = svgEl('g')
    const nodeLayer = svgEl('g')

    // predecessors[id] = ids that point into id, i.e. things id depends on
    const predecessors = new Map()
    graph.nodes.forEach(n => predecessors.set(n.id, []))
    graph.edges.forEach(e => predecessors.get(e.to)?.push(e.from))

    function getAncestors(targetId) {
      const visited = new Set()
      const queue = [targetId]
      while (queue.length) {
        const cur = queue.shift()
        for (const p of predecessors.get(cur) || []) {
          if (!visited.has(p)) { visited.add(p); queue.push(p) }
        }
      }
      return visited
    }

    graph.edges.forEach(e => {
      if (!positions.get(e.from) || !positions.get(e.to)) return

      const color = EDGE_COLOR[e.type] || '#94a3b8'
      const line = svgEl('path', {
        d: edgePath(e.from, e.to),
        stroke: color,
        'stroke-width': 1.5,
        fill: 'none',
        'stroke-dasharray': e.type === 'needs' ? '5,4' : e.type === 'optional' ? '2,3' : 'none',
        'marker-end': `url(#arrow-${e.type})`,
      })
      edgeLayer.appendChild(line)
      edgeEls.push({ el: line, from: e.from, to: e.to, color })
    })

    function refreshEdgesFor(nodeId) {
      edgeEls.forEach(edge => {
        if (edge.from === nodeId || edge.to === nodeId) {
          edge.el.setAttribute('d', edgePath(edge.from, edge.to))
        }
      })
    }

    function applySelection(selectedId) {
      const ancestors = getAncestors(selectedId)

      nodeEls.forEach(({ g, rect, colors }, id) => {
        if (id === selectedId) {
          rect.setAttribute('fill', HL_TARGET_FILL)
          rect.setAttribute('stroke', HL_BORDER)
          rect.setAttribute('stroke-width', 2.5)
          g.setAttribute('opacity', 1)
        } else if (ancestors.has(id)) {
          rect.setAttribute('fill', HL_PATH_FILL)
          rect.setAttribute('stroke', HL_BORDER)
          rect.setAttribute('stroke-width', 2)
          g.setAttribute('opacity', 1)
        } else {
          rect.setAttribute('fill', colors.background)
          rect.setAttribute('stroke', colors.border)
          rect.setAttribute('stroke-width', 1.5)
          g.setAttribute('opacity', DIM_OPACITY)
        }
      })

      edgeEls.forEach(({ el, from, to, color }) => {
        const inPath = to === selectedId ? ancestors.has(from) : (ancestors.has(from) && ancestors.has(to))
        if (inPath) {
          el.setAttribute('stroke', HL_EDGE_COLOR)
          el.setAttribute('stroke-width', 2.5)
          el.setAttribute('opacity', 1)
        } else {
          el.setAttribute('stroke', color)
          el.setAttribute('stroke-width', 1.5)
          el.setAttribute('opacity', DIM_OPACITY)
        }
      })
    }

    graph.nodes.forEach(n => {
      const pos = positions.get(n.id)
      if (!pos) return
      const colors = KIND_COLOR[n.kind] || KIND_COLOR.concept

      const g = svgEl('g', { transform: `translate(${pos.x}, ${pos.y})`, cursor: 'grab' })
      const rect = svgEl('rect', {
        width: NODE_W, height: NODE_H, rx: 6,
        fill: colors.background, stroke: colors.border, 'stroke-width': 1.5,
      })
      const text = svgEl('text', {
        x: NODE_W / 2, y: NODE_H / 2 + 4, 'text-anchor': 'middle',
        'font-size': 12, 'font-family': 'system-ui, sans-serif', fill: '#1e293b',
      })
      text.textContent = n.label.length > 22 ? n.label.slice(0, 21) + '…' : n.label

      const title = svgEl('title')
      title.textContent = `${n.component ? n.component + ' · ' : ''}${n.kind}`

      g.append(rect, text, title)
      nodeLayer.appendChild(g)
      nodeEls.set(n.id, { g, rect, colors })

      // Drag to reposition; a pointerdown/up with negligible movement is
      // treated as a click (select + highlight dependents) instead.
      let dragging = false
      let moved = false
      let startClientX = 0
      let startClientY = 0
      let startPos = null

      g.addEventListener('pointerdown', e => {
        dragging = true
        moved = false
        startClientX = e.clientX
        startClientY = e.clientY
        startPos = { ...positions.get(n.id) }
        g.setPointerCapture(e.pointerId)
        g.style.cursor = 'grabbing'
      })

      g.addEventListener('pointermove', e => {
        if (!dragging) return
        // Screen-pixel deltas; the SVG's own coordinate system is in viewBox
        // units, which only equal screen pixels at zoom === 1 (see applyZoom
        // — width/height scale with zoom while viewBox doesn't), so divide
        // back out or dragging drifts from the cursor once zoomed.
        const dx = (e.clientX - startClientX) / zoom
        const dy = (e.clientY - startClientY) / zoom
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) moved = true
        if (!moved) return
        const newPos = {
          ...positions.get(n.id),
          x: Math.max(0, startPos.x + dx),
          y: Math.max(0, startPos.y + dy),
        }
        positions.set(n.id, newPos)
        ensureBounds(newPos.x, newPos.y)
        g.setAttribute('transform', `translate(${newPos.x}, ${newPos.y})`)
        refreshEdgesFor(n.id)
      })

      g.addEventListener('pointerup', e => {
        dragging = false
        g.style.cursor = 'grab'
        g.releasePointerCapture(e.pointerId)
        if (!moved) {
          applySelection(n.id)
          onNodeSelect(n)
        }
      })
    })

    svg.append(edgeLayer, nodeLayer)
    container.appendChild(svg)
  }

  function recenter() {
    zoom = 1
    baseWidth = originalWidth
    baseHeight = originalHeight
    if (svgEl_) svgEl_.setAttribute('viewBox', `0 0 ${baseWidth} ${baseHeight}`)
    applyZoom()
    nodeEls.forEach(({ g, rect, colors }, id) => {
      const pos = originalPositions.get(id)
      if (!pos) return
      positions.set(id, { ...pos })
      g.setAttribute('transform', `translate(${pos.x}, ${pos.y})`)
      g.setAttribute('opacity', 1)
      rect.setAttribute('fill', colors.background)
      rect.setAttribute('stroke', colors.border)
      rect.setAttribute('stroke-width', 1.5)
    })
    edgeEls.forEach(({ el, from, to, color }) => {
      el.setAttribute('d', edgePath(from, to))
      el.setAttribute('stroke', color)
      el.setAttribute('stroke-width', 1.5)
      el.setAttribute('opacity', 1)
    })
    container.scrollTo({ top: 0, left: 0, behavior: 'smooth' })
  }

  return { render, recenter, zoomIn, zoomOut }
}
