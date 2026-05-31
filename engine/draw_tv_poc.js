(function() {
    let old = document.getElementById('commander-alert');
    if (old) old.remove();
    
    let banner = document.createElement('div');
    banner.id = 'commander-alert';
    banner.style.position = 'fixed';
    banner.style.top = '15px';
    banner.style.left = '50%';
    banner.style.transform = 'translateX(-50%)';
    banner.style.background = 'rgba(4, 15, 10, 0.95)';
    banner.style.border = '2px solid #00ff66';
    banner.style.color = '#00ff66';
    banner.style.padding = '15px 40px';
    banner.style.fontFamily = 'Consolas, monospace';
    banner.style.fontSize = '18px';
    banner.style.fontWeight = 'bold';
    banner.style.zIndex = '999999999';
    banner.style.borderRadius = '8px';
    banner.style.boxShadow = '0 0 25px rgba(0, 255, 102, 0.6)';
    banner.style.textAlign = 'center';
    banner.style.transition = 'all 0.5s ease';
    banner.style.cursor = 'pointer';
    
    banner.innerHTML = '⚔️ COMMANDER DADANG COMMAND CENTER ONLINE ⚔️<br><span style="font-size: 11px; color: #00cccc; letter-spacing: 1px;">📡 AI UPLINK ESTABLISHED | CDP SECURED PORT 9222</span>';
    
    // Close on click
    banner.onclick = function() {
        banner.style.opacity = '0';
        setTimeout(function() { banner.remove(); }, 500);
    };
    
    document.body.appendChild(banner);
    
    // Pulse animation
    let count = 0;
    setInterval(function() {
        if (count % 2 === 0) {
            banner.style.borderColor = '#00cccc';
            banner.style.boxShadow = '0 0 25px rgba(0, 204, 204, 0.8)';
            banner.style.textShadow = '0 0 5px #00cccc';
        } else {
            banner.style.borderColor = '#00ff66';
            banner.style.boxShadow = '0 0 25px rgba(0, 255, 102, 0.8)';
            banner.style.textShadow = '0 0 5px #00ff66';
        }
        count++;
    }, 1000);
})();
