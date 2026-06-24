import os
import time
import threading
import base64
import requests
from flask import Flask, request, jsonify, render_template_string
from tinydb import TinyDB, Query
from datetime import datetime

app = Flask(__name__)
db = TinyDB('database.json')

# --- ROBÔ DE DISPARO (24H NA NUVEM) ---
def bot_worker():
    while True:
        try:
            now = datetime.now().timestamp() * 1000
            Job = Query()
            # Pega apenas o que ainda não foi enviado e já passou da hora
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
                    requests.post(url + "sendPhoto", data={'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}, files=files)
                else:
                    requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'})
                
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

# --- INTERFACE HTML COM HISTÓRICO DETALHADO ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Marketing Cloud</title>
    <style>
        :root { --blue: #0088cc; --red: #e74c3c; --bg: #f4f7f6; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .app { max-width: 500px; margin: auto; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--blue); color: white; padding: 25px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; font-size: 14px; }
        input, textarea, select { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 12px; box-sizing: border-box; }
        button { width: 100%; padding: 15px; border: none; border-radius: 12px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .btn-blue { background: var(--blue); color: white; }
        .btn-gray { background: #6c757d; color: white; }
        
        /* Estilo do Histórico */
        .history-container { margin-top: 30px; border-top: 2px solid #eee; padding-top: 20px; }
        .job-card { background: white; border: 1px solid #eee; padding: 15px; border-radius: 15px; margin-bottom: 15px; position: relative; display: flex; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
        .job-card img { width: 60px; height: 60px; border-radius: 10px; object-fit: cover; margin-right: 15px; border: 1px solid #eee; }
        .job-info { font-size: 12px; flex-grow: 1; color: #555; }
        .job-info strong { color: var(--blue); display: block; margin-bottom: 4px; }
        .job-info a { color: var(--blue); text-decoration: none; font-weight: bold; }
        .btn-delete { background: #fee; color: var(--red); width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; position: absolute; top: 10px; right: 10px; border: 1px solid #fcc; }
        
        .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .profile-card { background: #fff; border: 2px solid #eee; padding: 15px; border-radius: 12px; text-align: center; cursor: pointer; }
        .profile-card:hover { border-color: var(--blue); }
    </style>
</head>
<body>
<div class="app">
    <div class="header"><h1>Marketing Cloud</h1></div>
    <div class="p-20">
        <!-- LOGIN -->
        <div id="screen-login">
            <label>Entrar como:</label>
            <div id="profiles" class="profile-grid">
                <div class="profile-card" onclick="openUser('Admin')">Admin</div>
                <div class="profile-card" onclick="openUser('Marketing')">Marketing</div>
                <div class="profile-card" onclick="openUser('Equipe Alpha')">Equipe Alpha</div>
                <div class="profile-card" onclick="openUser('Equipe Beta')">Equipe Beta</div>
            </div>
            <button class="btn-gray" onclick="openAdmin()" style="margin-top:20px;">⚙️ Configuração Bot (123456)</button>
        </div>

        <!-- ADMIN -->
        <div id="screen-admin" class="hidden">
            <label>Token do Bot:</label><input type="password" id="c-token">
            <label>ID do Canal:</label><input type="text" id="c-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR AGORA</button>
            <button onclick="location.reload()">Voltar</button>
        </div>

        <!-- AGENDADOR -->
        <div id="screen-user" class="hidden">
            <h3 id="u-tag"></h3>
            <textarea id="u-msg" rows="3" placeholder="Frase da mensagem..."></textarea>
            <label>Texto do Link:</label><input type="text" id="u-ltxt" placeholder="Ex: 👉 CLIQUE AQUI">
            <label>URL do Link:</label><input type="url" id="u-lurl">
            <label>Foto da Galeria:</label><input type="file" id="u-img" accept="image/*">
            <label>Início:</label><input type="datetime-local" id="u-date">
            <label>Repetições:</label>
            <select id="u-freq"><option value="1">1x dia</option><option value="3">3x dia</option><option value="6">6x dia</option></select>
            <label>Por quantos dias?</label><input type="number" id="u-days" value="1">
            <button class="btn-blue" onclick="schedule()">PROGRAMAR DISPAROS</button>
            
            <div class="history-container">
                <h4>📋 Histórico de Agendamentos</h4>
                <div id="history-list"></div>
            </div>
            
            <button class="btn-gray" onclick="location.reload()">Sair do Perfil</button>
        </div>
    </div>
</div>

<script>
    let botCfg = {token:'', chat:''};
    
    async function openAdmin() { if(prompt("Senha:") === "123456") { document.getElementById('screen-login').classList.add('hidden'); document.getElementById('screen-admin').classList.remove('hidden'); const r = await fetch('/api/config').then(res=>res.json()); document.getElementById('c-token').value = r.token; document.getElementById('c-chat').value = r.chat; } }
    async function saveAdmin() { await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:document.getElementById('c-token').value, chat:document.getElementById('c-chat').value})}); location.reload(); }

    async function openUser(n) {
        botCfg = await fetch('/api/config').then(r=>r.json());
        if(!botCfg.token) return alert("Configure o Bot no Admin primeiro!");
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('u-tag').innerText = "Perfil: " + n;
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
                phrase: document.getElementById('u-msg').value,
                link_url: document.getElementById('u-lurl').value,
                text: document.getElementById('u-msg').value + `\\n\\n<a href="${document.getElementById('u-lurl').value}">${document.getElementById('u-ltxt').value}</a>`,
                time: start + (i * interval),
                photo: img, sent: false
            };
            await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
        }
        alert("Mensagens agendadas!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch('/api/jobs').then(r=>r.json());
        const list = document.getElementById('history-list');
        list.innerHTML = "";
        
        // Filtra os que ainda não foram enviados e ordena por data
        jobs.filter(j => !j.sent).sort((a,b) => a.time - b.time).forEach(j => {
            const card = document.createElement('div');
            card.className = 'job-card';
            const imgHtml = j.photo ? `<img src="${j.photo}">` : `<div style="width:60px;height:60px;background:#eee;margin-right:15px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:10px;color:#999;">Sem Foto</div>`;
            
            card.innerHTML = `
                <button class="btn-delete" onclick="delJob(${j.id})">🗑️</button>
                ${imgHtml}
                <div class="job-info">
                    <strong>📅 ${new Date(j.time).toLocaleString()}</strong>
                    <span>Frase: ${j.phrase.substring(0,30)}...</span><br>
                    <a href="${j.link_url}" target="_blank">🔗 Ver Link</a>
                </div>
            `;
            list.appendChild(card);
        });
    }

    async function delJob(id) {
        if(confirm("Deseja apagar este envio e cancelar a mensagem?")) {
            await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
            updateHistory();
        }
    }

    const toB64 = f => new Promise(r => { const rd = new FileReader(); rd.readAsDataURL(f); rd.onload = () => r(rd.result); });
</script>
</body>
</html>
"""

if __name__ == '__main__':
    threading.Thread(target=bot_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
