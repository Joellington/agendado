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

# --- ROBÔ DE DISPARO ---
def bot_worker():
    while True:
        try:
            now = datetime.now().timestamp() * 1000
            Job = Query()
            # Busca apenas jobs que não foram enviados e que já passaram da hora
            pending_jobs = db.search((Job.type == 'job') & (Job.sent == False) & (Job.time <= now))
            
            for job in pending_jobs:
                send_telegram(job)
                db.update({'sent': True}, Job.id == job['id'])
        except Exception as e:
            print(f"Erro no Bot: {e}")
        time.sleep(20)

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
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

# --- API ---
@app.route('/')
def index():
    return render_template_string(HTML_CODE)

@app.route('/api/profiles', methods=['GET', 'POST'])
def manage_profiles():
    P = Query()
    if request.method == 'POST':
        name = request.json.get('name')
        if not db.search((P.type == 'profile') & (P.name == name)):
            db.insert({'type': 'profile', 'name': name})
        return jsonify({"ok": True})
    return jsonify(db.search(P.type == 'profile'))

@app.route('/api/jobs')
def get_jobs():
    user = request.args.get('user')
    Job = Query()
    # Retorna apenas jobs do usuário logado e que não foram enviados
    res = db.search((Job.type == 'job') & (Job.user == user) & (Job.sent == False))
    return jsonify(res)

@app.route('/api/save', methods=['POST'])
def save_job():
    data = request.json
    data['type'] = 'job'
    db.insert(data)
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

# --- HTML/JS/CSS ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Multi-Profile Bot</title>
    <style>
        :root { --primary: #0088cc; --bg: #f0f2f5; --danger: #ff4d4d; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .card { max-width: 500px; margin: auto; background: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--primary); color: white; padding: 20px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        input, textarea, select { width: 100%; padding: 12px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 5px; transition: 0.3s; }
        .btn-blue { background: var(--primary); color: white; }
        .btn-outline { background: white; border: 2px solid var(--primary); color: var(--primary); margin-bottom: 10px; }
        .btn-admin { background: #6c757d; color: white; }
        .btn-delete { background: var(--danger); color: white; width: 40px; padding: 5px; margin: 0; }
        .profile-list { margin-bottom: 20px; }
        .job-card { border-left: 4px solid var(--primary); padding: 10px; background: #fff; margin-top: 10px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); border-radius: 4px; }
        .phrase-box { background: #f8f9fa; border: 1px solid #eee; padding: 10px; max-height: 100px; overflow-y: auto; margin-bottom: 15px; border-radius: 8px; }
        .phrase-item { font-size: 12px; padding: 6px; border-bottom: 1px solid #eee; cursor: pointer; }
    </style>
</head>
<body>
<div class="card">
    <div class="header"><h2>Telegram Marketing VIP</h2></div>
    <div class="p-20">
        
        <!-- TELA DE SELEÇÃO DE PERFIL -->
        <div id="screen-login">
            <h3 style="text-align:center">Escolha seu Perfil</h3>
            <div id="profile-container" class="profile-list"></div>
            <hr>
            <input type="text" id="new-profile-name" placeholder="Nome do novo perfil">
            <button class="btn-blue" onclick="addProfile()">+ Criar Novo Perfil</button>
            <button class="btn-admin" style="margin-top:20px;" onclick="openAdmin()">🛡️ Configurações Master</button>
        </div>

        <!-- ADMIN -->
        <div id="screen-admin" class="hidden">
            <h3>Configurações Globais</h3>
            <label>Token do Bot:</label><input type="password" id="cfg-token">
            <label>ID do Canal/Grupo:</label><input type="text" id="cfg-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR CONFIGURAÇÃO</button>
            <button onclick="location.reload()">Voltar</button>
        </div>

        <!-- DASHBOARD DO USUÁRIO -->
        <div id="screen-user" class="hidden">
            <div style="display:flex; justify-content: space-between; align-items: center;">
                <strong id="user-display"></strong>
                <button onclick="location.reload()" style="width:auto; padding:5px 10px; font-size:11px;">Sair</button>
            </div>
            
            <hr>
            <label>Frases Prontas:</label>
            <div class="phrase-box" id="phrases-list"></div>
            
            <textarea id="msg-text" rows="3" placeholder="Sua mensagem principal..."></textarea>
            <input type="text" id="link-text" placeholder="Texto do Botão (Ex: 👉 CLIQUE AQUI)">
            <input type="url" id="link-url" placeholder="https://seu-link.com">
            
            <label>Foto (opcional):</label>
            <input type="file" id="msg-photo" accept="image/*">
            
            <div style="display:flex; gap:10px;">
                <div style="flex:2"><label>Início:</label><input type="datetime-local" id="msg-date"></div>
                <div style="flex:1"><label>Dias:</label><input type="number" id="msg-days" value="1"></div>
            </div>
            
            <label>Frequência Diária:</label>
            <select id="msg-freq">
                <option value="1">1 vez ao dia</option>
                <option value="3">3 vezes ao dia</option>
                <option value="6">6 vezes ao dia</option>
                <option value="12">12 vezes ao dia</option>
            </select>
            
            <button class="btn-blue" onclick="schedule()">PROGRAMAR DISPAROS</button>
            
            <div style="margin-top:25px;">
                <strong>🗓️ Meus Agendamentos (Fila):</strong>
                <div id="history"></div>
            </div>
        </div>
    </div>
</div>

<script>
    let currentUser = "";
    let config = {};
    const frasesMarketing = [
        "🚀 Oportunidade única para lucrar hoje!",
        "💰 BÔNUS DE 100% LIBERADO! Veja como pegar.",
        "🚨 ÚLTIMAS VAGAS no nosso grupo VIP!",
        "💎 Estratégia revelada! Clique no botão abaixo.",
        "🔥 O mercado está pagando muito, aproveite!",
        "⚠️ Link expira em 10 minutos. Corra!"
    ];

    window.onload = loadProfiles;

    async function loadProfiles() {
        const res = await fetch('/api/profiles').then(r => r.json());
        const container = document.getElementById('profile-container');
        container.innerHTML = "";
        res.forEach(p => {
            let btn = document.createElement('button');
            btn.className = 'btn-outline';
            btn.innerText = "👤 " + p.name;
            btn.onclick = () => openUser(p.name);
            container.appendChild(btn);
        });
    }

    async function addProfile() {
        const name = document.getElementById('new-profile-name').value;
        if(!name) return;
        await fetch('/api/profiles', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        document.getElementById('new-profile-name').value = "";
        loadProfiles();
    }

    async function openAdmin() {
        if(prompt("Senha Master:") === "123456") {
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
        if(!config.token) return alert("Erro: O Admin não configurou o BOT!");
        
        currentUser = name;
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('user-display').innerText = "Perfil: " + name;
        
        // Carregar frases
        const list = document.getElementById('phrases-list');
        list.innerHTML = "";
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
        const startInput = document.getElementById('msg-date').value;
        if(!startInput) return alert("Selecione a data e hora!");
        
        const start = new Date(startInput).getTime();
        const days = parseInt(document.getElementById('msg-days').value);
        const freq = parseInt(document.getElementById('msg-freq').value);
        const interval = (24/freq)*60*60*1000;

        for(let i=0; i<(days*freq); i++) {
            const data = {
                id: Date.now() + i,
                user: currentUser,
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
        alert("Agendamentos criados com sucesso!"); 
        updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch(`/api/jobs?user=${currentUser}`).then(r => r.json());
        const div = document.getElementById('history');
        div.innerHTML = "";
        
        // Ordenar por tempo
        jobs.sort((a,b) => a.time - b.time).forEach(j => {
            const dataFormatada = new Date(j.time).toLocaleString('pt-BR');
            div.innerHTML += `
                <div class="job-card">
                    <div>
                        <strong>📅 ${dataFormatada}</strong><br>
                        <span style="color:#666">${j.text.substring(0, 30)}...</span>
                    </div>
                    <button class="btn-delete" onclick="delJob(${j.id})">🗑️</button>
                </div>`;
        });
        if(jobs.length === 0) div.innerHTML = "<p style='font-size:12px; color:#999'>Nenhum envio pendente.</p>";
    }

    async function delJob(id) {
        if(!confirm("Deseja cancelar este envio?")) return;
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
    # Inicia o robô em uma thread separada
    threading.Thread(target=bot_worker, daemon=True).start()
    # Inicia o servidor Flask
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
