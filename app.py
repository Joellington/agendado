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

# --- ROBÔ DE DISPARO (Roda 24h na Nuvem) ---
def bot_worker():
    while True:
        try:
            now = datetime.now().timestamp() * 1000
            Job = Query()
            pending_jobs = db.search((Job.sent == False) & (Job.time <= now))
            
            for job in pending_jobs:
                send_telegram(job)
                db.update({'sent': True}, Job.id == job['id'])
        except Exception as e:
            print(f"Erro: {e}")
        time.sleep(30)

def send_telegram(job):
    token = job['token']
    chat_id = job['chat']
    text = job['text']
    url = f"https://api.telegram.org/bot{token}/"
    
    try:
        if job.get('photo'):
            header, encoded = job['photo'].split(",", 1)
            data = base64.b64decode(encoded)
            files = {'photo': ('image.jpg', data)}
            payload = {'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}
            requests.post(url + "sendPhoto", data=payload, files=files)
        else:
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            requests.post(url + "sendMessage", data=payload)
    except:
        pass

# --- INTERFACE E API ---
@app.route('/')
def index():
    return render_template_string(HTML_CODE)

@app.route('/api/jobs')
def get_jobs():
    return jsonify(db.all())

@app.route('/api/save', methods=['POST'])
def save_job():
    db.insert(request.json)
    return jsonify({"status": "ok"})

@app.route('/api/delete', methods=['POST'])
def delete_job():
    db.remove(Query().id == request.json.get('id'))
    return jsonify({"status": "ok"})

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    C = Query()
    if request.method == 'POST':
        db.remove(C.type == 'config')
        db.insert({'type': 'config', 'token': request.json['token'], 'chat': request.json['chat']})
        return jsonify({"ok": True})
    res = db.search(C.type == 'config')
    return jsonify(res[0] if res else {"token": "", "chat": ""})

# --- SEU HTML COMPLETO ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram VIP Scheduler</title>
    <style>
        :root { --primary: #0088cc; --bg: #f0f2f5; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .card { max-width: 500px; margin: auto; background: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--primary); color: white; padding: 20px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        input, textarea, select { width: 100%; padding: 12px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 5px; }
        .btn-blue { background: var(--primary); color: white; }
        .btn-admin { background: #6c757d; color: white; }
        .phrase-box { background: #f8f9fa; border: 1px solid #eee; padding: 10px; max-height: 120px; overflow-y: auto; margin-bottom: 15px; border-radius: 8px; }
        .phrase-item { font-size: 13px; padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }
        .phrase-item:hover { color: var(--primary); }
        .job-card { border-left: 4px solid var(--primary); padding: 10px; background: #fff; margin-top: 10px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
<div class="card">
    <div class="header"><h2>Telegram Marketing</h2></div>
    <div class="p-20">
        <!-- LOGIN -->
        <div id="screen-login">
            <button class="btn-blue" onclick="openUser('Equipe Alpha')">Acessar como Equipe Alpha</button>
            <button class="btn-admin" style="margin-top:15px;" onclick="openAdmin()">🛡️ Administrador</button>
        </div>

        <!-- ADMIN (CONFIGURA ID E TOKEN) -->
        <div id="screen-admin" class="hidden">
            <label>Token do Bot:</label><input type="password" id="cfg-token">
            <label>ID do Canal (Fixo):</label><input type="text" id="cfg-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR CONFIGURAÇÃO FIXA</button>
            <button onclick="location.reload()">Voltar</button>
        </div>

        <!-- USUÁRIO -->
        <div id="screen-user" class="hidden">
            <h4 id="user-info"></h4>
            <label>Escolha uma frase de impacto:</label>
            <div class="phrase-box" id="phrases-list"></div>
            
            <textarea id="msg-text" rows="3" placeholder="Sua mensagem principal..."></textarea>
            
            <label>Texto que vira Link:</label>
            <input type="text" id="link-text" placeholder="Ex: 👉 GANHE BÔNUS DE 100% AGORA!">
            <label>Link de Afiliado:</label>
            <input type="url" id="link-url" placeholder="https://seu-link.com">
            
            <label>Foto da Galeria:</label>
            <input type="file" id="msg-photo" accept="image/*">
            
            <div style="display:flex; gap:10px;">
                <input type="datetime-local" id="msg-date">
                <input type="number" id="msg-days" value="1" placeholder="Dias">
            </div>
            
            <label>Vezes ao dia:</label>
            <select id="msg-freq"><option value="1">1 vez ao dia</option><option value="3">3 vezes ao dia</option><option value="6">6 vezes ao dia</option></select>
            
            <button class="btn-blue" onclick="schedule()">PROGRAMAR NA NUVEM</button>
            
            <div style="margin-top:25px;">
                <strong>Fila de Envios Agendados:</strong>
                <div id="history"></div>
            </div>
            <button class="btn-admin" onclick="location.reload()" style="margin-top:20px;">Sair</button>
        </div>
    </div>
</div>

<script>
    let config = {token: '', chat: ''};
    const frasesMarketing = [
        "🚀 Venha conferir essa oportunidade única!",
        "💰 BÔNUS DE 100% PARA NOVOS USUÁRIOS! Aproveite agora.",
        "🚨 ÚLTIMAS VAGAS! Não perca o que preparamos para você.",
        "💎 Estratégia VIP liberada. Clique no link e veja!",
        "🔥 O mercado está pagando muito hoje, não fique de fora.",
        "🎯 Aproveite a promoção e ganhe apostas grátis!",
        "⚠️ Atenção: O link expira em breve. Corra!"
    ];

    async function openAdmin() {
        if(prompt("Senha do Admin:") === "123456") {
            document.getElementById('screen-login').classList.add('hidden');
            document.getElementById('screen-admin').classList.remove('hidden');
            const res = await fetch('/api/config').then(r => r.json());
            document.getElementById('cfg-token').value = res.token;
            document.getElementById('cfg-chat').value = res.chat;
        }
    }

    async function saveAdmin() {
        const token = document.getElementById('cfg-token').value;
        const chat = document.getElementById('cfg-chat').value;
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token, chat})
        });
        alert("Configuração Salva!"); location.reload();
    }

    async function openUser(name) {
        config = await fetch('/api/config').then(r => r.json());
        if(!config.token) return alert("O administrador ainda não configurou o bot!");
        
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('user-info').innerText = "Perfil: " + name;
        
        const list = document.getElementById('phrases-list');
        frasesMarketing.forEach(f => {
            let d = document.createElement('div'); d.className = 'phrase-item'; d.innerText = f;
            d.onclick = () => document.getElementById('msg-text').value = f;
            list.appendChild(d);
        });
        updateHistory();
    }

    async function schedule() {
        const file = document.getElementById('msg-photo').files[0];
        const photo = file ? await toBase64(file) : null;
        const start = new Date(document.getElementById('msg-date').value).getTime();
        const days = parseInt(document.getElementById('msg-days').value);
        const freq = parseInt(document.getElementById('msg-freq').value);
        const interval = (24/freq)*60*60*1000;

        for(let i=0; i<(days*freq); i++) {
            const data = {
                id: Date.now() + i,
                token: config.token,
                chat: config.chat,
                text: document.getElementById('msg-text').value + `\\n\\n<a href="${document.getElementById('link-url').value}">${document.getElementById('link-text').value}</a>`,
                time: start + (i * interval),
                photo: photo,
                sent: false
            };
            await fetch('/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
        }
        alert("Agendado com sucesso!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch('/api/jobs').then(r => r.json());
        const div = document.getElementById('history');
        div.innerHTML = "";
        jobs.filter(j => !j.sent).sort((a,b) => a.time - b.time).forEach(j => {
            div.innerHTML += `<div class="job-card">
                <div>📅 <strong>${new Date(j.time).toLocaleString()}</strong></div>
                <button onclick="delJob(${j.id})" style="width:auto; background:red; color:white; padding:4px 8px; margin:0;">X</button>
            </div>`;
        });
    }

    async function delJob(id) {
        await fetch('/api/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id})
        });
        updateHistory();
    }

    const toBase64 = file => new Promise(res => {
        const r = new FileReader(); r.readAsDataURL(file); r.onload = () => res(r.result);
    });
</script>
</body>
</html>
"""

if __name__ == '__main__':
    threading.Thread(target=bot_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
