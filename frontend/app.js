document.addEventListener('DOMContentLoaded', () => {
    // API Configuration
    const API_BASE = ''; // Same origin
    
    // Elements
    const statusIndicator = document.getElementById('apiStatusIndicator');
    const statusText = document.getElementById('apiStatusText');
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.view-section');
    
    // KPI Elements
    const kpiPrecision = document.getElementById('kpiPrecision');
    
    // Form Elements
    const scoreForm = document.getElementById('scoreForm');
    const submitBtn = document.getElementById('submitBtn');
    const resultPanel = document.getElementById('resultPanel');
    
    // Result Elements
    const resProb = document.getElementById('resProb');
    const resTierBadge = document.getElementById('resTierBadge');
    const resFlagged = document.getElementById('resFlagged');
    const gaugeFill = document.getElementById('gaugeFill');
    const featureList = document.getElementById('featureList');
    
    // Initialize
    checkApiStatus();
    loadModelInfo();
    setupNavigation();
    setupForm();
    
    // ---- Functions ----
    
    async function checkApiStatus() {
        try {
            const res = await fetch(`${API_BASE}/health`);
            if (res.ok) {
                statusIndicator.className = 'status-indicator online';
                statusText.textContent = 'API Online';
            } else {
                throw new Error('Status not OK');
            }
        } catch (e) {
            statusIndicator.className = 'status-indicator offline';
            statusText.textContent = 'API Offline';
            console.error('API Check Failed', e);
        }
    }
    
    async function loadModelInfo() {
        try {
            // First load metrics if available
            try {
                const metRes = await fetch(`${API_BASE}/model/metrics`);
                if (metRes.ok) {
                    const metrics = await metRes.json();
                    
                    const pVal = (metrics.precision || 0);
                    animateValue(kpiPrecision, 0, pVal, 1000, true);
                    
                    // Provide some standard values for the dataset if it's the PaySim one
                    document.getElementById('kpiTotalTx').textContent = '2,305,671'; 
                    document.getElementById('kpiFraudCases').textContent = '2,783';
                    document.getElementById('kpiFraudRate').textContent = '0.12%';
                }
            } catch(e) {
                kpiPrecision.textContent = 'N/A';
            }
            
            // Load Model Info
            const res = await fetch(`${API_BASE}/model/info`);
            if (res.ok) {
                const info = await res.json();
                const container = document.getElementById('modelInfoContent');
                container.innerHTML = `
                    <div class="info-item">
                        <div class="info-item-label">Model Type</div>
                        <div class="info-item-val">${info.model_type}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-item-label">Features Count</div>
                        <div class="info-item-val">${info.n_features}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-item-label">Low Risk Threshold</div>
                        <div class="info-item-val">< ${(info.risk_thresholds.LOW * 100).toFixed(0)}%</div>
                    </div>
                    <div class="info-item">
                        <div class="info-item-label">Critical Risk Threshold</div>
                        <div class="info-item-val">> ${(info.risk_thresholds.HIGH * 100).toFixed(0)}%</div>
                    </div>
                `;
            }
        } catch(e) {
            console.error('Model info load failed', e);
            document.getElementById('modelInfoContent').innerHTML = 'Failed to load model information.';
        }
    }
    
    function setupNavigation() {
        navItems.forEach(btn => {
            btn.addEventListener('click', (e) => {
                navItems.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                const targetId = btn.getAttribute('data-target');
                sections.forEach(sec => sec.classList.remove('active'));
                document.getElementById(targetId).classList.add('active');
            });
        });
    }
    
    function setupForm() {
        scoreForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const btnText = submitBtn.querySelector('span');
            const originalText = btnText.innerHTML;
            btnText.innerHTML = '<span class="spinner"></span> Scoring...';
            submitBtn.disabled = true;
            
            const formData = new FormData(scoreForm);
            const data = {
                step: parseInt(formData.get('step')),
                type: formData.get('type'),
                amount: parseFloat(formData.get('amount')),
                nameOrig: formData.get('nameOrig'),
                oldbalanceOrg: parseFloat(formData.get('oldbalanceOrg')),
                newbalanceOrig: parseFloat(formData.get('newbalanceOrig')),
                nameDest: formData.get('nameDest'),
                oldbalanceDest: parseFloat(formData.get('oldbalanceDest')),
                newbalanceDest: parseFloat(formData.get('newbalanceDest')),
            };
            
            try {
                const res = await fetch(`${API_BASE}/predict`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                if (!res.ok) throw new Error('Prediction failed');
                
                const result = await res.json();
                displayResult(result);
                showToast('Transaction scored successfully', 'success');
            } catch (err) {
                showToast('Error scoring transaction: ' + err.message, 'error');
            } finally {
                btnText.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }
    
    function displayResult(data) {
        resultPanel.classList.remove('hidden');
        
        const prob = data.fraud_probability;
        animateValue(resProb, 0, prob * 100, 1000, true);
        
        resTierBadge.textContent = data.risk_tier;
        resTierBadge.className = `tier-badge risk-${data.risk_tier.toLowerCase()}`;
        
        resFlagged.textContent = data.is_flagged ? '🚨 YES' : '✅ NO';
        
        // Update gauge fill width and color
        gaugeFill.style.width = `${prob * 100}%`;
        if(prob < 0.2) gaugeFill.style.background = 'var(--risk-low)';
        else if (prob < 0.5) gaugeFill.style.background = 'var(--risk-medium)';
        else if (prob < 0.8) gaugeFill.style.background = 'var(--risk-high)';
        else gaugeFill.style.background = 'var(--risk-critical)';
        
        // Populate features
        featureList.innerHTML = '';
        const feats = data.features_used;
        let delay = 0;
        for (const [key, value] of Object.entries(feats)) {
            const item = document.createElement('div');
            item.className = 'feature-item stagger-item';
            item.style.animationDelay = `${delay}ms`;
            item.innerHTML = `<span>${key}</span> <span>${value.toFixed(4)}</span>`;
            featureList.appendChild(item);
            delay += 50;
        }
    }

    function showToast(message, type = 'success') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = type === 'success' ? '✅' : '🚨';
        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        
        container.appendChild(toast);
        
        // Trigger reflow for transition
        void toast.offsetWidth;
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    function animateValue(obj, start, end, duration, isPercentage = false) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            
            // easeOutQuart
            const easeOut = 1 - Math.pow(1 - progress, 4);
            const current = start + easeOut * (end - start);
            
            obj.innerHTML = current.toFixed(isPercentage ? 4 : 0) + (isPercentage ? '%' : '');
            
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
});
    

