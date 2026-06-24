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

# --- ROBÔ DE DISPARO (Nuvem 24h) ---
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
            print(f"Erro no disparo: {e}")
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

# --- ROTAS API ---
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

# --- HTML INTERFACE ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Marketing Pro</title>
    <style>
        :root { --blue: #0088cc; --red: #e74c3c; --bg: #f4f7f6; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .card { max-width: 550px; margin: auto; background: white; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--blue); color: white; padding: 20px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        
        label { display: block; margin: 10px 0 5px; font-weight: bold; font-size: 14px; }
        input, textarea, select { width: 100%; padding: 12px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 10px; box-sizing: border-box; }
        
        button { width: 100%; padding: 14px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; margin-bottom: 10px; transition: 0.2s; }
        .btn-blue { background: var(--blue); color: white; }
        .btn-gray { background: #6c757d; color: white; }
        .btn-add { background: #2ecc71; color: white; margin-top: 5px; font-size: 12px; padding: 8px; }
        
        /* Perfis */
        .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .profile-item { background: #fff; border: 2px solid #eee; padding: 15px; border-radius: 10px; text-align: center; cursor: pointer; font-weight: bold; }
        .profile-item:hover { border-color: var(--blue); }

        /* Histórico Detalhado */
        .job-card { background: #fff; border: 1px solid #eee; padding: 15px; border-radius: 12px; margin-bottom: 15px; position: relative; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .job-card img { width: 60px; height: 60px; object-fit: cover; border-radius: 8px; margin-right: 15px; float: left; border: 1px solid #ddd; }
        .job-details { font-size: 13px; color: #555; }
        .job-details strong { color: var(--blue); }
        .btn-del { position: absolute; top: 10px; right: 10px; background: #fee; color: var(--red); width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 1px solid #fcc; }
        .btn-del:hover { background: var(--red); color: white; }
        .job-link { color: #00a8ff; text-decoration: none; font-weight: bold; display: block; margin-top: 5px; }

        .phrase-box { background: #f9f9f9; padding: 10px; border-radius: 10px; max-height: 120px; overflow-y: auto; margin-bottom: 15px; border: 1px solid #eee; }
        .phrase-btn { font-size: 12px; padding: 6px; border-bottom: 1px solid #eee; cursor: pointer; color: #444; }
        .phrase-btn:hover { color: var(--blue); }
    </style>
</head>
<body>

<div class="card">
    <div class="header"><h2>Telegram Marketing VIP</h2></div>
    
    <div class="p-20">
        <!-- TELA 1: LOGIN -->
        <div id="screen-login">
            <label>Acessar como:</label>
            <div id="profiles-list" class="profile-grid">
                <!-- Perfis aparecem aqui -->
            </div>
            <hr style="margin:20px 0;">
            <button class="btn-add" onclick="addNewProfile()">+ Criar Novo Acesso</button>
            <button class="btn-gray" onclick="openAdmin()">⚙️ Configurações Admin</button>
        </div>

        <!-- TELA 2: ADMIN -->
        <div id="screen-admin" class="hidden">
            <h3>⚙️ Configuração Fixa</h3>
            <label>Bot Token:</label><input type="password" id="cfg-token">
            <label>ID do Canal:</label><input type="text" id="cfg-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR AGORA</button>
            <button class="btn-gray" onclick="location.reload()">Sair</button>
        </div>

        <!-- TELA 3: AGENDADOR -->
        <div id="screen-user" class="hidden">
            <p id="user-tag" style="font-weight:bold; color:var(--blue)"></p>
            
            <label>Gatilhos Prontos:</label>
            <div class="phrase-box" id="phrase-options"></div>

            <label>Sua Mensagem:</label>
            <textarea id="msg-text" rows="3" placeholder="Escreva aqui..."></textarea>
            
            <label>Frase do Link:</label>
            <input type="text" id="link-label" placeholder="Ex: 👉 CLIQUE AQUI E GANHE BÔNUS!">
            <label>Link de Afiliado:</label>
            <input type="url" id="link-target" placeholder="https://...">

            <label>Foto da Galeria:</label>
            <input type="file" id="msg-photo" accept="image/*">

            <div style="display:flex; gap:10px;">
                <div style="flex:2"><label>Início:</label><input type="datetime-local" id="msg-date"></div>
                <div style="flex:1"><label>Dias:</label><input type="number" id="msg-days" value="1"></div>
            </div>

            <label>Repetições por dia:</label>
            <select id="msg-freq">
                <option value="1">1x ao dia</option>
                <option value="3">3x ao dia (8h em 8h)</option>
                <option value="6">6x ao dia (4h em 4h)</option>
                <option value="12">12x ao dia (2h em 2h)</option>
            </select>

            <button class="btn-blue" onclick="schedule()">AGENDAR NA NUVEM</button>

            <div style="margin-top:30px;">
                <h4>📦 Fila de Disparos Ativos</h4>
                <div id="history-content"></div>
            </div>
            
            <button class="btn-gray" style="margin-top:20px;" onclick="location.reload()">Sair do Perfil</button>
        </div>
    </div>
</div>

<script>
    let botConfig = {token: '', chat: ''};
    let currentUser = "";
    const frases = [
        "🚀 Venha conferir essa oportunidade única!",
        "💰 BÔNUS DE 100% PARA NOVOS USUÁRIOS!",
        "🚨 ÚLTIMAS VAGAS! Não perca o que preparamos.",
        "💎 Estratégia VIP liberada. Veja agora!",
        "🔥 O mercado está pagando muito hoje!",
        "🎯 Apostas grátis liberadas via link exclusivo."
    ];

    // Carregar Perfis do LocalStorage (Sempre guarda quem você criou)
    let profiles = JSON.parse(localStorage.getItem('tg_profiles')) || ["Marketing", "Vendas"];

    function loadLoginScreen() {
        const div = document.getElementById('profiles-list');
        div.innerHTML = "";
        profiles.forEach(p => {
            div.innerHTML += `<div class="profile-item" onclick="openUser('${p}')">${p}</div>`;
        });
    }

    function addNewProfile() {
        const name = prompt("Nome da nova pessoa/equipe:");
        if(name) {
            profiles.push(name);
            localStorage.setItem('tg_profiles', JSON.stringify(profiles));
            loadLoginScreen();
        }
    }

    async function openAdmin() {
        if(prompt("Senha:") === "123456") {
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
        alert("Salvo!"); location.reload();
    }

    async function openUser(name) {
        botConfig = await fetch('/api/config').then(r => r.json());
        if(!botConfig.token) return alert("Admin não configurou o sistema!");
        
        currentUser = name;
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('user-tag').innerText = "Perfil: " + name;

        const pDiv = document.getElementById('phrase-options');
        pDiv.innerHTML = "";
        frases.forEach(f => {
            let d = document.createElement('div'); d.className = 'phrase-btn'; d.innerText = f;
            d.onclick = () => document.getElementById('msg-text').value = f;
            pDiv.appendChild(d);
        });
        updateHistory();
    }

    async function schedule() {
        const file = document.getElementById('msg-photo').files[0];
        const photoBase64 = file ? await toBase64(file) : null;
        const start = new Date(document.getElementById('msg-date').value).getTime();
        const days = parseInt(document.getElementById('msg-days').value);
        const freq = parseInt(document.getElementById('msg-freq').value);
        const interval = (24/freq)*60*60*1000;
        
        const phrase = document.getElementById('msg-text').value;
        const linkTxt = document.getElementById('link-label').value;
        const linkUrl = document.getElementById('link-target').value;

        for(let i=0; i<(days*freq); i++) {
            const data = {
                id: Date.now() + i,
                user: currentUser,
                token: botConfig.token,
                chat: botConfig.chat,
                text: phrase + `\\n\\n<a href="${linkUrl}">${linkTxt}</a>`,
                phrase: phrase, // Guardamos separado para o histórico
                link: linkUrl,
                time: start + (i * interval),
                photo: photoBase64,
                sent: false
            };
            await fetch('/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
        }
        alert("Tudo agendado na Nuvem!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch('/api/jobs').then(r => r.json());
        const div = document.getElementById('history-content');
        div.innerHTML = "";
        
        // Filtra apenas agendamentos do futuro para este canal
        jobs.filter(j => !j.sent).sort((a,b) => a.time - b.time).forEach(j => {
            const date = new Date(j.time).toLocaleString();
            const imgHtml = j.photo ? `<img src="${j.photo}">` : `<div style="width:60px;height:60px;background:#eee;float:left;margin-right:15px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:10px;">Sem foto</div>`;
            
            div.innerHTML += `
                <div class="job-card">
                    <button class="btn-del" onclick="delJob(${j.id})">🗑️</button>
                    ${imgHtml}
                    <div class="job-details">
                        <strong>📅 ${date}</strong>
                        <span>Frase: ${j.phrase || "Personalizada"}</span>
                        <a href="${j.link}" class="job-link" target="_blank">🔗 Ver Link Enviado</a>
                    </div>
                    <div style="clear:both;"></div>
                </div>
            `;
        });
    }

    async function delJob(id) {
        if(confirm("Deseja cancelar este envio?")) {
            await fetch('/api/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id})
            });
            updateHistory();
        }
    }

    const toBase64 = file => new Promise(res => {
        const r = new FileReader(); r.readAsDataURL(file); r.onload = () => res(r.result);
    });

    loadLoginScreen();
</script>
</body>
</html>
    
