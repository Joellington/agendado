import os
import time
import threading
import base64
import requests
from flask import Flask, request, jsonify, render_template_string
from tinydb import TinyDB, Query
from datetime import datetime

app = Flask(__name__)
# No Render, o banco de dados temporário funciona assim:
db = TinyDB('database.json')

# --- ROBÔ DE DISPARO (Roda na Nuvem 24h) ---
def bot_worker():
    while True:
        try:
            now = datetime.now().timestamp() * 1000
            Job = Query()
            # Busca mensagens agendadas para agora ou passado que não foram enviadas
            pending_jobs = db.search((Job.sent == False) & (Job.time <= now))
            
            for job in pending_jobs:
                token = job['token']
                chat_id = job['chat']
                text = job['text']
                url = f"https://api.telegram.org/bot{token}/"
                
                if job.get('photo'):
                    header, encoded = job['photo'].split(",", 1)
                    photo_data = base64.b64decode(encoded)
                    files = {'photo': ('image.jpg', photo_data)}
                    payload = {'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}
                    requests.post(url + "sendPhoto", data=payload, files=files)
                else:
                    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
                    requests.post(url + "sendMessage", data=payload)
                
                db.update({'sent': True}, Job.id == job['id'])
        except Exception as e:
            print(f"Erro no envio: {e}")
        time.sleep(30)

# --- ROTAS DA API ---
@app.route('/')
def index():
    return render_template_string(HTML_CODE)

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    return jsonify(db.all())

@app.route('/api/save', methods=['POST'])
def save_job():
    db.insert(request.json)
    return jsonify({"status": "ok"})

@app.route('/api/delete', methods=['POST'])
def delete_job():
    job_id = request.json.get('id')
    db.remove(Query().id == job_id)
    return jsonify({"status": "deleted"})

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    C = Query()
    if request.method == 'POST':
        db.remove(C.type == 'config')
        db.insert({'type': 'config', 'token': request.json['token'], 'chat': request.json['chat']})
        return jsonify({"ok": True})
    res = db.search(C.type == 'config')
    return jsonify(res[0] if res else {"token": "", "chat": ""})

# --- INTERFACE HTML COMPLETA ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Ads Cloud</title>
    <style>
        :root { --blue: #0088cc; --red: #e74c3c; --bg: #f4f7f6; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .app { max-width: 500px; margin: auto; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--blue); color: white; padding: 25px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; font-size: 14px; }
        input, textarea, select { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 12px; box-sizing: border-box; }
        button { width: 100%; padding: 15px; border: none; border-radius: 12px; font-weight: bold; cursor: pointer; transition: 0.3s; margin-top: 10px; }
        .btn-blue { background: var(--blue); color: white; }
        .btn-gray { background: #6c757d; color: white; }
        .btn-add { background: #2ecc71; color: white; font-size: 12px; padding: 10px; }
        .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px; }
        .profile-card { background: #fff; border: 2px solid #eee; padding: 15px; border-radius: 12px; text-align: center; cursor: pointer; }
        .profile-card:hover { border-color: var(--blue); }
        .phrase-box { background: #f9f9f9; padding: 10px; border-radius: 12px; max-height: 120px; overflow-y: auto; border: 1px solid #eee; margin-bottom: 10px; }
        .phrase-item { font-size: 12px; padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }
        
        /* Histórico */
        .job-card { background: #fff; border: 1px solid #eee; padding: 15px; border-radius: 15px; margin-top: 15px; position: relative; display: flex; align-items: center; }
        .job-card img { width: 50px; height: 50px; border-radius: 8px; object-fit: cover; margin-right: 15px; }
        .job-data { font-size: 12px; flex-grow: 1; }
        .job-data strong { color: var(--blue); }
        .btn-trash { background: #fee; color: var(--red); width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; position: absolute; top: 10px; right: 10px; border: 1px solid #fcc; }
    </style>
</head>
<body>
<div class="app">
    <div class="header"><h1>Marketing Cloud</h1></div>
    <div class="p-20">
        <!-- TELA LOGIN -->
        <div id="screen-login">
            <label>Entrar como:</label>
            <div id="profiles" class="profile-grid"></div>
            <button class="btn-add" onclick="addProfile()">+ Adicionar Nova Pessoa</button>
            <button class="btn-gray" onclick="openAdmin()">⚙️ Configurar Bot (Admin)</button>
        </div>

        <!-- TELA ADMIN -->
        <div id="screen-admin" class="hidden">
            <h3>⚙️ Configuração Principal</h3>
            <label>Token do Bot:</label><input type="password" id="c-token">
            <label>ID do Canal:</label><input type="text" id="c-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR CONFIGURAÇÕES</button>
            <button onclick="location.reload()">Voltar</button>
        </div>

        <!-- TELA AGENDADOR -->
        <div id="screen-user" class="hidden">
            <h3 id="u-tag"></h3>
            <div class="phrase-box" id="u-phrases"></div>
            <textarea id="u-msg" rows="3" placeholder="Mensagem principal..."></textarea>
            <label>Frase do Link:</label><input type="text" id="u-ltxt" placeholder="Ex: 👉 CLIQUE AQUI AGORA!">
            <label>Link:</label><input type="url" id="u-lurl">
            <label>Foto:</label><input type="file" id="u-img" accept="image/*">
            <div style="display:flex; gap:10px;">
                <div style="flex:2"><label>Início:</label><input type="datetime-local" id="u-date"></div>
                <div style="flex:1"><label>Dias:</label><input type="number" id="u-days" value="1"></div>
            </div>
            <label>Vezes ao dia:</label>
            <select id="u-freq"><option value="1">1x dia</option><option value="3">3x dia</option><option value="6">6x dia</option></select>
            <button class="btn-blue" onclick="schedule()">PROGRAMAR NA NUVEM</button>
            <hr>
            <h4>📦 Fila de Disparos Ativos</h4>
            <div id="history"></div>
            <button class="btn-gray" onclick="location.reload()">Sair do Perfil</button>
        </div>
    </div>
</div>

<script>
    let botCfg = {token:'', chat:''};
    let profiles = JSON.parse(localStorage.getItem('p_list')) || ["Admin", "Marketing", "Vendas"];
    const frases = ["🚀 Ganhe bônus de 100%!", "🔥 Promoção exclusiva hoje!", "🎯 Apostas grátis liberadas!", "💰 Link VIP atualizado!", "🚨 ÚLTIMAS VAGAS!"];

    function loadLogin() {
        const div = document.getElementById('profiles'); div.innerHTML = "";
        profiles.forEach(p => div.innerHTML += `<div class="profile-card" onclick="openUser('${p}')">${p}</div>`);
    }
    function addProfile() { const n = prompt("Nome:"); if(n){ profiles.push(n); localStorage.setItem('p_list', JSON.stringify(profiles)); loadLogin(); } }
    
    async function openAdmin() { if(prompt("Senha:") === "123456") { document.getElementById('screen-login').classList.add('hidden'); document.getElementById('screen-admin').classList.remove('hidden'); const r = await fetch('/api/config').then(res=>res.json()); document.getElementById('c-token').value = r.token; document.getElementById('c-chat').value = r.chat; } }
    async function saveAdmin() { await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:document.getElementById('c-token').value, chat:document.getElementById('c-chat').value})}); location.reload(); }

    async function openUser(n) {
        botCfg = await fetch('/api/config').then(r=>r.json());
        if(!botCfg.token) return alert("Admin não configurou o sistema!");
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('u-tag').innerText = "Perfil: " + n;
        const box = document.getElementById('u-phrases'); box.innerHTML = "";
        frases.forEach(f => { let d = document.createElement('div'); d.className='phrase-item'; d.innerText=f; d.onclick=()=>document.getElementById('u-msg').value=f; box.appendChild(d); });
        updateHistory();
    }

    async function schedule() {
        const file = document.getElementById('u-img').files[0];
        const img = file ? await toB64(file) : null;
        const start = new Date(document.getElementById('u-date').value).getTime();
        const days = parseInt(document.getElementById('u-days').value);
        const freq = parseInt(document.getElementById('u-freq').value);
        const interval = (24/freq)*60*60*1000;
        
        for(let i=0; i<(days*freq); i++) {
            const data = {
                id: Date.now() + i,
                token: botCfg.token, chat: botCfg.chat,
                text: document.getElementById('u-msg').value + `\\n\\n<a href="${document.getElementById('u-lurl').value}">${document.getElementById('u-ltxt').value}</a>`,
                phrase: document.getElementById('u-msg').value,
                time: start + (i * interval),
                photo: img, sent: false
            };
            await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
        }
        alert("Agendado!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch('/api/jobs').then(r=>r.json());
        const div = document.getElementById('history'); div.innerHTML = "";
        jobs.filter(j=>!j.sent).sort((a,b)=>a.time - b.time).forEach(j => {
            div.innerHTML += `<div class="job-card">
                <button class="btn-trash" onclick="delJob(${j.id})">🗑️</button>
                ${j.photo ? '<img src="'+j.photo+'">' : ''}
                <div class="job-data"><strong>📅 ${new Date(j.time).toLocaleString()}</strong><br>${j.phrase.substring(0,30)}...</div>
            </div>`;
        });
    }

    async function delJob(id) { if(confirm("Apagar?")) { await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})}); updateHistory(); } }
    const toB64 = f => new Promise(r => { const rd = new FileReader(); rd.readAsDataURL(f); rd.onload = () => r(rd.result); });
    loadLogin();
</script>
</body>
</html>
"""

if __name__ == '__main__':
    # Inicia o robô em segundo plano
    threading.Thread(target=bot_worker, daemon=True).start()
    # Pega a porta automática do Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
