// API Base URL
const API_BASE = '';

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;
        
        // Update active states
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        tab.classList.add('active');
        document.getElementById(tabName).classList.add('active');
    });
});

// Search type toggle
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

// Search functionality
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
            alert('Please enter a sequence');
            return;
        }
    } else {
        payload.metadata_filter = document.getElementById('metadataFilter').value.trim();
        if (!payload.metadata_filter) {
            alert('Please enter a metadata filter');
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
        alert('Search failed. Please try again.');
    }
});

function displayResults(results) {
    const resultsList = document.getElementById('resultsList');
    const resultCount = document.getElementById('resultCount');
    
    resultCount.textContent = `${results.length} result${results.length !== 1 ? 's' : ''}`;
    
    if (results.length === 0) {
        resultsList.innerHTML = '<div class="empty-state">No results found</div>';
        return;
    }
    
    resultsList.innerHTML = results.map(result => `
        <div class="result-card">
            <div class="result-header">
                <div>
                    <div class="result-id">${result.id}</div>
                </div>
                <div class="result-score">${(result.score * 100).toFixed(1)}%</div>
            </div>
            <div class="result-metadata">
                ${Object.entries(result.metadata || {}).map(([key, value]) => 
                    `<span class="metadata-tag">${key}: ${value}</span>`
                ).join('')}
            </div>
        </div>
    `).join('');
}

// Upload functionality
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');

browseBtn.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = 'var(--primary)';
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.style.borderColor = 'var(--border)';
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = 'var(--border)';
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
        progressFill.style.width = '50%';
        progressText.textContent = 'Uploading and processing...';
        
        const response = await fetch(`${API_BASE}/ingest/fasta`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error('Upload failed');
        
        progressFill.style.width = '100%';
        progressText.textContent = 'Upload complete!';
        
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
        setTimeout(() => {
            uploadArea.classList.remove('hidden');
            uploadProgress.classList.add('hidden');
            progressFill.style.width = '0%';
        }, 2000);
    }
}

// Export functionality
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
    } catch (error) {
        console.error('Export error:', error);
        alert('Export failed. Please try again.');
    }
});

// Update stats
async function updateStats() {
    // This would call an API endpoint to get total count
    // For now, we'll skip this as it requires a new endpoint
}

// Initialize
updateStats();
