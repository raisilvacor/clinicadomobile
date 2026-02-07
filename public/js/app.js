class RepairManager {
    constructor() {
        this.STORAGE_KEY = 'techcell_repairs';
    }

    // Helper: Generate UUID
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Get all repairs
    getAllRepairs() {
        const repairs = localStorage.getItem(this.STORAGE_KEY);
        return repairs ? JSON.parse(repairs) : [];
    }

    // Get single repair
    getRepair(id) {
        const repairs = this.getAllRepairs();
        return repairs.find(r => r.id === id);
    }

    // Create new repair
    createRepair(data) {
        const repairs = this.getAllRepairs();
        
        const newRepair = {
            id: this.generateUUID(),
            created_at: new Date().toISOString(),
            status: 'pendente',
            ...data
        };

        repairs.push(newRepair);
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(repairs));
        return newRepair;
    }

    // Update repair
    updateRepair(id, updates) {
        const repairs = this.getAllRepairs();
        const index = repairs.findIndex(r => r.id === id);
        
        if (index !== -1) {
            repairs[index] = { ...repairs[index], ...updates, updated_at: new Date().toISOString() };
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(repairs));
            return repairs[index];
        }
        return null;
    }

    // Delete repair
    deleteRepair(id) {
        let repairs = this.getAllRepairs();
        repairs = repairs.filter(r => r.id !== id);
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(repairs));
    }
}

// Global instance
const repairManager = new RepairManager();

// UI Helpers
function toggleAdminMenu() {
    const menu = document.querySelector('.admin-nav-links');
    const toggle = document.querySelector('.admin-menu-toggle');
    const overlay = document.querySelector('.admin-menu-overlay');
    
    menu.classList.toggle('active');
    toggle.classList.toggle('active');
    overlay.classList.toggle('active');
    document.body.style.overflow = menu.classList.contains('active') ? 'hidden' : '';
}

// Fechar menu ao clicar em um link
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.admin-nav-links a').forEach(link => {
        link.addEventListener('click', () => {
            if(document.querySelector('.admin-nav-links.active')) {
                toggleAdminMenu();
            }
        });
    });
});
