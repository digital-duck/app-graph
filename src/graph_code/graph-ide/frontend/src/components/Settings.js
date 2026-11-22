// Client-side Settings modal — persisted to localStorage. Currently controls
// UI font size; the LLM section is a placeholder for future features (graph
// summarization, node-spec drafting, ...) that will need a model/key, so the
// storage shape is settled now even though nothing reads llm.* yet.
const STORAGE_KEY = 'gide.settings.v1'

const DEFAULTS = {
  fontScale: 1.15,
  llm: { provider: 'anthropic', model: '', apiKey: '' },
}

export function loadSettings() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return { ...DEFAULTS, ...stored, llm: { ...DEFAULTS.llm, ...(stored.llm || {}) } }
  } catch {
    return { ...DEFAULTS }
  }
}

function saveSettings(settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
}

export function applyFontScale(fontScale) {
  document.documentElement.style.setProperty('--gide-scale', String(fontScale))
}

const MODEL_PLACEHOLDER = {
  anthropic: 'e.g. claude-sonnet-5',
  openai: 'e.g. gpt-5',
  ollama: 'e.g. llama3.1, qwen2.5-coder',
  other: 'model name',
}

export function openSettings(onAppsRootChanged) {
  const settings = loadSettings()

  const backdrop = document.createElement('div')
  backdrop.className = 'gide__modal-backdrop'
  backdrop.innerHTML = `
    <div class="gide__modal">
      <h2>Settings</h2>

      <h3>Workspace</h3>
      <label for="settings-apps-root">Apps root folder</label>
      <input type="text" id="settings-apps-root" placeholder="loading…" />
      <p class="settings-hint" id="settings-apps-root-hint">
        Where Graph IDE looks for &lt;app&gt;/blueprint/*.graph.yaml. Defaults to
        ~/graph-code/ide — point it at this repo's apps/, or any other location.
      </p>

      <h3>Appearance</h3>
      <label for="settings-font-scale">Font size (${settings.fontScale.toFixed(2)}×)</label>
      <input type="range" id="settings-font-scale" min="0.85" max="1.6" step="0.05" value="${settings.fontScale}" />

      <h3>LLM</h3>
      <label for="settings-llm-provider">Provider</label>
      <select id="settings-llm-provider">
        <option value="anthropic">Anthropic</option>
        <option value="openai">OpenAI</option>
        <option value="ollama">Ollama (local)</option>
        <option value="other">Other</option>
      </select>
      <label for="settings-llm-model" id="settings-llm-model-label">Model</label>
      <input type="text" id="settings-llm-model" placeholder="e.g. claude-sonnet-5" value="${settings.llm.model}" />
      <div id="settings-llm-key-row">
        <label for="settings-llm-key">API key</label>
        <input type="password" id="settings-llm-key" placeholder="sk-…" value="${settings.llm.apiKey}" />
      </div>
      <p class="settings-hint">Stored only in this browser (localStorage). Not wired to any feature yet.</p>

      <div class="settings-actions">
        <button type="button" class="secondary" id="settings-cancel">Cancel</button>
        <button type="button" id="settings-save">Save</button>
      </div>
    </div>
  `
  document.body.appendChild(backdrop)

  const appsRootInput = backdrop.querySelector('#settings-apps-root')
  const appsRootHint = backdrop.querySelector('#settings-apps-root-hint')
  const appsRootHintDefault = appsRootHint.textContent
  let loadedAppsRoot = ''

  fetch('/api/settings/apps-root')
    .then(res => res.json())
    .then(data => {
      loadedAppsRoot = data.apps_root
      appsRootInput.value = loadedAppsRoot
    })
    .catch(() => {
      appsRootInput.placeholder = 'error loading current value'
    })

  const fontScaleInput = backdrop.querySelector('#settings-font-scale')
  const fontScaleLabel = backdrop.querySelector('label[for="settings-font-scale"]')
  fontScaleInput.addEventListener('input', () => {
    const v = Number(fontScaleInput.value)
    fontScaleLabel.textContent = `Font size (${v.toFixed(2)}×)`
    applyFontScale(v) // live preview
  })

  const providerSelect = backdrop.querySelector('#settings-llm-provider')
  const modelInput = backdrop.querySelector('#settings-llm-model')
  const keyRow = backdrop.querySelector('#settings-llm-key-row')

  function updateProviderUI() {
    const provider = providerSelect.value
    modelInput.placeholder = MODEL_PLACEHOLDER[provider] || MODEL_PLACEHOLDER.other
    keyRow.style.display = provider === 'ollama' ? 'none' : ''
  }

  providerSelect.value = settings.llm.provider
  updateProviderUI()
  providerSelect.addEventListener('change', updateProviderUI)

  function close() {
    backdrop.remove()
  }

  backdrop.addEventListener('click', e => {
    if (e.target === backdrop) {
      applyFontScale(settings.fontScale) // discard live preview
      close()
    }
  })
  backdrop.querySelector('#settings-cancel').addEventListener('click', () => {
    applyFontScale(settings.fontScale) // discard live preview
    close()
  })
  backdrop.querySelector('#settings-save').addEventListener('click', async () => {
    const saveBtn = backdrop.querySelector('#settings-save')
    const newAppsRoot = appsRootInput.value.trim()

    if (newAppsRoot && newAppsRoot !== loadedAppsRoot) {
      saveBtn.disabled = true
      saveBtn.textContent = 'Saving…'
      try {
        const res = await fetch('/api/settings/apps-root', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ apps_root: newAppsRoot }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || res.statusText)
        loadedAppsRoot = data.apps_root
        if (onAppsRootChanged) onAppsRootChanged()
      } catch (err) {
        appsRootHint.textContent = `error: ${err.message}`
        appsRootHint.classList.add('settings-error')
        saveBtn.disabled = false
        saveBtn.textContent = 'Save'
        return // keep the modal open so the user can fix the path
      }
      appsRootHint.textContent = appsRootHintDefault
      appsRootHint.classList.remove('settings-error')
      saveBtn.disabled = false
      saveBtn.textContent = 'Save'
    }

    const updated = {
      fontScale: Number(fontScaleInput.value),
      llm: {
        provider: backdrop.querySelector('#settings-llm-provider').value,
        model: backdrop.querySelector('#settings-llm-model').value.trim(),
        apiKey: backdrop.querySelector('#settings-llm-key').value,
      },
    }
    saveSettings(updated)
    applyFontScale(updated.fontScale)
    close()
  })
}
