// Minimal hash router — #/<page>?<query>. No history stack beyond what the
// browser's own hash navigation already gives us; that's all four pages need.

export function parseHash() {
  const raw = location.hash.startsWith('#/') ? location.hash.slice(2) : location.hash.replace(/^#/, '')
  const [page, query] = raw.split('?')
  return { page: page || 'graph', params: new URLSearchParams(query || '') }
}

export function navigate(page, params = {}) {
  const qs = new URLSearchParams(params).toString()
  location.hash = `#/${page}${qs ? '?' + qs : ''}`
}

// Updates the URL to reflect current page state without triggering a
// hashchange (and therefore without re-mounting the page) — for a page to
// keep its own URL in sync as the user interacts with it (e.g. the Graph
// page remembering which app is loaded across a refresh).
export function replaceRoute(page, params = {}) {
  const qs = new URLSearchParams(params).toString()
  history.replaceState(null, '', `#/${page}${qs ? '?' + qs : ''}`)
}

export function startRouter(onChange) {
  window.addEventListener('hashchange', () => onChange(parseHash()))
  onChange(parseHash())
}
