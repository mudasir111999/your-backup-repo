import os, json, zipfile

base = "/mnt/data/iris-quick-login-extension"
os.makedirs(base, exist_ok=True)

manifest = {
    "manifest_version": 3,
    "name": "IRIS Quick Login Helper",
    "version": "1.0.0",
    "description": "Always-on panel on IRIS login with CSV import/export, AES-GCM vault, and collapse/reopen.",
    "content_scripts": [{
        "matches": [
            "https://iris.fbr.gov.pk/login",
            "https://iris.fbr.gov.pk/login*",
            "https://www.iris.fbr.gov.pk/login",
            "https://www.iris.fbr.gov.pk/login*"
        ],
        "js": ["content.js"],
        "css": ["style.css"],
        "run_at": "document_start"
    }]
}

content_js = r"""
// IRIS Quick Login Helper - content script (MV3)
(() => {
  'use strict';

  // --- constants & utils ---
  const STORAGE_KEY   = 'iris_quick_login_accounts_v1';
  const SETTINGS_KEY  = 'iris_quick_login_settings_v2'; // { autoCollapse, collapsed }
  const PBKDF_ITER    = 250000;
  const VAULT_VERSION = 1;

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const TE = new TextEncoder(), TD = new TextDecoder();
  const escapeHtml = s => (s||'').replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

  const readRaw = () => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); } catch { return []; } };
  const writeRaw = (obj) => localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
  const loadSettings = () => { try { return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}'); } catch { return {}; } };
  const saveSettings = (s) => localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));

  // --- vault ---
  let unlockedAccounts = null, isEncrypted = false, lastPassphrase = null;

  async function deriveKey(pass, salt, iter = PBKDF_ITER){
    const base = await crypto.subtle.importKey('raw', TE.encode(pass), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({ name:'PBKDF2', salt, iterations:iter, hash:'SHA-256' }, base, { name:'AES-GCM', length:256 }, false, ['encrypt','decrypt']);
  }
  async function encryptAccounts(accounts, passphrase){
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv   = crypto.getRandomValues(new Uint8Array(12));
    const key  = await deriveKey(passphrase, salt);
    const ct   = await crypto.subtle.encrypt({ name:'AES-GCM', iv }, key, TE.encode(JSON.stringify(accounts)));
    return { enc:true, v:VAULT_VERSION, iter:PBKDF_ITER, s:btoa(String.fromCharCode(...salt)), iv:btoa(String.fromCharCode(...iv)), d:btoa(String.fromCharCode(...new Uint8Array(ct))) };
  }
  async function decryptVault(vault, passphrase){
    const salt = new Uint8Array(atob(vault.s).split('').map(c=>c.charCodeAt(0)));
    const iv   = new Uint8Array(atob(vault.iv).split('').map(c=>c.charCodeAt(0)));
    const key  = await deriveKey(passphrase, salt, vault.iter||PBKDF_ITER);
    const ct   = new Uint8Array(atob(vault.d).split('').map(c=>c.charCodeAt(0)));
    const pt   = await crypto.subtle.decrypt({ name:'AES-GCM', iv }, key, ct);
    return JSON.parse(TD.decode(pt));
  }
  function tryLoad(){
    const raw = readRaw();
    if (Array.isArray(raw)) { isEncrypted=false; unlockedAccounts=raw; }
    else if (raw && typeof raw==='object' && raw.enc) { isEncrypted=true; unlockedAccounts=null; }
    else { isEncrypted=false; unlockedAccounts=[]; }
  }
  async function setPassphrase(newPass, currentPass=null){
    if (isEncrypted && !unlockedAccounts) {
      if (!currentPass) throw new Error('Locked');
      unlockedAccounts = await decryptVault(readRaw(), currentPass);
    }
    const vault = await encryptAccounts(unlockedAccounts||[], newPass);
    writeRaw(vault); isEncrypted=true;
  }
  async function unlock(pass){
    const raw = readRaw(); if (!raw || !raw.enc) throw new Error('No encrypted vault');
    unlockedAccounts = await decryptVault(raw, pass); isEncrypted=true;
  }
  async function lock(){ if (isEncrypted) unlockedAccounts = null; }
  async function saveAccounts(){
    if (isEncrypted) {
      if (!unlockedAccounts) throw new Error('Vault locked');
      if (!lastPassphrase) throw new Error('Missing session passphrase');
      const vault = await encryptAccounts(unlockedAccounts, lastPassphrase);
      writeRaw(vault);
    } else {
      writeRaw(unlockedAccounts||[]);
    }
  }

  // --- CSV helpers ---
  const csvEscape = v => `"${String(v??'').replace(/"/g,'""')}"`;
  const accountsToCSV = list => ['label,username,password', ...(list||[]).map(a => [a.label||'',a.username||'',a.password||''].map(csvEscape).join(','))].join('\\r\\n');
  function parseCSV(text){
    const rows=[]; let row=[], cell='', i=0, q=false;
    while (i<text.length){ const ch=text[i];
      if (q){ if (ch === '"'){ if (text[i+1] === '"'){ cell+='"'; i+=2; } else { q=false; i++; } } else { cell+=ch; i++; } }
      else { if (ch === '"'){ q=true; i++; } else if (ch===','){ row.push(cell); cell=''; i++; } else if (ch==='\\r'){ i++; } else if (ch==='\\n'){ row.push(cell); rows.push(row); row=[]; cell=''; i++; } else { cell+=ch; i++; } }
    }
    row.push(cell); rows.push(row);
    if (rows.length && rows[rows.length-1].every(x => x.trim()==='')) rows.pop();
    let start=0; if (rows[0] && rows[0].map(x=>x.trim().toLowerCase()).join(',')==='label,username,password') start=1;
    const out=[]; for (let r=start;r<rows.length;r++){ const [label,u,p]=rows[r]; if ((u||'').trim()&&(p||'').trim()) out.push({ id:Date.now().toString(36)+Math.random().toString(36).slice(2), label:(label||'').trim(), username:(u||'').trim(), password:String(p||'') }); }
    return out;
  }

  // --- field helpers ---
  function findUsernameField(){ for (const sel of ['input[placeholder*="CNIC/NTN" i]','input[placeholder*="CNIC" i]','input[placeholder*="NTN" i]','input[name*="cnic" i]','input[name*="ntn" i]','input#cnic, input#ntn','input[type="text"]','input[type="tel"]']) { const el=$(sel); if (el) return el; } return null; }
  function findPasswordField(){ for (const sel of ['input[type="password"]','input[name*="pass" i]','input#password']) { const el=$(sel); if (el) return el; } return null; }
  function findLoginButton(){ const byType=$('button[type="submit"], input[type="submit"]'); if (byType) return byType; for (const b of $$('button, a, input[type="button"]')){ const t=(b.innerText||b.value||'').trim().toUpperCase(); if (t==='LOGIN'||t.includes('LOG IN')) return b; } const form=$('form'); if (form) return form; return null; }
  function setValue(el,val){ if(!el) return; el.focus(); el.value=val; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); el.blur(); }
  function doFill(u,p,submit=false){ const uf=findUsernameField(), pf=findPasswordField(); if(!uf||!pf){ alert('IRIS Helper: Could not find login fields on this page.'); return; } setValue(uf,u); setValue(pf,p); if(submit){ const t=findLoginButton(); if(t){ if (t.tagName==='FORM'){ t.requestSubmit?t.requestSubmit():t.submit(); } else t.click(); } } }

  // --- UI ---
  function createPanel(){
    if (document.getElementById('iris-helper-panel') || document.getElementById('iris-reopen')) return;

    // CSS via style tag (style.css is also injected by manifest for overrides)
    const style=document.createElement('style');
    style.textContent=`
      #iris-helper-panel{position:fixed;right:16px;top:80px;width:340px;z-index:2147483647;background:#0d2235;color:#fff;border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.35);font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;overflow:hidden}
      #iris-helper-header{display:flex;align-items:center;gap:8px;justify-content:space-between;padding:10px 12px;background:#132a40;border-bottom:1px solid rgba(255,255,255,.08)}
      #iris-helper-title{font-weight:700;letter-spacing:.2px;font-size:14px}
      #iris-helper-actions button{background:#22a6b3;border:none;color:#fff;padding:6px 8px;border-radius:7px;cursor:pointer;font-weight:600}
      #iris-helper-actions button:hover{filter:brightness(1.05)}
      #iris-helper-body{padding:10px 12px;max-height:55vh;overflow:auto}
      #iris-helper-search{width:100%;box-sizing:border-box;border-radius:8px;padding:8px 10px;border:1px solid rgba(255,255,255,.15);background:#0b1b2a;color:#fff;margin-bottom:10px}
      .iris-item{background:#0b1b2a;border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:8px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;gap:8px}
      .iris-item .info{min-width:0}.iris-item .label{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.iris-item .user{opacity:.8;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .iris-btns{display:flex;gap:6px;flex-shrink:0}.iris-btns button{cursor:pointer;border:none;padding:6px 8px;border-radius:6px;font-weight:600}
      .iris-fill{background:#1abc9c;color:#022}.iris-login{background:#2ecc71;color:#022}.iris-edit{background:#f1c40f;color:#222}.iris-del{background:#e74c3c;color:#fff}
      #iris-helper-add{display:none;gap:6px;margin-top:6px}
      #iris-helper-add input{flex:1;padding:8px;border-radius:8px;border:1px solid rgba(255,255,255,.15);background:#0b1b2a;color:#fff}
      #iris-helper-add .save{background:#3498db;color:#fff;border:none;padding:8px 10px;border-radius:8px;cursor:pointer;font-weight:700}
      #iris-helper-footer{padding:8px 12px;font-size:11px;opacity:.8;display:flex;align-items:center;justify-content:space-between;gap:8px}
      #iris-collapse{background:#e0e0e0;color:#222}
      #iris-reopen{position:fixed;right:16px;top:80px;z-index:2147483648;display:none;border:none;padding:8px 10px;border-radius:8px;background:#132a40;color:#fff;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.35);font-weight:700}
      #iris-reopen:hover{filter:brightness(1.05)}
      .iris-hidden{display:none !important}
      #iris-helper-unlock{display:none;gap:6px;margin-bottom:8px}
      #iris-helper-unlock input{flex:1;padding:8px;border-radius:8px;border:1px solid rgba(255,255,255,.15);background:#0b1b2a;color:#fff}
    `;
    (document.head || document.documentElement).appendChild(style);

    const panel=document.createElement('section');
    panel.id='iris-helper-panel';
    panel.innerHTML=`
      <div id="iris-helper-header">
        <div id="iris-helper-title">IRIS Quick Login</div>
        <div id="iris-helper-actions">
          <button id="iris-btn-add">+ Add</button>
          <button id="iris-btn-import">Import CSV</button>
          <button id="iris-btn-export">Export CSV</button>
          <button id="iris-btn-pass">Set/Change Pass</button>
          <button id="iris-btn-lock">Lock</button>
          <button id="iris-collapse" title="Collapse">Collapse</button>
        </div>
      </div>
      <div id="iris-helper-body">
        <div id="iris-helper-unlock">
          <input id="iris-passphrase" type="password" placeholder="Master passphrase" />
          <button id="iris-btn-unlock">Unlock</button>
        </div>
        <input id="iris-helper-search" placeholder="Search label or username..." autocomplete="off" />
        <div id="iris-list"></div>
        <div id="iris-helper-add">
          <input id="iris-add-label" placeholder="Label (e.g., Company A)" />
          <input id="iris-add-user"  placeholder="CNIC/NTN" />
          <input id="iris-add-pass"  placeholder="Password" type="password" />
          <button class="save" id="iris-add-save">Save</button>
        </div>
      </div>
      <div id="iris-helper-footer">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
          <input type="checkbox" id="iris-auto-collapse"> Auto-collapse on load
        </label>
        <div>Data stays in this browser.</div>
      </div>
      <input id="iris-file" type="file" accept=".csv" style="display:none">
    `;
    (document.body || document.documentElement).appendChild(panel);

    const reopen=document.createElement('button'); reopen.id='iris-reopen'; reopen.textContent='IRIS'; (document.body || document.documentElement).appendChild(reopen);

    // refs
    const listEl = $('#iris-list', panel);
    const addWrap = $('#iris-helper-add', panel);
    const searchEl = $('#iris-helper-search', panel);
    const addBtn  = $('#iris-btn-add', panel);
    const importBtn = $('#iris-btn-import', panel);
    const exportBtn = $('#iris-btn-export', panel);
    const passBtn   = $('#iris-btn-pass', panel);
    const lockBtn   = $('#iris-btn-lock', panel);
    const unlockWrap = $('#iris-helper-unlock', panel);
    const passInput  = $('#iris-passphrase', panel);
    const unlockBtn  = $('#iris-btn-unlock', panel);
    const fileInput  = $('#iris-file', panel);
    const collapseBtn = $('#iris-collapse', panel);
    const autoCollapseCb = $('#iris-auto-collapse', panel);

    const settings = Object.assign({ autoCollapse:false, collapsed:false }, loadSettings());
    autoCollapseCb.checked = !!settings.autoCollapse;
    autoCollapseCb.addEventListener('change', () => { settings.autoCollapse = autoCollapseCb.checked; saveSettings(settings); });

    function setLockedUI(locked){
      unlockWrap.style.display = locked ? 'grid' : 'none';
      addBtn.disabled = locked; importBtn.disabled = locked; exportBtn.disabled = locked;
      searchEl.disabled = locked; $('#iris-add-save').disabled = locked;
      lockBtn.textContent = locked ? 'Locked' : 'Lock'; lockBtn.disabled = locked;
      if (locked) listEl.innerHTML = '<div style="opacity:.85;padding:8px;">Vault is locked. Enter passphrase to unlock.</div>';
    }

    function renderItems(filter=''){
      if (isEncrypted && !unlockedAccounts){ setLockedUI(true); return; }
      setLockedUI(false);
      const f = filter.trim().toLowerCase();
      listEl.innerHTML='';
      const accs = unlockedAccounts || [];
      if (!accs.length) { listEl.innerHTML='<div style="opacity:.8;padding:6px;">No accounts yet. Click "Add" or "Import CSV".</div>'; return; }
      accs.filter(a => !f || (a.label||'').toLowerCase().includes(f) || (a.username||'').toLowerCase().includes(f))
          .forEach(acc => {
            const item=document.createElement('div'); item.className='iris-item';
            item.innerHTML=`
              <div class="info">
                <div class="label">${escapeHtml(acc.label || '(no label)')}</div>
                <div class="user">${escapeHtml(acc.username)}</div>
              </div>
              <div class="iris-btns">
                <button class="iris-fill">Fill</button>
                <button class="iris-login">Login</button>
                <button class="iris-edit">Edit</button>
                <button class="iris-del">Del</button>
              </div>`;
            item.querySelector('.iris-fill').addEventListener('click', () => doFill(acc.username, acc.password, false));
            item.querySelector('.iris-login').addEventListener('click', () => doFill(acc.username, acc.password, true));
            item.querySelector('.iris-edit').addEventListener('click', async () => {
              addWrap.style.display='grid'; addWrap.style.gridTemplateColumns='1fr 1fr 1fr auto';
              $('#iris-add-label').value = acc.label||''; $('#iris-add-user').value = acc.username||''; $('#iris-add-pass').value = acc.password||'';
              $('#iris-add-save').onclick = async () => { acc.label=$('#iris-add-label').value.trim(); acc.username=$('#iris-add-user').value.trim(); acc.password=$('#iris-add-pass').value; await saveAccounts(); addWrap.style.display='none'; renderItems(searchEl.value); };
            });
            item.querySelector('.iris-del').addEventListener('click', async () => {
              if (confirm('Delete this account?')){
                const idx=(unlockedAccounts||[]).findIndex(a=>a===acc);
                if (idx>-1) (unlockedAccounts||[]).splice(idx,1);
                await saveAccounts(); renderItems(searchEl.value);
              }
            });
            listEl.appendChild(item);
          });
    }

    // add & save
    $('#iris-add-save').addEventListener('click', async () => {
      const label=$('#iris-add-label').value.trim(), user=$('#iris-add-user').value.trim(), pass=$('#iris-add-pass').value;
      if (!user || !pass) { alert('Username and password are required.'); return; }
      (unlockedAccounts ||= []);
      unlockedAccounts.push({ id: Date.now().toString(36)+Math.random().toString(36).slice(2), label, username:user, password:pass });
      await saveAccounts(); $('#iris-add-label').value=''; $('#iris-add-user').value=''; $('#iris-add-pass').value=''; addWrap.style.display='none'; renderItems(searchEl.value);
    });
    addBtn.addEventListener('click', () => {
      if (isEncrypted && !unlockedAccounts){ alert('Unlock the vault first.'); return; }
      addWrap.style.display = addWrap.style.display === 'grid' ? 'none' : 'grid';
      if (addWrap.style.display === '') addWrap.style.display = 'grid';
      addWrap.style.gridTemplateColumns = '1fr 1fr 1fr auto';
    });
    searchEl.addEventListener('input', () => renderItems(searchEl.value));

    // CSV import/export
    fileInput.addEventListener('change', async (e) => {
      const f=e.target.files[0]; if(!f) return;
      const text = await f.text();
      const rows = parseCSV(text);
      if (!rows.length){ alert('No valid rows found. Use header: label,username,password'); e.target.value=''; return; }
      (unlockedAccounts ||= []).push(...rows);
      await saveAccounts(); renderItems(searchEl.value);
      e.target.value='';
      alert(`Imported ${rows.length} account(s).`);
    });
    importBtn.addEventListener('click', () => { if (isEncrypted && !unlockedAccounts){ alert('Unlock the vault first.'); return; } fileInput.click(); });
    exportBtn.addEventListener('click', () => {
      if (isEncrypted && !unlockedAccounts){ alert('Unlock the vault first.'); return; }
      const blob=new Blob([accountsToCSV(unlockedAccounts||[])], { type:'text/csv;charset=utf-8' });
      const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=`iris-accounts-${new Date().toISOString().slice(0,10)}.csv`;
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href), 1500);
    });

    // passphrase / lock
    passBtn.addEventListener('click', async () => {
      try {
        if (!isEncrypted) {
          const p1=prompt('Create a master passphrase (min 6 chars):',''); if (!p1 || p1.length<6) return alert('Passphrase not set.');
          const p2=prompt('Confirm passphrase:',''); if (p1!==p2) return alert('Mismatch.');
          lastPassphrase=p1; await setPassphrase(p1); alert('Vault enabled and encrypted.'); renderItems(searchEl.value);
        } else {
          const current=prompt('Enter current passphrase to change:',''); if (!current) return;
          await unlock(current); lastPassphrase=current;
          const p1=prompt('New passphrase:',''); if (!p1 || p1.length<6) return alert('Not changed.');
          const p2=prompt('Confirm new passphrase:',''); if (p1!==p2) return alert('Mismatch.');
          lastPassphrase=p1; await setPassphrase(p1, current); alert('Passphrase changed.'); renderItems(searchEl.value);
        }
      } catch(e){ alert('Could not set/change passphrase: '+e.message); }
    });
    lockBtn.addEventListener('click', async () => { try { await lock(); lastPassphrase=null; renderItems(searchEl.value); } catch(e){ alert('Lock failed: '+e.message); } });
    unlockBtn.addEventListener('click', async () => {
      const pass=passInput.value; if(!pass) return alert('Enter passphrase.');
      try { await unlock(pass); lastPassphrase=pass; await saveAccounts(); passInput.value=''; renderItems(searchEl.value); }
      catch(e){ alert('Unlock failed. Check passphrase.'); }
    });

    // collapse / reopen
    function collapsePanel(skipSave=false){
      panel.classList.add('iris-hidden');
      reopen.style.display='block';
      if(!skipSave){ const s=Object.assign({autoCollapse:false,collapsed:false}, loadSettings()); s.collapsed=true; saveSettings(s); }
    }
    function expandPanel(skipSave=false){
      panel.classList.remove('iris-hidden');
      reopen.style.display='none';
      if(!skipSave){ const s=Object.assign({autoCollapse:false,collapsed:false}, loadSettings()); s.collapsed=false; saveSettings(s); }
    }
    collapseBtn.addEventListener('click', () => collapsePanel());
    reopen.addEventListener('click', () => expandPanel());

    // initial render
    tryLoad();
    const s=Object.assign({autoCollapse:false,collapsed:false}, loadSettings());
    if (s.autoCollapse || s.collapsed) collapsePanel(true);
    renderItems();
  }

  // --- HARDCORE mounting ---
  function ensureBody(cb){
    if (document.body) return cb();
    const obs = new MutationObserver(()=>{ if (document.body){ obs.disconnect(); cb(); } });
    obs.observe(document.documentElement || document, { childList:true });
  }
  function mountIfNeeded(){
    if (!document.getElementById('iris-helper-panel') && !document.getElementById('iris-reopen')) {
      ensureBody(createPanel);
    }
  }

  // run immediately, then keep watching
  mountIfNeeded();
  let domObserverStarted = false;
  function startDomObserver(){
    if (domObserverStarted) return; domObserverStarted = true;
    ensureBody(() => {
      const mo = new MutationObserver(() => { mountIfNeeded(); });
      mo.observe(document.body, { childList:true, subtree:true });
    });
  }
  startDomObserver();
  setInterval(mountIfNeeded, 1000);

  // handle SPA-ish navigation
  const _ps = history.pushState, _rs = history.replaceState;
  const fireLocChange = () => window.dispatchEvent(new Event('locationchange'));
  history.pushState = function(){ const r=_ps.apply(this, arguments); fireLocChange(); return r; };
  history.replaceState = function(){ const r=_rs.apply(this, arguments); fireLocChange(); return r; };
  window.addEventListener('popstate', fireLocChange);
  window.addEventListener('hashchange', fireLocChange);
  window.addEventListener('locationchange', mountIfNeeded);
  document.addEventListener('readystatechange', mountIfNeeded);
  document.addEventListener('DOMContentLoaded', mountIfNeeded, { once:true });
  window.addEventListener('load', mountIfNeeded, { once:true });
})();
"""

style_css = r"""/* Optional overrides */"""

# Write files
with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

with open(os.path.join(base, "content.js"), "w", encoding="utf-8") as f:
    f.write(content_js.strip())

with open(os.path.join(base, "style.css"), "w", encoding="utf-8") as f:
    f.write(style_css.strip())

# Create ZIP
zip_path = "D:/Synthetic Data Generator/iris-quick-login-extension.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(base, "manifest.json"), arcname="manifest.json")
    z.write(os.path.join(base, "content.js"), arcname="content.js")
    z.write(os.path.join(base, "style.css"), arcname="style.css")

print("OK", zip_path)
