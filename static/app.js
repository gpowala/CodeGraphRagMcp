/**
 * C++ Graph-RAG MCP Server - Dashboard JavaScript
 */

// State
let currentPath = '/host';
let selectedPath = null;
let monitoredPaths = [];

// DOM Elements
const elements = {
    // Status
    serverStatus: document.getElementById('serverStatus'),
    serverStatusText: document.getElementById('serverStatusText'),
    totalFiles: document.getElementById('totalFiles'),
    indexedFiles: document.getElementById('indexedFiles'),
    entitiesCount: document.getElementById('entitiesCount'),
    chunksCount: document.getElementById('chunksCount'),
    progressContainer: document.getElementById('progressContainer'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    currentFile: document.getElementById('currentFile'),
    lastIndexed: document.getElementById('lastIndexed'),
    reindexBtn: document.getElementById('reindexBtn'),
    
    // Directories
    directoryList: document.getElementById('directoryList'),
    addDirectoryBtn: document.getElementById('addDirectoryBtn'),
    
    // Search
    searchInput: document.getElementById('searchInput'),
    searchBtn: document.getElementById('searchBtn'),
    searchResults: document.getElementById('searchResults'),
    
    // Modal
    directoryModal: document.getElementById('directoryModal'),
    closeModal: document.getElementById('closeModal'),
    breadcrumb: document.getElementById('breadcrumb'),
    fileBrowser: document.getElementById('fileBrowser'),
    cancelBrowse: document.getElementById('cancelBrowse'),
    selectDirectory: document.getElementById('selectDirectory'),
    
    // Toast
    toastContainer: document.getElementById('toastContainer')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    init();
});

async function init() {
    // Start polling for status
    pollStatus();
    setInterval(pollStatus, 3000);
    
    // Load directories
    await loadDirectories();
    
    // Event listeners
    elements.reindexBtn.addEventListener('click', triggerReindex);
    elements.addDirectoryBtn.addEventListener('click', openDirectoryModal);
    elements.closeModal.addEventListener('click', closeDirectoryModal);
    elements.cancelBrowse.addEventListener('click', closeDirectoryModal);
    elements.selectDirectory.addEventListener('click', selectCurrentDirectory);
    elements.searchBtn.addEventListener('click', performSearch);
    elements.searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    // Close modal on outside click
    elements.directoryModal.addEventListener('click', (e) => {
        if (e.target === elements.directoryModal) {
            closeDirectoryModal();
        }
    });
}

// =============================================================================
// Status Polling
// =============================================================================

async function pollStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error('Status request failed');
        
        const status = await response.json();
        updateStatusUI(status);
        
        elements.serverStatus.className = 'status-indicator connected';
        elements.serverStatusText.textContent = status.is_indexing ? 'Indexing...' : 'Connected';
        
        if (status.is_indexing) {
            elements.serverStatus.className = 'status-indicator indexing';
        }
    } catch (error) {
        elements.serverStatus.className = 'status-indicator error';
        elements.serverStatusText.textContent = 'Disconnected';
        console.error('Status poll error:', error);
    }
}

function updateStatusUI(status) {
    elements.totalFiles.textContent = formatNumber(status.total_files || 0);
    elements.indexedFiles.textContent = formatNumber(status.indexed_files || 0);
    elements.entitiesCount.textContent = formatNumber(status.entities_count || 0);
    elements.chunksCount.textContent = formatNumber(status.chunks_count || 0);
    
    // Progress bar
    if (status.is_indexing && status.total_files > 0) {
        elements.progressContainer.classList.add('active');
        const percent = Math.round((status.indexed_files / status.total_files) * 100);
        elements.progressFill.style.width = `${percent}%`;
        elements.progressText.textContent = `Indexing: ${percent}%`;
        elements.currentFile.textContent = truncatePath(status.current_file || '');
    } else {
        elements.progressContainer.classList.remove('active');
    }
    
    // Last indexed
    if (status.last_indexed) {
        const date = new Date(status.last_indexed);
        elements.lastIndexed.textContent = formatDate(date);
    }
}

// =============================================================================
// Directory Management
// =============================================================================

async function loadDirectories() {
    try {
        const response = await fetch('/api/directories');
        if (!response.ok) throw new Error('Failed to load directories');
        
        const data = await response.json();
        monitoredPaths = data.monitored_paths || [];
        renderDirectoryList();
    } catch (error) {
        console.error('Load directories error:', error);
        showToast('Failed to load directories', 'error');
    }
}

function renderDirectoryList() {
    if (monitoredPaths.length === 0) {
        elements.directoryList.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <p>No directories configured</p>
                <p class="hint">Click "Add Directory" to select folders to index</p>
            </div>
        `;
        return;
    }
    
    elements.directoryList.innerHTML = monitoredPaths.map(path => `
        <div class="directory-item" data-path="${escapeHtml(path)}">
            <span class="directory-path">${escapeHtml(path)}</span>
            <div class="directory-meta">
                <button class="btn-remove" onclick="removeDirectory('${escapeHtml(path)}')" title="Remove">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

async function removeDirectory(path) {
    monitoredPaths = monitoredPaths.filter(p => p !== path);
    
    // Delete associated files, entities, and chunks from database
    try {
        const response = await fetch(`/api/directories/${encodeURIComponent(path)}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            const result = await response.json();
            console.log(`Cleaned up ${result.deleted_files} files`);
        }
    } catch (error) {
        console.error('Cleanup error:', error);
    }
    
    await saveDirectories();
    showToast('Directory removed and data cleaned up', 'success');
}

async function saveDirectories() {
    try {
        const response = await fetch('/api/directories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monitored_paths: monitoredPaths })
        });
        
        if (!response.ok) throw new Error('Failed to save directories');
        
        renderDirectoryList();
    } catch (error) {
        console.error('Save directories error:', error);
        showToast('Failed to save directories', 'error');
    }
}

// =============================================================================
// Directory Browser Modal
// =============================================================================

function openDirectoryModal() {
    currentPath = '/host';
    selectedPath = null;
    elements.selectDirectory.disabled = true;
    elements.directoryModal.classList.add('active');
    browsePath(currentPath);
}

function closeDirectoryModal() {
    elements.directoryModal.classList.remove('active');
}

async function browsePath(path) {
    currentPath = path;
    selectedPath = path;
    elements.selectDirectory.disabled = false;
    
    elements.fileBrowser.innerHTML = '<div class="loading">Loading...</div>';
    updateBreadcrumb(path);
    
    try {
        const response = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
        if (!response.ok) throw new Error('Failed to browse directory');
        
        const data = await response.json();
        
        if (data.error) {
            elements.fileBrowser.innerHTML = `
                <div class="empty-state">
                    <p>${escapeHtml(data.error)}</p>
                </div>
            `;
            return;
        }
        
        renderFileBrowser(data);
    } catch (error) {
        console.error('Browse error:', error);
        elements.fileBrowser.innerHTML = `
            <div class="empty-state">
                <p>Failed to load directory</p>
            </div>
        `;
    }
}

function renderFileBrowser(data) {
    const items = data.items || [];
    
    // Filter to only show directories
    const directories = items.filter(item => item.is_dir);
    
    if (directories.length === 0) {
        elements.fileBrowser.innerHTML = `
            <div class="empty-state small">
                <p>No subdirectories found</p>
            </div>
        `;
        return;
    }
    
    elements.fileBrowser.innerHTML = directories.map(item => `
        <div class="file-item" onclick="browsePath('${escapeHtml(item.path)}')" data-path="${escapeHtml(item.path)}">
            <svg class="file-icon folder" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="file-name">${escapeHtml(item.name)}</span>
            ${item.cpp_files > 0 ? `<span class="file-meta">${item.cpp_files} C++ files</span>` : ''}
        </div>
    `).join('');
}

function updateBreadcrumb(path) {
    const parts = path.split('/').filter(p => p);
    let currentPath = '';
    
    const items = parts.map((part, index) => {
        currentPath += '/' + part;
        const isLast = index === parts.length - 1;
        return `<span class="breadcrumb-item" ${!isLast ? `onclick="browsePath('${escapeHtml(currentPath)}')"` : ''} data-path="${escapeHtml(currentPath)}">${escapeHtml(part)}</span>`;
    });
    
    elements.breadcrumb.innerHTML = items.join('');
}

async function selectCurrentDirectory() {
    if (!selectedPath) return;
    
    if (!monitoredPaths.includes(selectedPath)) {
        monitoredPaths.push(selectedPath);
        await saveDirectories();
        showToast('Directory added', 'success');
    } else {
        showToast('Directory already added', 'info');
    }
    
    closeDirectoryModal();
}

// =============================================================================
// Search
// =============================================================================

async function performSearch() {
    const query = elements.searchInput.value.trim();
    if (!query) return;
    
    elements.searchResults.innerHTML = '<div class="loading">Searching...</div>';
    
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, max_results: 5 })
        });
        
        if (!response.ok) throw new Error('Search failed');
        
        const data = await response.json();
        renderSearchResults(data);
    } catch (error) {
        console.error('Search error:', error);
        elements.searchResults.innerHTML = `
            <div class="empty-state small">
                <p>Search failed. Make sure files are indexed.</p>
            </div>
        `;
    }
}

function renderSearchResults(data) {
    const results = data.results || [];
    
    if (results.length === 0) {
        elements.searchResults.innerHTML = `
            <div class="empty-state small">
                <p>No results found</p>
            </div>
        `;
        return;
    }
    
    elements.searchResults.innerHTML = results.map(result => `
        <div class="search-result">
            <div class="search-result-header">
                <span class="search-result-entity">${escapeHtml(result.entity || 'Unknown')}</span>
                <span class="search-result-similarity">${(result.similarity * 100).toFixed(1)}%</span>
            </div>
            <div class="search-result-file">${escapeHtml(result.file)} (${result.lines})</div>
            <pre class="search-result-code">${escapeHtml(truncateCode(result.content))}</pre>
        </div>
    `).join('');
}

// =============================================================================
// Actions
// =============================================================================

async function triggerReindex() {
    try {
        elements.reindexBtn.disabled = true;
        const response = await fetch('/api/reindex', { method: 'POST' });
        
        if (!response.ok) throw new Error('Reindex failed');
        
        showToast('Re-indexing started', 'success');
    } catch (error) {
        console.error('Reindex error:', error);
        showToast('Failed to start re-indexing', 'error');
    } finally {
        elements.reindexBtn.disabled = false;
    }
}

// =============================================================================
// Toast Notifications
// =============================================================================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    elements.toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// =============================================================================
// Utilities
// =============================================================================

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatDate(date) {
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return Math.floor(diff / 60000) + ' min ago';
    if (diff < 86400000) return Math.floor(diff / 3600000) + ' hours ago';
    
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function truncatePath(path, maxLength = 50) {
    if (!path || path.length <= maxLength) return path;
    return '...' + path.slice(-maxLength);
}

function truncateCode(code, maxLength = 300) {
    if (!code || code.length <= maxLength) return code;
    return code.slice(0, maxLength) + '...';
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Make functions available globally
window.browsePath = browsePath;
window.removeDirectory = removeDirectory;
