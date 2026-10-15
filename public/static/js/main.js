// ============================================================
// EV ChargePoint — shared frontend helpers
// ============================================================

// Toast notifications: showToast('Saved', 'success' | 'error' | 'warning' | 'info')
function showToast(message, type = 'success') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    const icons = { success: '\u2713', error: '\u2715', warning: '\u26A0', info: '\u2139' };
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = '<span class="toast-icon">' + (icons[type] || icons.info) +
        '</span><span class="toast-msg"></span>';
    toast.querySelector('.toast-msg').textContent = message;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-show'));
    setTimeout(() => {
        toast.classList.remove('toast-show');
        setTimeout(() => toast.remove(), 300);
    }, 3800);
}

// Indian Rupee formatting
function formatINR(amount) {
    const value = parseFloat(amount);
    return isNaN(value) ? '\u20B90.00' : '\u20B9' + value.toFixed(2);
}

// Escape user data before rendering it as HTML
function escapeHtml(value) {
    return String(value === null || value === undefined ? '' : value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Consistent status badges used across history and admin tables
function statusBadge(status) {
    const map = {
        'PENDING':   ['badge-warning', 'PENDING'],
        'BOOKED':    ['badge-info', 'BOOKED'],
        'CONFIRMED': ['badge-success', 'CONFIRMED'],
        'CHARGING':  ['badge-charging', 'CHARGING'],
        'COMPLETED': ['badge-success', 'COMPLETED'],
        'CANCELLED': ['badge-danger', 'CANCELLED'],
        'SUCCESS':   ['badge-success', 'PAID'],
        'FAILED':    ['badge-danger', 'FAILED'],
        'ACTIVE':    ['badge-success', 'ACTIVE'],
        'INACTIVE':  ['badge-neutral', 'INACTIVE']
    };
    const entry = map[status] || ['badge-neutral', status];
    return '<span class="badge ' + entry[0] + '">' + entry[1] + '</span>';
}

// Mobile navigation toggle + shared startup
document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('nav-toggle');
    const links = document.getElementById('nav-links');
    if (toggle && links) {
        toggle.addEventListener('click', () => links.classList.toggle('nav-open'));
    }
});

function getCookie(name) {
    let value = "; " + document.cookie;
    let parts = value.split("; " + name + "=");
    if (parts.length == 2) return parts.pop().split(";").shift();
}
