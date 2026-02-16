<?php
// CONFIGURATION
$runDir = isset($_GET['run_dir']) ? rtrim($_GET['run_dir'], '/') : '.';
$jsonFile = $runDir . '/data/faq_categorized.json';

// --- BACKEND: HANDLE AJAX REQUESTS ---
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json');

    $input = json_decode(file_get_contents('php://input'), true);
    $action = $input['action'] ?? '';

    // Check file existence
    if (!file_exists($jsonFile)) {
        echo json_encode(['success' => false, 'message' => 'File not found']);
        exit;
    }

    $data = json_decode(file_get_contents($jsonFile), true);

    if ($action === 'save_entry') {
        $id = $input['entry']['id'];
        $updated = false;

        foreach ($data as &$item) {
            if ($item['id'] === $id) {
                // Update editable fields
                // Note: We do NOT update 'source_facts' here, so the baked-in URLs are preserved safe and sound.
                $item['questions'] = $input['entry']['questions'];
                $item['answer'] = $input['entry']['answer'];
                $item['category'] = $input['entry']['category'];
                $item['status'] = $input['entry']['status'];
                $item['admin_notes'] = $input['entry']['admin_notes'];

                // Sync legacy field for backward compatibility
                $item['verified'] = ($input['entry']['status'] === 'approved');

                $updated = true;
                break;
            }
        }

        if ($updated) {
            file_put_contents($jsonFile, json_encode($data, JSON_PRETTY_PRINT), LOCK_EX);
            echo json_encode(['success' => true]);
        } else {
            echo json_encode(['success' => false, 'message' => 'ID not found']);
        }
        exit;
    }
}

// --- FRONTEND: RENDER UI ---
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FAQ QC Tool</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f6f9; }
        .sidebar { height: 100vh; overflow-y: auto; border-right: 1px solid #dee2e6; background: white; }
        .item-list-row { cursor: pointer; border-bottom: 1px solid #f0f0f0; }
        .item-list-row:hover { background-color: #f8f9fa; }
        .item-list-row.active { background-color: #e9ecef; border-left: 4px solid #0d6efd; }
        /* Custom scrollbar for source box */
        #sourceFactsDisplay::-webkit-scrollbar { width: 6px; }
        #sourceFactsDisplay::-webkit-scrollbar-thumb { background-color: #ccc; border-radius: 4px; }
    </style>
</head>
<body>

<div class="container-fluid">
    <div class="row">
        <div class="col-md-3 sidebar p-0">
            <div class="p-3 border-bottom bg-white sticky-top">
                <h5 class="mb-2">Review Queue</h5>
                <div class="d-flex gap-2 mb-2">
                    <select id="filterCategory" class="form-select form-select-sm">
                        <option value="all">All Categories</option>
                    </select>
                    <select id="filterStatus" class="form-select form-select-sm">
                        <option value="all">All Status</option>
                        <option value="pending" selected>Pending</option>
                        <option value="approved">Approved</option>
                        <option value="rejected">Rejected</option>
                        <option value="audit_fail">Audit FAIL</option>
                    </select>
                </div>
                <small class="text-muted" id="countDisplay">Loading...</small>
            </div>
            <div id="itemList" class="list-group list-group-flush">
                </div>
        </div>

        <div class="col-md-9 py-4" style="height: 100vh; overflow-y: auto;">
            <div id="editorArea" class="container" style="max-width: 900px;">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h4 class="m-0"><i class="fas fa-microscope text-primary"></i> QC & Validation</h4>
                    <div class="d-flex gap-2">
                        <div id="auditBadgeArea"></div>
                        <span id="currentStatusBadge" class="badge bg-secondary">Pending</span>
                        <span class="text-muted ms-2 small" id="currentIdDisplay"></span>
                    </div>
                </div>

                <!-- Utility Score Bar -->
                <div id="utilityScoreArea" class="mb-4"></div>

                <div class="card shadow-sm mb-4">
                    <div class="card-header bg-white py-3">
                        <div class="row g-2 align-items-center">
                            <div class="col-md-8">
                                <label class="form-label small text-muted text-uppercase fw-bold">Category</label>
                                <div class="input-group">
                                    <select id="editCategory" class="form-select"></select>
                                    <button class="btn btn-outline-secondary" type="button" id="btnNewCategory" title="Add New Category">
                                        <i class="fas fa-plus"></i>
                                    </button>
                                </div>
                            </div>
                            <div class="col-md-4 text-end">
                                <label class="form-label small text-muted text-uppercase fw-bold d-block">&nbsp;</label>
                                <button type="button" class="btn btn-success me-1" onclick="updateStatus('approved')">
                                    <i class="fas fa-check"></i> Approve
                                </button>
                                <button type="button" class="btn btn-danger" onclick="updateStatus('rejected')">
                                    <i class="fas fa-ban"></i> Strike
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <label class="form-label fw-bold">Question / Topic</label>
                            <input type="text" class="form-control form-control-lg" id="editQuestion">
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-bold">Synthesized Answer</label>
                            <textarea class="form-control" id="editAnswer" rows="6"></textarea>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-bold small text-muted">Source Facts (Reference)</label>
                            <div class="bg-light p-3 rounded border" id="sourceFactsDisplay" style="max-height: 250px; overflow-y: auto; font-size: 0.95em;">
                                </div>
                        </div>

                        <div class="mb-3">
                            <label class="form-label fw-bold small text-muted">Reviewer Notes</label>
                            <input type="text" class="form-control form-control-sm" id="editNotes" placeholder="e.g. Merged with ID 55...">
                        </div>
                    </div>
                    <div class="card-footer d-flex justify-content-between">
                        <button class="btn btn-outline-dark" onclick="navigate(-1)">Previous</button>
                        <button class="btn btn-primary px-4" onclick="saveAndNext()">Save & Next <i class="fas fa-arrow-right ms-2"></i></button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

<script>
    // --- XSS PROTECTION ---
    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;')
            .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }

    // --- STATE ---
    let allData = [];
    let currentFiltered = [];
    let currentIndex = 0;
    let categories = new Set();
    const JSON_FILE = <?php echo json_encode($jsonFile); ?>;
    const SELF_URL = <?php echo json_encode(basename($_SERVER['PHP_SELF'])); ?>;

    $(document).ready(function() {
        // Load JSON directly (with cache buster)
        $.getJSON(JSON_FILE + '?t=' + new Date().getTime(), function(data) {
            allData = data;

            // Extract categories
            categories.clear();
            allData.forEach(item => {
                // Normalize legacy/missing fields
                if(!item.status) item.status = item.verified ? 'approved' : 'pending';
                if(!item.admin_notes) item.admin_notes = '';
                if(item.category) categories.add(item.category);
            });

            populateCategoryDropdowns();
            applyFilters();
        }).fail(function() {
            alert("Could not load " + JSON_FILE);
        });

        // UI Event Listeners
        $('#filterCategory, #filterStatus').on('change', applyFilters);

        $('#btnNewCategory').click(function() {
            let newCat = prompt("Enter new category name:");
            if (newCat) {
                categories.add(newCat);
                populateCategoryDropdowns();
                $('#editCategory').val(newCat);
            }
        });
    });

    // --- LOGIC ---

    function populateCategoryDropdowns() {
        const sortedCats = Array.from(categories).sort();
        const options = sortedCats.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');

        $('#filterCategory').html('<option value="all">All Categories</option>' + options);
        $('#editCategory').html(options);
    }

    function applyFilters() {
        const catFilter = $('#filterCategory').val();
        const statFilter = $('#filterStatus').val();

        currentFiltered = allData.filter(item => {
            const matchCat = (catFilter === 'all') || (item.category === catFilter);

            let matchStat = (statFilter === 'all') || (item.status === statFilter);
            if (statFilter === 'audit_fail') {
                matchStat = (item.audit_status === 'FAIL');
            }

            return matchCat && matchStat;
        });

        currentIndex = 0;
        renderSidebar();
        loadCurrentItem();
    }

    function renderSidebar() {
        const list = $('#itemList');
        list.empty();
        $('#countDisplay').text(`${currentFiltered.length} items found`);

        currentFiltered.forEach((item, index) => {
            // Icons
            let iconClass = 'far fa-circle text-muted';
            if(item.status === 'approved') iconClass = 'fas fa-check-circle text-success';
            if(item.status === 'rejected') iconClass = 'fas fa-times-circle text-danger';

            const activeClass = (index === currentIndex) ? 'active' : '';
            const qText = Array.isArray(item.questions) ? item.questions[0] : item.questions;

            const html = `
                <div class="p-3 item-list-row ${activeClass}" onclick="selectItem(${index})">
                    <div class="d-flex justify-content-between mb-1">
                        <small class="fw-bold text-truncate" style="max-width: 60%">${escapeHtml(item.category)}</small>
                        <div class="d-flex gap-2 align-items-center">
                            ${item.utility_score ? `<span class="badge bg-light text-dark border">${escapeHtml(String(item.utility_score))}</span>` : ''}
                            <span><i class="${iconClass}"></i></span>
                        </div>
                    </div>
                    <div class="small text-dark text-truncate">${escapeHtml(qText)}</div>
                </div>
            `;
            list.append(html);
        });
    }

    function selectItem(index) {
        currentIndex = index;
        renderSidebar();
        loadCurrentItem();
    }

    function loadCurrentItem() {
        if (currentFiltered.length === 0) {
            $('#editorArea').addClass('d-none');
            return;
        }
        $('#editorArea').removeClass('d-none');

        const item = currentFiltered[currentIndex];

        // Fill Form
        $('#currentIdDisplay').text(item.id);
        $('#editCategory').val(item.category);
        $('#editQuestion').val(Array.isArray(item.questions) ? item.questions[0] : item.questions);
        $('#editAnswer').val(item.answer);
        $('#editNotes').val(item.admin_notes || '');

        // Badge
        const badges = { 'pending': 'bg-warning text-dark', 'approved': 'bg-success', 'rejected': 'bg-danger' };
        $('#currentStatusBadge')
            .removeClass()
            .addClass(`badge ${badges[item.status] || 'bg-secondary'}`)
            .text(item.status.toUpperCase());

        // Audit Info
        let auditHtml = '';
        if (item.audit_status) {
            const auditColor = item.audit_status === 'PASS' ? 'success' : 'danger';
            const auditIcon = item.audit_status === 'PASS' ? 'check' : 'exclamation-triangle';
            auditHtml = `<span class="badge bg-${auditColor}" title="${escapeHtml(item.audit_reason || '')}">
                            <i class="fas fa-${auditIcon}"></i> AUDIT: ${escapeHtml(item.audit_status)}
                         </span>`;
        }
        $('#auditBadgeArea').html(auditHtml);

        // Utility Score Bar
        let utilityHtml = '';
        if (item.utility_score) {
            utilityHtml = `
                <div class="card border-0 shadow-sm">
                    <div class="card-body py-2 px-3 bg-white rounded">
                        <div class="row align-items-center">
                            <div class="col-md-2 border-end">
                                <div class="small text-muted text-uppercase fw-bold" style="font-size:0.7rem">Utility</div>
                                <div class="h4 m-0 text-primary">${escapeHtml(String(item.utility_score))}<small class="text-muted" style="font-size:0.5em">/10</small></div>
                            </div>
                            <div class="col-md-10 px-3">
                                <div class="d-flex justify-content-between small text-muted mb-1">
                                    <span>Reach: ${escapeHtml(String(item.score_universality || '?'))}</span>
                                    <span>Impact: ${escapeHtml(String(item.score_criticality || '?'))}</span>
                                    <span>Demand: ${escapeHtml(String(item.score_demand || '?'))}</span>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar" role="progressbar" style="width: ${item.utility_score * 10}%"></div>
                                </div>
                                <div class="small text-muted mt-1 italic">"${escapeHtml(item.score_reason || '')}"</div>
                            </div>
                        </div>
                    </div>
                </div>`;
        }
        $('#utilityScoreArea').html(utilityHtml);

        // RENDER SOURCES WITH BAKED-IN URLS
        let sourcesHtml = '<ul class="list-unstyled m-0">';
        if (item.source_facts && item.source_facts.length > 0) {
            item.source_facts.forEach(fact => {
                let linkHtml = '';

                // Handle live_url as string or array
                let urls = fact.live_url;
                if (urls && !Array.isArray(urls)) {
                    urls = [urls];
                }

                if (urls && urls.length > 0) {
                    linkHtml = urls.map(url =>
                        `<a href="${escapeHtml(url)}" target="_blank" class="text-decoration-none text-primary fw-bold">
                            ${escapeHtml(fact.source)} <i class="fas fa-external-link-alt small ms-1"></i>
                        </a>`
                    ).join(' ');
                } else {
                    linkHtml = `<span class="text-muted">${escapeHtml(fact.source)} (No URL)</span>`;
                }

                sourcesHtml += `
                    <li class="mb-3 border-bottom pb-2">
                        <div class="d-flex align-items-start">
                            <i class="fas fa-info-circle text-primary mt-1 me-2"></i>
                            <div>
                                <div>${escapeHtml(fact.fact)}</div>
                                <small class="text-muted">
                                    <i class="fas fa-link"></i> ${linkHtml}
                                </small>
                            </div>
                        </div>
                    </li>`;
            });
        } else {
            sourcesHtml += '<li class="text-muted">No source facts linked.</li>';
        }
        sourcesHtml += '</ul>';
        $('#sourceFactsDisplay').html(sourcesHtml);
    }

    function updateStatus(newStatus) {
        if(currentFiltered[currentIndex]) {
            currentFiltered[currentIndex].status = newStatus;
            saveAndNext();
        }
    }

    function saveAndNext() {
        const item = currentFiltered[currentIndex];
        if(!item) return;

        // Build update object
        const updatedEntry = {
            id: item.id,
            category: $('#editCategory').val(),
            questions: $('#editQuestion').val(),
            answer: $('#editAnswer').val(),
            status: item.status,
            admin_notes: $('#editNotes').val()
        };

        // Update local memory
        Object.assign(item, updatedEntry);

        // Send to PHP
        $.ajax({
            url: SELF_URL,
            type: 'POST',
            data: JSON.stringify({ action: 'save_entry', entry: updatedEntry }),
            contentType: 'application/json',
            success: function(response) {
                if(response.success) {
                    navigate(1);
                } else {
                    alert("Error saving: " + response.message);
                }
            },
            error: function() {
                alert("Server error.");
            }
        });
    }

    function navigate(direction) {
        let newIndex = currentIndex + direction;
        if (newIndex >= 0 && newIndex < currentFiltered.length) {
            currentIndex = newIndex;
            renderSidebar();
            loadCurrentItem();
            // Scroll sidebar
            const activeItem = document.querySelector('.item-list-row.active');
            if(activeItem) activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } else {
            alert("End of list.");
        }
    }
</script>
</body>
</html>
