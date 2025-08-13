// Variables globales
let candidatures = [];
let certifications = [];
let competencesPersonnalisees = [];
let editingIndex = -1;

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    loadData();
    loadCompetences();
    
    // Event listeners pour les filtres
    document.getElementById('filterStatus').addEventListener('change', renderCandidatures);
    document.getElementById('filterCompany').addEventListener('input', renderCandidatures);
    document.getElementById('filterSkill').addEventListener('change', renderCandidatures);
});

// Fonctions API
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        alert('Erreur de communication avec le serveur: ' + error.message);
        throw error;
    }
}

async function loadData() {
    try {
        // Charger candidatures
        candidatures = await apiCall('/api/candidatures');
        
        // Charger certifications
        certifications = await apiCall('/api/certifications');
        
        // Mettre à jour l'affichage
        updateStats();
        renderCandidatures();
        checkReminders();
        renderCertifications();
        loadCompetencesInSelects();
    } catch (error) {
        console.error('Erreur lors du chargement des données:', error);
    }
}

async function loadCompetences() {
    try {
        competencesPersonnalisees = await apiCall('/api/competences');
        loadCompetencesInSelects();
    } catch (error) {
        console.error('Erreur lors du chargement des compétences:', error);
    }
}

async function updateStats() {
    try {
        const stats = await apiCall('/api/stats');
        
        document.getElementById('totalCandidatures').textContent = stats.total;
        document.getElementById('envoyees').textContent = stats.envoyees;
        document.getElementById('relancees').textContent = stats.relancees;
        document.getElementById('entretiens').textContent = stats.entretiens;
        document.getElementById('refusees').textContent = stats.refusees;
        document.getElementById('acceptees').textContent = stats.acceptees;
        document.getElementById('tauxReponse').textContent = stats.tauxReponse + '%';
        
        // Ajouter les pourcentages
        const total = stats.total || 1; // Éviter division par 0
        document.getElementById('envoyeesPercent').textContent = Math.round((stats.envoyees / total) * 100) + '%';
        document.getElementById('relanceesPercent').textContent = Math.round((stats.relancees / total) * 100) + '%';
        document.getElementById('entretiensPercent').textContent = Math.round((stats.entretiens / total) * 100) + '%';
        document.getElementById('refuseesPercent').textContent = Math.round((stats.refusees / total) * 100) + '%';
        document.getElementById('accepteesPercent').textContent = Math.round((stats.acceptees / total) * 100) + '%';
    } catch (error) {
        console.error('Erreur lors de la mise à jour des stats:', error);
    }
}

function renderCandidatures() {
    const grid = document.getElementById('candidaturesGrid');
    let filtered = candidatures;

    // Filtres
    const statusFilter = document.getElementById('filterStatus').value;
    const companyFilter = document.getElementById('filterCompany').value.toLowerCase();
    const skillFilter = document.getElementById('filterSkill').value;

    if (statusFilter) {
        filtered = filtered.filter(c => c.status === statusFilter);
    }
    if (companyFilter) {
        filtered = filtered.filter(c => c.company.toLowerCase().includes(companyFilter));
    }
    if (skillFilter) {
        filtered = filtered.filter(c => c.competences && c.competences.includes(skillFilter));
    }

    grid.innerHTML = filtered.map((candidature) => {
        const competencesTags = candidature.competences ? 
            candidature.competences.map(comp => `<span class="tag">${comp}</span>`).join('') : '';
        
        const daysSinceApplication = candidature.dateEnvoi ? 
            Math.floor((Date.now() - new Date(candidature.dateEnvoi)) / (1000 * 60 * 60 * 24)) : 0;

        return `
            <div class="candidature-card">
                <div class="card-header">
                    <div>
                        <div class="company-name">${candidature.company}</div>
                        <div class="position">${candidature.position}</div>
                    </div>
                    <span class="status status-${candidature.status}">${candidature.status}</span>
                </div>
                
                <div class="card-details">
                    ${candidature.dateEnvoi ? `<div class="detail-row">
                        <span class="detail-label">Envoyée le:</span>
                        <span>${new Date(candidature.dateEnvoi).toLocaleDateString('fr-FR')} (${daysSinceApplication}j)</span>
                    </div>` : ''}
                    
                    ${candidature.contactEmail ? `<div class="detail-row">
                        <span class="detail-label">Contact:</span>
                        <span>${candidature.contactEmail}</span>
                    </div>` : ''}
                    
                    ${candidature.lienOffre ? `<div class="detail-row">
                        <span class="detail-label">Offre:</span>
                        <a href="${candidature.lienOffre}" target="_blank">Voir l'offre</a>
                    </div>` : ''}
                </div>

                ${competencesTags ? `<div class="tags">${competencesTags}</div>` : ''}

                ${candidature.notes ? `<div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 8px; font-size: 14px;">
                    <strong>Notes:</strong> ${candidature.notes.substring(0, 100)}${candidature.notes.length > 100 ? '...' : ''}
                </div>` : ''}

                <div class="card-actions">
                    <button class="btn btn-small" onclick="editCandidature(${candidature.id})">✏️ Modifier</button>
                    <button class="btn btn-small" onclick="addRelance(${candidature.id})">📞 Relancer</button>
                    <button class="btn btn-danger btn-small" onclick="deleteCandidature(${candidature.id})">🗑️ Supprimer</button>
                </div>
            </div>
        `;
    }).join('');
}

function openModal(modalId) {
    document.getElementById(modalId).style.display = 'block';
    if (modalId === 'candidatureModal') {
        document.getElementById('modalTitle').textContent = editingIndex >= 0 ? 'Modifier candidature' : 'Nouvelle candidature';
    } else if (modalId === 'competencesModal') {
        renderCompetencesList();
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
    if (modalId === 'candidatureModal') {
        document.getElementById('candidatureForm').reset();
        editingIndex = -1;
    } else if (modalId === 'competencesModal') {
        document.getElementById('competencesForm').reset();
    }
}

// Fermer modal en cliquant en dehors
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}

// Gestion du formulaire candidature
document.getElementById('candidatureForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const competencesSelect = document.getElementById('competences');
    const selectedCompetences = Array.from(competencesSelect.selectedOptions).map(option => option.value);
    
    const candidature = {
        company: document.getElementById('company').value,
        position: document.getElementById('position').value,
        status: document.getElementById('status').value,
        dateEnvoi: document.getElementById('dateEnvoi').value || new Date().toISOString().split('T')[0],
        lienOffre: document.getElementById('lienOffre').value,
        contactEmail: document.getElementById('contactEmail').value,
        contactPhone: document.getElementById('contactPhone').value,
        competences: selectedCompetences,
        notes: document.getElementById('notes').value
    };

    try {
        if (editingIndex >= 0) {
            // Trouver la candidature à modifier
            const candidatureToEdit = candidatures.find(c => c.id === editingIndex);
            if (candidatureToEdit) {
                candidature.relances = candidatureToEdit.relances || [];
                await apiCall(`/api/candidatures/${editingIndex}`, {
                    method: 'PUT',
                    body: JSON.stringify(candidature)
                });
            }
        } else {
            await apiCall('/api/candidatures', {
                method: 'POST',
                body: JSON.stringify(candidature)
            });
        }

        await loadData();
        closeModal('candidatureModal');
    } catch (error) {
        console.error('Erreur lors de la sauvegarde:', error);
    }
});

async function editCandidature(candidatureId) {
    const candidature = candidatures.find(c => c.id === candidatureId);
    if (!candidature) return;
    
    editingIndex = candidatureId;
    
    document.getElementById('company').value = candidature.company;
    document.getElementById('position').value = candidature.position;
    document.getElementById('status').value = candidature.status;
    document.getElementById('dateEnvoi').value = candidature.dateEnvoi;
    document.getElementById('lienOffre').value = candidature.lienOffre || '';
    document.getElementById('contactEmail').value = candidature.contactEmail || '';
    document.getElementById('contactPhone').value = candidature.contactPhone || '';
    document.getElementById('notes').value = candidature.notes || '';
    
    // Sélectionner les compétences
    const competencesSelect = document.getElementById('competences');
    Array.from(competencesSelect.options).forEach(option => {
        option.selected = candidature.competences && candidature.competences.includes(option.value);
    });
    
    openModal('candidatureModal');
}

async function deleteCandidature(candidatureId) {
    if (confirm('Êtes-vous sûr de vouloir supprimer cette candidature ?')) {
        try {
            await apiCall(`/api/candidatures/${candidatureId}`, {
                method: 'DELETE'
            });
            await loadData();
        } catch (error) {
            console.error('Erreur lors de la suppression:', error);
        }
    }
}

async function addRelance(candidatureId) {
    const message = prompt('Message de relance (optionnel):');
    if (message !== null) {
        try {
            await apiCall(`/api/candidatures/${candidatureId}/relance`, {
                method: 'POST',
                body: JSON.stringify({ message })
            });
            await loadData();
        } catch (error) {
            console.error('Erreur lors de l\'ajout de la relance:', error);
        }
    }
}

function checkReminders() {
    const now = new Date();
    const reminders = [];

    candidatures.forEach((candidature) => {
        if (candidature.status === 'envoyee') {
            const applicationDate = new Date(candidature.dateEnvoi);
            const daysSince = Math.floor((now - applicationDate) / (1000 * 60 * 60 * 24));
            
            if (daysSince >= 7) {
                reminders.push({
                    type: 'relance',
                    message: `Relancer ${candidature.company} pour le poste ${candidature.position} (${daysSince} jours)`,
                    action: () => addRelance(candidature.id)
                });
            }
        }
    });

    // Vérifier les certifications qui expirent
    certifications.forEach((cert) => {
        if (cert.expiration) {
            const expDate = new Date(cert.expiration);
            const daysUntilExp = Math.floor((expDate - now) / (1000 * 60 * 60 * 24));
            
            if (daysUntilExp <= 30 && daysUntilExp >= 0) {
                reminders.push({
                    type: 'certification',
                    message: `La certification ${cert.name} expire dans ${daysUntilExp} jours`,
                    action: () => openModal('certificationModal')
                });
            }
        }
    });

    const remindersSection = document.getElementById('remindersSection');
    const remindersList = document.getElementById('remindersList');
    
    if (reminders.length > 0) {
        remindersSection.style.display = 'block';
        remindersList.innerHTML = reminders.map((reminder, index) => `
            <div class="reminder-item">
                <span>${reminder.message}</span>
                <button class="btn btn-small" onclick="executeReminderAction(${index})">Action</button>
            </div>
        `).join('');
        
        // Stocker les actions pour pouvoir les exécuter
        window.reminderActions = reminders.map(r => r.action);
    } else {
        remindersSection.style.display = 'none';
    }
}

function executeReminderAction(index) {
    if (window.reminderActions && window.reminderActions[index]) {
        window.reminderActions[index]();
    }
}

// Gestion des certifications
document.getElementById('certificationForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const certification = {
        name: document.getElementById('certName').value,
        obtention: document.getElementById('certObtention').value,
        expiration: document.getElementById('certExpiration').value
    };

    try {
        await apiCall('/api/certifications', {
            method: 'POST',
            body: JSON.stringify(certification)
        });
        
        await loadData();
        document.getElementById('certificationForm').reset();
    } catch (error) {
        console.error('Erreur lors de l\'ajout de la certification:', error);
    }
});

function renderCertifications() {
    const list = document.getElementById('certificationsList');
    const now = new Date();
    
    list.innerHTML = certifications.map((cert) => {
        let statusClass = '';
        let statusText = '';
        
        if (cert.expiration) {
            const expDate = new Date(cert.expiration);
            const daysUntilExp = Math.floor((expDate - now) / (1000 * 60 * 60 * 24));
            
            if (daysUntilExp < 0) {
                statusClass = 'cert-expired';
                statusText = ` - Expirée depuis ${Math.abs(daysUntilExp)} jours`;
            } else if (daysUntilExp <= 30) {
                statusClass = 'cert-expiring';
                statusText = ` - Expire dans ${daysUntilExp} jours`;
            }
        }
        
        return `
            <div class="certification-item ${statusClass}">
                <div>
                    <strong>${cert.name}</strong><br>
                    <small>
                        Obtenue: ${cert.obtention ? new Date(cert.obtention).toLocaleDateString('fr-FR') : 'Non renseignée'}
                        ${cert.expiration ? ` | Expire: ${new Date(cert.expiration).toLocaleDateString('fr-FR')}` : ''}
                        ${statusText}
                    </small>
                </div>
                <button class="btn btn-danger btn-small" onclick="deleteCertification(${cert.id})">Supprimer</button>
            </div>
        `;
    }).join('');
}

async function deleteCertification(certificationId) {
    if (confirm('Supprimer cette certification ?')) {
        try {
            await apiCall(`/api/certifications/${certificationId}`, {
                method: 'DELETE'
            });
            await loadData();
        } catch (error) {
            console.error('Erreur lors de la suppression de la certification:', error);
        }
    }
}

// Gestion des compétences
document.getElementById('competencesForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const competenceName = document.getElementById('newCompetence').value.trim();
    if (!competenceName) return;

    try {
        const result = await apiCall('/api/competences', {
            method: 'POST',
            body: JSON.stringify({ name: competenceName })
        });
        
        if (result.success) {
            await loadCompetences();
            document.getElementById('newCompetence').value = '';
            renderCompetencesList();
        } else {
            alert('Cette compétence existe déjà !');
        }
    } catch (error) {
        console.error('Erreur lors de l\'ajout de la compétence:', error);
    }
});

function renderCompetencesList() {
    const list = document.getElementById('competencesList');
    
    list.innerHTML = competencesPersonnalisees.map(comp => `
        <div class="certification-item">
            <div><strong>${comp}</strong></div>
            <button class="btn btn-danger btn-small" onclick="deleteCompetence('${comp}')">Supprimer</button>
        </div>
    `).join('');
}

async function deleteCompetence(competenceName) {
    if (confirm(`Supprimer la compétence "${competenceName}" ?`)) {
        try {
            await apiCall(`/api/competences/${encodeURIComponent(competenceName)}`, {
                method: 'DELETE'
            });
            await loadCompetences();
            renderCompetencesList();
        } catch (error) {
            console.error('Erreur lors de la suppression de la compétence:', error);
        }
    }
}

async function resetDefaultCompetences() {
    if (confirm('Réinitialiser la liste des compétences ? Cela supprimera toutes les compétences personnalisées.')) {
        try {
            await apiCall('/api/competences/reset', {
                method: 'POST'
            });
            await loadCompetences();
            renderCompetencesList();
        } catch (error) {
            console.error('Erreur lors de la réinitialisation:', error);
        }
    }
}

function loadCompetencesInSelects() {
    const competencesSelect = document.getElementById('competences');
    const filterSkillSelect = document.getElementById('filterSkill');
    
    // Vider les sélects
    competencesSelect.innerHTML = '';
    filterSkillSelect.innerHTML = '<option value="">Toutes les compétences</option>';
    
    // Remplir avec les compétences
    competencesPersonnalisees.forEach(comp => {
        const option1 = document.createElement('option');
        option1.value = comp;
        option1.textContent = comp;
        competencesSelect.appendChild(option1);
        
        const option2 = document.createElement('option');
        option2.value = comp;
        option2.textContent = comp;
        filterSkillSelect.appendChild(option2);
    });
}

// Export/Import
async function exportData() {
    try {
        const response = await fetch('/api/export/csv');
        if (!response.ok) throw new Error('Erreur lors de l\'export');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `candidatures_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Erreur lors de l\'export:', error);
        alert('Erreur lors de l\'export: ' + error.message);
    }
}

function importData() {
    document.getElementById('importFile').click();
}

async function handleImport(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/import', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`${result.count} candidature(s) importée(s) avec succès !`);
            await loadData();
        } else {
            alert('Erreur lors de l\'importation: ' + result.error);
        }
    } catch (error) {
        console.error('Erreur lors de l\'importation:', error);
        alert('Erreur lors de l\'importation: ' + error.message);
    }
    
    // Reset l'input file
    event.target.value = '';
}

// Fonction de recherche avancée
function searchAdvanced() {
    const searchTerm = prompt('Recherche avancée (entreprise, poste, notes...):');
    if (!searchTerm) return;
    
    const results = candidatures.filter(c => 
        c.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.position.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (c.notes && c.notes.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (c.competences && c.competences.some(comp => 
            comp.toLowerCase().includes(searchTerm.toLowerCase())
        ))
    );
    
    if (results.length > 0) {
        alert(`${results.length} résultat(s) trouvé(s) pour "${searchTerm}"`);
        // Temporairement filtrer l'affichage
        const grid = document.getElementById('candidaturesGrid');
        grid.innerHTML = results.map((candidature) => {
            const competencesTags = candidature.competences ? 
                candidature.competences.map(comp => `<span class="tag">${comp}</span>`).join('') : '';
            
            const daysSinceApplication = candidature.dateEnvoi ? 
                Math.floor((Date.now() - new Date(candidature.dateEnvoi)) / (1000 * 60 * 60 * 24)) : 0;

            return `
                <div class="candidature-card" style="border: 2px solid #4c63b6;">
                    <div class="card-header">
                        <div>
                            <div class="company-name">${candidature.company}</div>
                            <div class="position">${candidature.position}</div>
                        </div>
                        <span class="status status-${candidature.status}">${candidature.status}</span>
                    </div>
                    
                    <div class="card-details">
                        ${candidature.dateEnvoi ? `<div class="detail-row">
                            <span class="detail-label">Envoyée le:</span>
                            <span>${new Date(candidature.dateEnvoi).toLocaleDateString('fr-FR')} (${daysSinceApplication}j)</span>
                        </div>` : ''}
                        
                        ${candidature.contactEmail ? `<div class="detail-row">
                            <span class="detail-label">Contact:</span>
                            <span>${candidature.contactEmail}</span>
                        </div>` : ''}
                        
                        ${candidature.lienOffre ? `<div class="detail-row">
                            <span class="detail-label">Offre:</span>
                            <a href="${candidature.lienOffre}" target="_blank">Voir l'offre</a>
                        </div>` : ''}
                    </div>

                    ${competencesTags ? `<div class="tags">${competencesTags}</div>` : ''}

                    ${candidature.notes ? `<div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 8px; font-size: 14px;">
                        <strong>Notes:</strong> ${candidature.notes.substring(0, 100)}${candidature.notes.length > 100 ? '...' : ''}
                    </div>` : ''}

                    <div class="card-actions">
                        <button class="btn btn-small" onclick="editCandidature(${candidature.id})">✏️ Modifier</button>
                        <button class="btn btn-small" onclick="addRelance(${candidature.id})">📞 Relancer</button>
                        <button class="btn btn-danger btn-small" onclick="deleteCandidature(${candidature.id})">🗑️ Supprimer</button>
                    </div>
                </div>
            `;
        }).join('');
        
        // Bouton pour revenir à l'affichage normal
        grid.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; margin-bottom: 20px;">
                <button class="btn" onclick="renderCandidatures()">🔙 Retour à l'affichage normal</button>
            </div>
        ` + grid.innerHTML;
    } else {
        alert(`Aucun résultat trouvé pour "${searchTerm}"`);
    }
}

// Raccourcis clavier
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey || e.metaKey) {
        switch(e.key) {
            case 'n':
                e.preventDefault();
                openModal('candidatureModal');
                break;
            case 'f':
                e.preventDefault();
                searchAdvanced();
                break;
            case 'e':
                e.preventDefault();
                exportData();
                break;
        }
    }
});

// Notifications système (si supportées)
function requestNotificationPermission() {
    if ("Notification" in window) {
        Notification.requestPermission();
    }
}

function showNotification(title, message) {
    if ("Notification" in window && Notification.permission === "granted") {
        new Notification(title, {
            body: message,
            icon: '/static/favicon.ico'
        });
    }
}

// Vérifier les rappels toutes les heures
setInterval(function() {
    checkReminders();
    const now = new Date();
    candidatures.forEach((candidature) => {
        if (candidature.status === 'envoyee') {
            const applicationDate = new Date(candidature.dateEnvoi);
            const daysSince = Math.floor((now - applicationDate) / (1000 * 60 * 60 * 24));
            
            if (daysSince === 7 || daysSince === 14) {
                showNotification('Rappel de relance', 
                    `Il est temps de relancer ${candidature.company} pour le poste ${candidature.position}`);
            }
        }
    });
}, 3600000); // 1 heure

// Demander permission pour les notifications au chargement
requestNotificationPermission();