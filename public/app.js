// API Base URL
const API_BASE = '';

// State
let currentTreeId = null;
let currentNodeId = null;
let treeData = null;
let selectionMode = false;
let selectedSubtreeRoot = null;
let selectedSubtreeNodeIds = [];

// ============== Tab Switching ==============
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;
        
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        tab.classList.add('active');
        document.getElementById(tabName).classList.add('active');
        
        // Load trees when switching to trees tab
        if (tabName === 'trees') {
            loadTrees();
        }
    });
});

// ============== Search Type Toggle ==============
document.querySelectorAll('input[name="searchType"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        const sequenceInput = document.getElementById('sequenceInput');
        const metadataInput = document.getElementById('metadataInput');
        
        if (e.target.value === 'sequence') {
            sequenceInput.classList.remove('hidden');
            metadataInput.classList.add('hidden');
        } else {
            sequenceInput.classList.add('hidden');
            metadataInput.classList.remove('hidden');
        }
    });
});

// ============== Search Functionality ==============
document.getElementById('searchBtn').addEventListener('click', async () => {
    const searchType = document.querySelector('input[name="searchType"]:checked').value;
    const limit = parseInt(document.getElementById('resultLimit').value);
    
    const payload = {
        limit,
        include_sequence: false
    };
    
    if (searchType === 'sequence') {
        payload.query_sequence = document.getElementById('querySequence').value.trim();
        if (!payload.query_sequence) {
            showToast('Please enter a sequence', 'error');
            return;
        }
    } else {
        payload.metadata_filter = document.getElementById('metadataFilter').value.trim();
        if (!payload.metadata_filter) {
            showToast('Please enter a metadata filter', 'error');
            return;
        }
    }
    
    try {
        const response = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error('Search failed');
        
        const results = await response.json();
        displayResults(results);
    } catch (error) {
        console.error('Search error:', error);
        showToast('Search failed. Please try again.', 'error');
    }
});

function displayResults(results) {
    const resultsList = document.getElementById('resultsList');
    const resultCount = document.getElementById('resultCount');
    
    resultCount.textContent = `${results.length} result${results.length !== 1 ? 's' : ''}`;
    
    if (results.length === 0) {
        resultsList.innerHTML = `
            <div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                </svg>
                <h3>No results found</h3>
                <p>Try adjusting your search criteria</p>
            </div>
        `;
        return;
    }
    
    resultsList.innerHTML = results.map(result => `
        <div class="result-card">
            <div class="result-header">
                <div class="result-id">${truncateId(result.id)}</div>
                <div class="result-score">${(result.score * 100).toFixed(1)}%</div>
            </div>
            <div class="result-metadata">
                ${Object.entries(result.metadata || {}).map(([key, value]) => 
                    `<span class="metadata-tag">${key}: ${formatValue(value)}</span>`
                ).join('')}
            </div>
        </div>
    `).join('');
}

// ============== Upload Functionality ==============
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');

browseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
});

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('drag-over');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileUpload(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
    }
});

async function handleFileUpload(file) {
    const uploadProgress = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    uploadArea.classList.add('hidden');
    uploadProgress.classList.remove('hidden');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        progressFill.style.width = '30%';
        progressText.textContent = 'Uploading file...';
        
        await new Promise(r => setTimeout(r, 300));
        progressFill.style.width = '60%';
        progressText.textContent = 'Processing sequences...';
        
        const response = await fetch(`${API_BASE}/ingest/fasta`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Upload failed');
        
        progressFill.style.width = '100%';
        progressText.textContent = 'Upload complete!';
        showToast('File uploaded successfully!', 'success');
        
        setTimeout(() => {
            uploadArea.classList.remove('hidden');
            uploadProgress.classList.add('hidden');
            progressFill.style.width = '0%';
            fileInput.value = '';
            updateStats();
        }, 2000);
    } catch (error) {
        console.error('Upload error:', error);
        progressText.textContent = 'Upload failed. Please try again.';
        showToast('Upload failed', 'error');
        setTimeout(() => {
            uploadArea.classList.remove('hidden');
            uploadProgress.classList.add('hidden');
            progressFill.style.width = '0%';
        }, 2000);
    }
}

// ============== Export Functionality ==============
document.getElementById('exportBtn').addEventListener('click', async () => {
    const sequence = document.getElementById('exportSequence').value.trim();
    const filter = document.getElementById('exportFilter').value.trim();
    const limit = parseInt(document.getElementById('exportLimit').value);
    
    const payload = {
        limit,
        query_sequence: sequence || null,
        metadata_filter: filter || null
    };
    
    try {
        const response = await fetch(`${API_BASE}/export/parquet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `genomic_export_${Date.now()}.parquet`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        showToast('Export completed!', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showToast('Export failed. Please try again.', 'error');
    }
});

// ============== Tree Functionality ==============
document.getElementById('ingestTreeBtn').addEventListener('click', async () => {
    const newick = document.getElementById('newickInput').value.trim();
    const name = document.getElementById('treeName').value.trim() || 'Unnamed Tree';
    
    if (!newick) {
        showToast('Please enter a Newick format tree', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/trees/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ newick, name })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to ingest tree');
        }
        
        const tree = await response.json();
        showToast(`Tree "${tree.name}" added successfully!`, 'success');
        document.getElementById('newickInput').value = '';
        document.getElementById('treeName').value = '';
        loadTrees();
        updateStats();
    } catch (error) {
        console.error('Tree ingest error:', error);
        showToast(error.message, 'error');
    }
});

document.getElementById('loadTreesBtn').addEventListener('click', loadTrees);

// ============== Tree Search Functionality ==============
document.getElementById('searchTreesBtn').addEventListener('click', async () => {
    const newick = document.getElementById('searchNewickInput').value.trim();
    const limit = parseInt(document.getElementById('treeSearchLimit').value) || 5;
    
    if (!newick) {
        showToast('Please enter a Newick pattern to search', 'error');
        return;
    }
    
    const searchBtn = document.getElementById('searchTreesBtn');
    searchBtn.disabled = true;
    searchBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <path d="M21 12a9 9 0 11-6.219-8.56"/>
        </svg>
        <span>Searching...</span>
    `;
    
    try {
        const response = await fetch(`${API_BASE}/trees/search/similar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ newick, limit })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Search failed');
        }
        
        const results = await response.json();
        displayTreeSearchResults(results);
        
    } catch (error) {
        console.error('Tree search error:', error);
        showToast(error.message || 'Search failed', 'error');
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="M21 21l-4.35-4.35"/>
            </svg>
            <span>Search Trees</span>
        `;
    }
});

// Store the last search query for explanations
let lastSearchNewick = '';
let lastSearchResults = [];

function displayTreeSearchResults(results) {
    const container = document.getElementById('treeSearchResults');
    const list = document.getElementById('treeSearchList');
    const count = document.getElementById('treeSearchCount');
    
    // Store the search newick and results for comparisons
    lastSearchNewick = document.getElementById('searchNewickInput').value.trim();
    lastSearchResults = results;
    
    container.classList.remove('hidden');
    count.textContent = `${results.length} result${results.length !== 1 ? 's' : ''}`;
    
    if (results.length === 0) {
        list.innerHTML = `
            <div class="empty-state small">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                </svg>
                <p>No similar trees found</p>
            </div>
        `;
        return;
    }
    
    list.innerHTML = results.map((result, idx) => `
        <div class="tree-search-result" data-tree-id="${result.tree.id}" data-result-idx="${idx}" data-score="${result.score}">
            <div class="tree-search-result-header">
                <span class="tree-search-result-name">${result.tree.name}</span>
                <span class="tree-search-result-score ${getScoreClass(result.score)}">${formatScore(result.score)}</span>
            </div>
            <div class="tree-search-result-stats">
                <span>${result.tree.num_nodes} nodes</span>
                <span>•</span>
                <span>${result.tree.num_leaves} leaves</span>
                <button class="explain-btn" data-tree-id="${result.tree.id}" onclick="event.stopPropagation(); showExplanation('${result.tree.id}', '${result.tree.name.replace(/'/g, "\\'")}')">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 16v-4M12 8h.01"/>
                    </svg>
                    Why?
                </button>
            </div>
            <div class="explanation-panel hidden" id="explanation-${result.tree.id}">
                <div class="explanation-loading">
                    <div class="spinner small"></div>
                    Analyzing similarity...
                </div>
            </div>
        </div>
    `).join('');
    
    // Add click handlers to show comparison view
    document.querySelectorAll('.tree-search-result').forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't navigate if clicking on explain button
            if (e.target.closest('.explain-btn')) return;
            const treeId = item.dataset.treeId;
            const score = parseFloat(item.dataset.score);
            const resultIdx = parseInt(item.dataset.resultIdx);
            showComparisonView(treeId, score, lastSearchResults[resultIdx]);
        });
    });
}

async function showExplanation(treeId, treeName) {
    const panel = document.getElementById(`explanation-${treeId}`);
    
    // Toggle visibility
    if (!panel.classList.contains('hidden')) {
        panel.classList.add('hidden');
        return;
    }
    
    panel.classList.remove('hidden');
    
    // Check if we already loaded the explanation
    if (panel.dataset.loaded === 'true') {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/trees/explain-similarity`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query_newick: lastSearchNewick,
                result_tree_id: treeId
            })
        });
        
        if (!response.ok) throw new Error('Failed to get explanation');
        
        const explanation = await response.json();
        
        // Render the explanation
        panel.innerHTML = renderExplanation(explanation);
        panel.dataset.loaded = 'true';
        
    } catch (error) {
        console.error('Explanation error:', error);
        panel.innerHTML = `
            <div class="explanation-error">
                <span>Could not analyze similarity</span>
            </div>
        `;
    }
}

function renderExplanation(explanation) {
    const featureScores = explanation.feature_scores;
    const comparison = explanation.comparison;
    const reasons = explanation.reasons;
    
    // Build feature bars
    const featureBars = Object.entries(featureScores).map(([key, data]) => {
        const score = data.score;
        const percent = Math.round(score * 100);
        const barClass = score > 0.7 ? 'high' : score > 0.4 ? 'medium' : 'low';
        
        return `
            <div class="feature-row">
                <span class="feature-icon">${data.icon}</span>
                <span class="feature-label">${data.label}</span>
                <div class="feature-bar-container">
                    <div class="feature-bar ${barClass}" style="width: ${percent}%"></div>
                </div>
                <span class="feature-percent">${percent}%</span>
            </div>
        `;
    }).join('');
    
    // Build comparison table
    const comparisonHtml = `
        <div class="comparison-table">
            <div class="comparison-header">
                <span></span>
                <span>Query</span>
                <span>Result</span>
            </div>
            <div class="comparison-row">
                <span>Leaves</span>
                <span>${comparison.query.leaves}</span>
                <span>${comparison.result.leaves}</span>
            </div>
            <div class="comparison-row">
                <span>Avg Depth</span>
                <span>${comparison.query.depth}</span>
                <span>${comparison.result.depth}</span>
            </div>
            <div class="comparison-row">
                <span>Max Depth</span>
                <span>${comparison.query.max_depth}</span>
                <span>${comparison.result.max_depth}</span>
            </div>
            <div class="comparison-row">
                <span>Balance</span>
                <span>${comparison.query.balance}</span>
                <span>${comparison.result.balance}</span>
            </div>
        </div>
    `;
    
    // Build reasons list
    const reasonsHtml = reasons.slice(0, 4).map(reason => {
        const icon = reason.type === 'match' ? '✓' : reason.type === 'similar' ? '≈' : reason.type === 'summary' ? '💡' : '≠';
        const className = reason.type === 'match' ? 'match' : reason.type === 'similar' ? 'similar' : reason.type === 'summary' ? 'summary' : 'different';
        
        return `
            <div class="reason-item ${className}">
                <span class="reason-icon">${icon}</span>
                <span class="reason-text">${reason.text}</span>
            </div>
        `;
    }).join('');
    
    return `
        <div class="explanation-content">
            <div class="explanation-section">
                <h5>Why similar?</h5>
                <div class="reasons-list">${reasonsHtml}</div>
            </div>
            <div class="explanation-section">
                <h5>Feature Breakdown</h5>
                <div class="feature-breakdown">${featureBars}</div>
            </div>
            <div class="explanation-section">
                <h5>Comparison</h5>
                ${comparisonHtml}
            </div>
        </div>
    `;
}

function getScoreClass(score) {
    if (score >= 0.8) return 'score-high';
    if (score >= 0.5) return 'score-medium';
    return 'score-low';
}

function formatScore(score) {
    if (score >= 0) {
        return `${(score * 100).toFixed(0)}% match`;
    }
    return 'Low similarity';
}

// ============== Side-by-Side Comparison View ==============
async function showComparisonView(resultTreeId, score, resultData) {
    const comparisonView = document.getElementById('comparisonView');
    const queryTreeSvg = document.getElementById('queryTreeSvg');
    const resultTreeSvg = document.getElementById('resultTreeSvg');
    const scoreEl = document.getElementById('comparisonScore');
    const explanationEl = document.getElementById('comparisonExplanation');
    
    // Show the comparison view
    comparisonView.classList.remove('hidden');
    
    // Update score badge
    const scorePercent = Math.round(score * 100);
    scoreEl.querySelector('.score-value').textContent = `${scorePercent}%`;
    
    // Update result tree name
    document.getElementById('resultTreeName').textContent = resultData.tree.name;
    
    // Parse and render the query tree
    renderComparisonTree(queryTreeSvg, lastSearchNewick, 'query');
    
    // Update query tree stats
    const queryStats = getTreeStatsFromNewick(lastSearchNewick);
    document.getElementById('queryTreeStats').innerHTML = `
        <span>📊 ${queryStats.nodes} nodes</span>
        <span>🍃 ${queryStats.leaves} leaves</span>
    `;
    
    // Update result tree stats
    document.getElementById('resultTreeStats').innerHTML = `
        <span>📊 ${resultData.tree.num_nodes} nodes</span>
        <span>🍃 ${resultData.tree.num_leaves} leaves</span>
    `;
    
    // Fetch the result tree structure and render it
    try {
        const response = await fetch(`${API_BASE}/trees/${resultTreeId}/structure`);
        if (response.ok) {
            const treeStructure = await response.json();
            renderComparisonTreeFromStructure(resultTreeSvg, treeStructure.root, 'result');
        }
    } catch (error) {
        console.error('Failed to load result tree:', error);
    }
    
    // Fetch and display explanation
    explanationEl.innerHTML = `
        <div class="explanation-loading">
            <div class="spinner small"></div>
            <span>Analyzing...</span>
        </div>
    `;
    
    try {
        const explainResponse = await fetch(`${API_BASE}/trees/explain-similarity`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query_newick: lastSearchNewick,
                result_tree_id: resultTreeId
            })
        });
        
        if (explainResponse.ok) {
            const explanation = await explainResponse.json();
            explanationEl.innerHTML = renderCompactExplanation(explanation);
        } else {
            explanationEl.innerHTML = '<p class="error-text">Could not load explanation</p>';
        }
    } catch (error) {
        console.error('Explanation error:', error);
        explanationEl.innerHTML = '<p class="error-text">Could not load explanation</p>';
    }
    
    // Scroll to comparison view
    comparisonView.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderCompactExplanation(explanation) {
    const featureScores = explanation.feature_scores;
    const reasons = explanation.reasons;
    
    // Build compact feature bars
    const featureBars = Object.entries(featureScores).map(([key, data]) => {
        const score = data.score;
        const percent = Math.round(score * 100);
        const barClass = score > 0.7 ? 'high' : score > 0.4 ? 'medium' : 'low';
        
        return `
            <div class="feature-row">
                <span class="feature-icon">${data.icon}</span>
                <div class="feature-bar-container">
                    <div class="feature-bar ${barClass}" style="width: ${percent}%"></div>
                </div>
                <span class="feature-percent">${percent}%</span>
            </div>
        `;
    }).join('');
    
    // Build compact reasons
    const reasonsHtml = reasons.slice(0, 3).map(reason => {
        const icon = reason.type === 'match' ? '✓' : reason.type === 'similar' ? '≈' : reason.type === 'summary' ? '💡' : '≠';
        const className = reason.type === 'match' ? 'match' : reason.type === 'similar' ? 'similar' : reason.type === 'summary' ? 'summary' : 'different';
        
        return `
            <div class="reason-item ${className}" style="font-size: 0.75rem; padding: 0.25rem 0;">
                <span class="reason-icon">${icon}</span>
                <span class="reason-text">${reason.text}</span>
            </div>
        `;
    }).join('');
    
    return `
        <div class="reasons-list">${reasonsHtml}</div>
        <h5>Feature Scores</h5>
        <div class="feature-breakdown">${featureBars}</div>
    `;
}

function getTreeStatsFromNewick(newick) {
    // Simple parser to count nodes and leaves from Newick string
    let leaves = 0;
    let internalNodes = 0;
    let depth = 0;
    
    for (let i = 0; i < newick.length; i++) {
        const char = newick[i];
        if (char === '(') {
            depth++;
            internalNodes++;
        } else if (char === ')') {
            depth--;
        } else if (char === ',' || (char === ')' && i > 0)) {
            // Check if previous segment was a leaf
        }
    }
    
    // Count leaves by looking for labels or commas
    const segments = newick.replace(/:[0-9.]+/g, '').split(/[(),;]+/).filter(s => s.trim());
    leaves = segments.length;
    
    return {
        nodes: leaves + internalNodes,
        leaves: leaves
    };
}

function renderComparisonTree(svg, newick, type) {
    // Parse newick and render a simple tree visualization
    const width = svg.clientWidth || 350;
    const height = 280;
    
    svg.innerHTML = '';
    svg.style.height = `${height}px`;
    
    // Parse the newick string into a simple tree structure
    const tree = parseNewickToTree(newick);
    if (!tree) {
        svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#888">Invalid tree</text>';
        return;
    }
    
    // Layout and render the tree
    const nodes = [];
    const links = [];
    
    function layoutTree(node, x, y, level, xSpan) {
        nodes.push({
            name: node.name,
            x,
            y,
            isLeaf: !node.children || node.children.length === 0
        });
        
        if (node.children && node.children.length > 0) {
            const childXSpan = xSpan / node.children.length;
            node.children.forEach((child, i) => {
                const childX = x - xSpan/2 + childXSpan/2 + i * childXSpan;
                const childY = y + 50;
                
                links.push({
                    source: { x, y },
                    target: { x: childX, y: childY }
                });
                
                layoutTree(child, childX, childY, level + 1, childXSpan);
            });
        }
    }
    
    layoutTree(tree, width / 2, 30, 0, width - 60);
    
    // Draw links
    const linksGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    links.forEach(link => {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const d = `M ${link.source.x} ${link.source.y} 
                   L ${link.source.x} ${(link.source.y + link.target.y) / 2}
                   L ${link.target.x} ${(link.source.y + link.target.y) / 2}
                   L ${link.target.x} ${link.target.y}`;
        path.setAttribute('d', d);
        path.setAttribute('class', 'tree-link');
        linksGroup.appendChild(path);
    });
    svg.appendChild(linksGroup);
    
    // Draw nodes
    const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    nodes.forEach(node => {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', `tree-node ${node.isLeaf ? 'leaf' : ''}`);
        g.setAttribute('transform', `translate(${node.x}, ${node.y})`);
        
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('r', node.isLeaf ? 5 : 4);
        circle.setAttribute('cx', 0);
        circle.setAttribute('cy', 0);
        g.appendChild(circle);
        
        if (node.name && node.isLeaf) {
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', 0);
            text.setAttribute('y', 15);
            text.setAttribute('text-anchor', 'middle');
            text.textContent = node.name.length > 8 ? node.name.substring(0, 8) + '..' : node.name;
            g.appendChild(text);
        }
        
        nodesGroup.appendChild(g);
    });
    svg.appendChild(nodesGroup);
}

function renderComparisonTreeFromStructure(svg, root, type) {
    const width = svg.clientWidth || 350;
    const height = 280;
    
    svg.innerHTML = '';
    svg.style.height = `${height}px`;
    
    const nodes = [];
    const links = [];
    
    function layoutTree(node, x, y, level, xSpan) {
        nodes.push({
            name: node.name,
            x,
            y,
            isLeaf: node.is_leaf
        });
        
        const children = node.children || [];
        if (children.length > 0) {
            const childXSpan = xSpan / children.length;
            children.forEach((child, i) => {
                const childX = x - xSpan/2 + childXSpan/2 + i * childXSpan;
                const childY = y + 50;
                
                links.push({
                    source: { x, y },
                    target: { x: childX, y: childY }
                });
                
                layoutTree(child, childX, childY, level + 1, childXSpan);
            });
        }
    }
    
    layoutTree(root, width / 2, 30, 0, width - 60);
    
    // Draw links
    const linksGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    links.forEach(link => {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const d = `M ${link.source.x} ${link.source.y} 
                   L ${link.source.x} ${(link.source.y + link.target.y) / 2}
                   L ${link.target.x} ${(link.source.y + link.target.y) / 2}
                   L ${link.target.x} ${link.target.y}`;
        path.setAttribute('d', d);
        path.setAttribute('class', 'tree-link');
        linksGroup.appendChild(path);
    });
    svg.appendChild(linksGroup);
    
    // Draw nodes
    const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    nodes.forEach(node => {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', `tree-node ${node.isLeaf ? 'leaf' : ''}`);
        g.setAttribute('transform', `translate(${node.x}, ${node.y})`);
        
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('r', node.isLeaf ? 5 : 4);
        circle.setAttribute('cx', 0);
        circle.setAttribute('cy', 0);
        g.appendChild(circle);
        
        if (node.name && node.isLeaf) {
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', 0);
            text.setAttribute('y', 15);
            text.setAttribute('text-anchor', 'middle');
            text.textContent = node.name.length > 8 ? node.name.substring(0, 8) + '..' : node.name;
            g.appendChild(text);
        }
        
        nodesGroup.appendChild(g);
    });
    svg.appendChild(nodesGroup);
}

function parseNewickToTree(newick) {
    // Simple recursive Newick parser
    newick = newick.trim();
    if (newick.endsWith(';')) {
        newick = newick.slice(0, -1);
    }
    
    function parse(str) {
        str = str.trim();
        
        // Check if this is a leaf node (no parentheses at the root level)
        if (!str.startsWith('(')) {
            const namePart = str.split(':')[0];
            return { name: namePart || '', children: [] };
        }
        
        // Find the matching closing parenthesis
        let depth = 0;
        let splitPoints = [];
        let i = 0;
        
        // Skip opening parenthesis
        if (str[0] === '(') {
            i = 1;
            depth = 1;
        }
        
        // Find comma positions at depth 1
        while (i < str.length && depth > 0) {
            if (str[i] === '(') depth++;
            else if (str[i] === ')') depth--;
            else if (str[i] === ',' && depth === 1) splitPoints.push(i);
            i++;
        }
        
        // Extract the content inside parentheses
        const innerEnd = i - 1;
        const inner = str.substring(1, innerEnd);
        
        // Get the label after the closing parenthesis
        const afterParen = str.substring(i);
        const labelPart = afterParen.split(':')[0];
        
        // Split by commas at depth 0
        const children = [];
        let lastSplit = 0;
        
        // Re-parse for children
        depth = 0;
        for (let j = 0; j < inner.length; j++) {
            if (inner[j] === '(') depth++;
            else if (inner[j] === ')') depth--;
            else if (inner[j] === ',' && depth === 0) {
                children.push(parse(inner.substring(lastSplit, j)));
                lastSplit = j + 1;
            }
        }
        children.push(parse(inner.substring(lastSplit)));
        
        return { name: labelPart || '', children };
    }
    
    try {
        return parse(newick);
    } catch (e) {
        console.error('Newick parse error:', e);
        return null;
    }
}

// Close comparison view
document.getElementById('closeComparisonBtn').addEventListener('click', () => {
    document.getElementById('comparisonView').classList.add('hidden');
});

async function loadTrees() {
    const treeList = document.getElementById('treeList');
    
    try {
        const response = await fetch(`${API_BASE}/trees`);
        if (!response.ok) throw new Error('Failed to load trees');
        
        const trees = await response.json();
        
        if (trees.length === 0) {
            treeList.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M12 3v18M3 12h18M7 7l10 10M17 7L7 17"/>
                    </svg>
                    <h3>No trees yet</h3>
                    <p>Add a tree using the Newick format above</p>
                </div>
            `;
            return;
        }
        
        treeList.innerHTML = trees.map(tree => `
            <div class="tree-card" data-tree-id="${tree.id}">
                <div class="tree-card-header">
                    <span class="tree-card-name">${tree.name}</span>
                </div>
                <div class="tree-card-stats">
                    <span class="tree-card-stat">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                        ${tree.num_nodes} nodes
                    </span>
                    <span class="tree-card-stat">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2a10 10 0 1 0 10 10"/>
                        </svg>
                        ${tree.num_leaves} leaves
                    </span>
                </div>
            </div>
        `).join('');
        
        // Add click handlers
        document.querySelectorAll('.tree-card').forEach(card => {
            card.addEventListener('click', () => {
                const treeId = card.dataset.treeId;
                visualizeTree(treeId);
            });
        });
        
    } catch (error) {
        console.error('Load trees error:', error);
        treeList.innerHTML = `
            <div class="empty-state">
                <h3>Failed to load trees</h3>
                <p>Please try refreshing</p>
            </div>
        `;
    }
}

async function visualizeTree(treeId) {
    currentTreeId = treeId;
    
    try {
        const response = await fetch(`${API_BASE}/trees/${treeId}/structure`);
        if (!response.ok) throw new Error('Failed to load tree structure');
        
        treeData = await response.json();
        
        document.getElementById('currentTreeName').textContent = treeData.name;
        document.getElementById('treeVisualization').classList.remove('hidden');
        document.getElementById('treeListContainer').classList.add('hidden');
        
        renderTree(treeData.root);
        
    } catch (error) {
        console.error('Visualize tree error:', error);
        showToast('Failed to load tree visualization', 'error');
    }
}

document.getElementById('closeTreeBtn').addEventListener('click', () => {
    document.getElementById('treeVisualization').classList.add('hidden');
    document.getElementById('treeListContainer').classList.remove('hidden');
    document.getElementById('nodeInfoPanel').classList.add('hidden');
    currentTreeId = null;
    currentNodeId = null;
    // Reset selection mode
    selectionMode = false;
    selectedSubtreeRoot = null;
    selectedSubtreeNodeIds = [];
    document.getElementById('selectionModeToggle').checked = false;
    document.getElementById('selectionBanner').classList.add('hidden');
    document.getElementById('treeSvg').classList.remove('selection-mode');
});

// ============== Selection Mode ==============
document.getElementById('selectionModeToggle').addEventListener('change', (e) => {
    selectionMode = e.target.checked;
    const banner = document.getElementById('selectionBanner');
    const svg = document.getElementById('treeSvg');
    
    if (selectionMode) {
        banner.classList.remove('hidden');
        svg.classList.add('selection-mode');
        // Clear any previous selection
        clearSubtreeSelection();
        // Hide node info panel in selection mode
        document.getElementById('nodeInfoPanel').classList.add('hidden');
    } else {
        banner.classList.add('hidden');
        svg.classList.remove('selection-mode');
        clearSubtreeSelection();
    }
});

function clearSubtreeSelection() {
    selectedSubtreeRoot = null;
    selectedSubtreeNodeIds = [];
    document.getElementById('searchSelectedSubtreeBtn').disabled = true;
    
    // Clear visual selection
    document.querySelectorAll('.tree-node').forEach(n => {
        n.classList.remove('subtree-selected');
    });
    document.querySelectorAll('.tree-link').forEach(l => {
        l.classList.remove('subtree-path');
    });
}

async function selectSubtreeAt(nodeId) {
    if (!currentTreeId || !nodeId) return;
    
    try {
        // Get subtree info from API
        const response = await fetch(
            `${API_BASE}/trees/${currentTreeId}/subtree/${nodeId}/newick`
        );
        
        if (!response.ok) throw new Error('Failed to get subtree');
        
        const data = await response.json();
        
        // Store selection
        selectedSubtreeRoot = nodeId;
        selectedSubtreeNodeIds = data.node_ids;
        
        // Highlight the subtree
        highlightSubtree(data.node_ids);
        
        // Enable search button
        const btn = document.getElementById('searchSelectedSubtreeBtn');
        btn.disabled = false;
        btn.dataset.newick = data.newick;
        btn.dataset.nodeCount = data.node_count;
        
        showToast(`Selected subtree with ${data.node_count} nodes`, 'success');
        
    } catch (error) {
        console.error('Select subtree error:', error);
        showToast('Failed to select subtree', 'error');
    }
}

// Search selected subtree button
document.getElementById('searchSelectedSubtreeBtn').addEventListener('click', async () => {
    const btn = document.getElementById('searchSelectedSubtreeBtn');
    const newick = btn.dataset.newick;
    
    if (!newick) {
        showToast('No subtree selected', 'error');
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <path d="M21 12a9 9 0 11-6.219-8.56"/>
        </svg>
        Searching...
    `;
    
    try {
        const response = await fetch(`${API_BASE}/trees/search/similar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ newick, limit: 10 })
        });
        
        if (!response.ok) throw new Error('Search failed');
        
        const results = await response.json();
        
        // Populate the search input and show results
        document.getElementById('searchNewickInput').value = newick;
        displayTreeSearchResults(results);
        
        showToast(`Found ${results.length} similar trees!`, 'success');
        
    } catch (error) {
        console.error('Subtree search error:', error);
        showToast('Search failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="M21 21l-4.35-4.35"/>
            </svg>
            Search Selected Subtree
        `;
    }
});

function renderTree(root) {
    const svg = document.getElementById('treeSvg');
    const width = svg.clientWidth || 800;
    const height = 400;
    
    // Clear previous content
    svg.innerHTML = '';
    
    // Calculate tree layout
    const nodes = [];
    const links = [];
    
    function traverse(node, x, y, level, xSpan) {
        nodes.push({
            id: node.id,
            name: node.name,
            x,
            y,
            isLeaf: node.is_leaf,
            depth: node.depth,
            branchLength: node.branch_length,
            sequenceId: node.sequence_id
        });
        
        const children = node.children || [];
        if (children.length > 0) {
            const childXSpan = xSpan / children.length;
            children.forEach((child, i) => {
                const childX = x - xSpan/2 + childXSpan/2 + i * childXSpan;
                const childY = y + 60;
                
                links.push({
                    source: { x, y },
                    target: { x: childX, y: childY },
                    sourceId: node.id,
                    targetId: child.id
                });
                
                traverse(child, childX, childY, level + 1, childXSpan);
            });
        }
    }
    
    traverse(root, width / 2, 40, 0, width - 100);
    
    // Create SVG group for links
    const linksGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    linksGroup.setAttribute('class', 'links');
    
    links.forEach(link => {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        // Create an L-shaped path for tree branches
        const d = `M ${link.source.x} ${link.source.y} 
                   L ${link.source.x} ${(link.source.y + link.target.y) / 2}
                   L ${link.target.x} ${(link.source.y + link.target.y) / 2}
                   L ${link.target.x} ${link.target.y}`;
        path.setAttribute('d', d);
        path.setAttribute('class', 'tree-link');
        path.dataset.sourceId = link.sourceId;
        path.dataset.targetId = link.targetId;
        linksGroup.appendChild(path);
    });
    
    svg.appendChild(linksGroup);
    
    // Create SVG group for nodes
    const nodesGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    nodesGroup.setAttribute('class', 'nodes');
    
    nodes.forEach(node => {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('class', `tree-node ${node.isLeaf ? 'leaf' : ''}`);
        g.setAttribute('transform', `translate(${node.x}, ${node.y})`);
        g.dataset.nodeId = node.id;
        
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('r', node.isLeaf ? 6 : 5);
        circle.setAttribute('cx', 0);
        circle.setAttribute('cy', 0);
        g.appendChild(circle);
        
        if (node.name) {
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', 0);
            text.setAttribute('y', node.isLeaf ? 20 : -12);
            text.setAttribute('text-anchor', 'middle');
            text.textContent = node.name.length > 12 ? node.name.substring(0, 12) + '...' : node.name;
            g.appendChild(text);
        }
        
        // Click handler
        g.addEventListener('click', () => selectNode(node));
        
        nodesGroup.appendChild(g);
    });
    
    svg.appendChild(nodesGroup);
    
    // Adjust SVG height based on tree depth
    const maxY = Math.max(...nodes.map(n => n.y)) + 60;
    svg.style.height = `${Math.max(maxY, 350)}px`;
}

function selectNode(node) {
    // If in selection mode, select subtree instead of showing info panel
    if (selectionMode) {
        selectSubtreeAt(node.id);
        return;
    }
    
    currentNodeId = node.id;
    
    // Clear previous selection
    document.querySelectorAll('.tree-node').forEach(n => {
        n.classList.remove('selected', 'ancestor', 'subtree-selected');
    });
    document.querySelectorAll('.tree-link').forEach(l => {
        l.classList.remove('ancestor-path', 'subtree-path');
    });
    
    // Highlight selected node
    const selectedNode = document.querySelector(`[data-node-id="${node.id}"]`);
    if (selectedNode) {
        selectedNode.classList.add('selected');
    }
    
    // Show node info panel
    const panel = document.getElementById('nodeInfoPanel');
    const content = document.getElementById('nodeInfoContent');
    
    content.innerHTML = `
        <div class="node-info-item">
            <span class="node-info-label">Type</span>
            <span class="node-info-value">${node.isLeaf ? 'Leaf' : 'Internal'}</span>
        </div>
        <div class="node-info-item">
            <span class="node-info-label">Depth</span>
            <span class="node-info-value">${node.depth}</span>
        </div>
        <div class="node-info-item">
            <span class="node-info-label">Branch Length</span>
            <span class="node-info-value">${node.branchLength.toFixed(4)}</span>
        </div>
        ${node.name ? `
        <div class="node-info-item">
            <span class="node-info-label">Name</span>
            <span class="node-info-value">${node.name}</span>
        </div>
        ` : ''}
        ${node.sequenceId ? `
        <div class="node-info-item">
            <span class="node-info-label">Sequence</span>
            <span class="node-info-value">${truncateId(node.sequenceId)}</span>
        </div>
        ` : ''}
    `;
    
    panel.classList.remove('hidden');
}

document.getElementById('closeNodeInfo').addEventListener('click', () => {
    document.getElementById('nodeInfoPanel').classList.add('hidden');
    document.querySelectorAll('.tree-node').forEach(n => {
        n.classList.remove('selected', 'ancestor');
    });
    document.querySelectorAll('.tree-link').forEach(l => {
        l.classList.remove('ancestor-path');
    });
    currentNodeId = null;
});

document.getElementById('showAncestorsBtn').addEventListener('click', async () => {
    if (!currentTreeId || !currentNodeId) return;
    
    try {
        const response = await fetch(`${API_BASE}/trees/${currentTreeId}/ancestors/${currentNodeId}`);
        if (!response.ok) throw new Error('Failed to get ancestors');
        
        const data = await response.json();
        
        // Highlight ancestor nodes
        data.ancestors.forEach(ancestor => {
            const node = document.querySelector(`[data-node-id="${ancestor.id}"]`);
            if (node) {
                node.classList.add('ancestor');
            }
        });
        
        // Highlight ancestor paths
        const ancestorIds = new Set(data.ancestors.map(a => a.id));
        ancestorIds.add(currentNodeId);
        
        document.querySelectorAll('.tree-link').forEach(link => {
            if (ancestorIds.has(link.dataset.sourceId) && ancestorIds.has(link.dataset.targetId)) {
                link.classList.add('ancestor-path');
            }
        });
        
        showToast(`Found ${data.ancestors.length} ancestors`, 'success');
        
    } catch (error) {
        console.error('Get ancestors error:', error);
        showToast('Failed to get ancestors', 'error');
    }
});

document.getElementById('showDescendantsBtn').addEventListener('click', async () => {
    if (!currentTreeId || !currentNodeId) return;
    
    try {
        const response = await fetch(`${API_BASE}/trees/${currentTreeId}/descendants/${currentNodeId}`);
        if (!response.ok) throw new Error('Failed to get descendants');
        
        const data = await response.json();
        
        // Highlight descendant nodes
        data.descendants.forEach(desc => {
            const node = document.querySelector(`[data-node-id="${desc.id}"]`);
            if (node) {
                node.classList.add('ancestor'); // Reuse the styling
            }
        });
        
        showToast(`Found ${data.descendants.length} descendants`, 'success');
        
    } catch (error) {
        console.error('Get descendants error:', error);
        showToast('Failed to get descendants', 'error');
    }
});

// ============== Interactive Subtree Search ==============
document.getElementById('searchSubtreeBtn').addEventListener('click', async () => {
    if (!currentTreeId || !currentNodeId) return;
    
    const btn = document.getElementById('searchSubtreeBtn');
    btn.disabled = true;
    btn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
            <path d="M21 12a9 9 0 11-6.219-8.56"/>
        </svg>
        <span>Extracting subtree...</span>
    `;
    
    try {
        // Step 1: Extract subtree as Newick and get node IDs for highlighting
        const subtreeResponse = await fetch(
            `${API_BASE}/trees/${currentTreeId}/subtree/${currentNodeId}/newick`
        );
        
        if (!subtreeResponse.ok) {
            throw new Error('Failed to extract subtree');
        }
        
        const subtreeData = await subtreeResponse.json();
        
        // Step 2: Highlight the selected subtree
        highlightSubtree(subtreeData.node_ids);
        
        // Step 3: Update button to show searching
        btn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
                <path d="M21 12a9 9 0 11-6.219-8.56"/>
            </svg>
            <span>Searching...</span>
        `;
        
        // Step 4: Search for similar trees
        const searchResponse = await fetch(`${API_BASE}/trees/search/similar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                newick: subtreeData.newick, 
                limit: 5 
            })
        });
        
        if (!searchResponse.ok) {
            throw new Error('Search failed');
        }
        
        const searchResults = await searchResponse.json();
        
        // Step 5: Display results
        displaySubtreeSearchResults(subtreeData, searchResults);
        
        showToast(`Found ${searchResults.length} similar trees!`, 'success');
        
    } catch (error) {
        console.error('Subtree search error:', error);
        showToast(error.message || 'Search failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/>
                <path d="M21 21l-4.35-4.35"/>
            </svg>
            <span>Search Similar Trees</span>
        `;
    }
});

function highlightSubtree(nodeIds) {
    // Clear previous subtree highlighting
    document.querySelectorAll('.tree-node').forEach(n => {
        n.classList.remove('subtree-selected');
    });
    document.querySelectorAll('.tree-link').forEach(l => {
        l.classList.remove('subtree-path');
    });
    
    // Highlight nodes in subtree
    const nodeIdSet = new Set(nodeIds);
    nodeIds.forEach(nodeId => {
        const node = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (node) {
            node.classList.add('subtree-selected');
        }
    });
    
    // Highlight links within subtree
    document.querySelectorAll('.tree-link').forEach(link => {
        if (nodeIdSet.has(link.dataset.sourceId) && nodeIdSet.has(link.dataset.targetId)) {
            link.classList.add('subtree-path');
        }
    });
}

function displaySubtreeSearchResults(subtreeData, results) {
    // Auto-populate the search field and show results
    const searchInput = document.getElementById('searchNewickInput');
    if (searchInput) {
        searchInput.value = subtreeData.newick;
    }
    
    // Display results in the tree search results section
    displayTreeSearchResults(results);
    
    // Scroll to results if they're not visible
    const resultsContainer = document.getElementById('treeSearchResults');
    if (resultsContainer) {
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// ============== Utility Functions ==============
function truncateId(id) {
    if (!id) return '';
    if (id.length <= 12) return id;
    return id.substring(0, 8) + '...' + id.substring(id.length - 4);
}

function formatValue(value) {
    if (value === null || value === undefined) return 'N/A';
    if (typeof value === 'object') return JSON.stringify(value);
    if (typeof value === 'number') return value.toFixed ? value.toFixed(2) : value;
    return String(value).substring(0, 30);
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============== Stats ==============
async function updateStats() {
    try {
        // Update tree count
        const treesResponse = await fetch(`${API_BASE}/trees`);
        if (treesResponse.ok) {
            const trees = await treesResponse.json();
            document.getElementById('totalTrees').textContent = trees.length;
        }
    } catch (error) {
        console.error('Failed to update stats:', error);
    }
}

// ============== Initialize ==============
updateStats();
// Load trees on startup (trees tab is now default)
loadTrees();
