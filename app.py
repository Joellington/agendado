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

# --- ROBÔ DE DISPARO (O MAIS SIMPLES POSSÍVEL PARA NÃO FALHAR) ---
def bot_worker():
    print("🤖 Robô Iniciado...")
    while True:
        try:
            now = datetime.now().timestamp() * 1000
            Job = Query()
            # O robô varre o banco e pega TUDO que não foi enviado e já passou da hora
            for job in db.all():
                if job.get('sent') == False and job.get('time', 0) <= now:
                    print(f"🚀 Tentando enviar job: {job.get('id')}")
                    
                    # Tenta enviar
                    success = send_telegram(job)
                    
                    if success:
                        db.update({'sent': True}, Job.id == job['id'])
                        print("✅ Sucesso!")
                    else:
                        # Se der erro (token ou id errado), marcamos como enviado para não travar a fila
                        db.update({'sent': True}, Job.id == job['id'])
                        print("❌ Falha no envio (verifique Token/ID no Admin)")
        except Exception as e:
            print(f"⚠️ Erro no Robô: {e}")
        time.sleep(5)

def send_telegram(job):
    token = job.get('token')
    chat_id = job.get('chat')
    text = job.get('text', '')
    url = f"https://api.telegram.org/bot{token}/"
    
    try:
        if job.get('photo'):
            # Envio com Foto
            header, encoded = job['photo'].split(",", 1)
            data = base64.b64decode(encoded)
            files = {'photo': ('image.jpg', data)}
            payload = {'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}
            r = requests.post(url + "sendPhoto", data=payload, files=files, timeout=15)
        else:
            # Envio só Texto
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            r = requests.post(url + "sendMessage", data=payload, timeout=15)
        
        return r.status_code == 200
    except:
        return False

# --- ROTAS DA API ---
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
    return jsonify(db.search(Query().type == 'profile'))

@app.route('/api/jobs')
def get_jobs():
    user = request.args.get('user')
    # Retorna apenas o que pertence ao perfil e não foi enviado
    res = [j for j in db.all() if j.get('user') == user and j.get('sent') == False]
    return jsonify(res)

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

# --- HTML COMPLETO ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Marketing VIP</title>
    <style>
        :root { --primary: #0088cc; --bg: #f0f2f5; }
        body { font-family: 'Segoe UI', sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .card { max-width: 500px; margin: auto; background: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--primary); color: white; padding: 20px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        input, textarea, select { width: 100%; padding: 12px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
        .btn-blue { background: var(--primary); color: white; }
        .btn-outline { background: white; border: 2px solid var(--primary); color: var(--primary); margin-bottom: 10px; }
        .btn-admin { background: #6c757d; color: white; margin-top: 10px; }
        .phrase-box { background: #f8f9fa; border: 1px solid #eee; padding: 10px; max-height: 100px; overflow-y: auto; margin-bottom: 10px; border-radius: 8px; }
        .phrase-item { font-size: 13px; padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }
        .job-card { border-left: 4px solid var(--primary); padding: 10px; background: #fff; margin-top: 10px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
<div class="card">
    <div class="header"><h2>Telegram Marketing</h2></div>
    <div class="p-20">
        
        <!-- TELA 1: LOGIN/PERFIS -->
        <div id="screen-login">
            <h3 style="text-align:center">Selecione seu Perfil</h3>
            <div id="profile-container"></div>
            <hr>
            <input type="text" id="new-profile-name" placeholder="Nome do novo perfil...">
            <button class="btn-blue" onclick="addProfile()">+ Criar Novo Perfil</button>
            <button class="btn-admin" onclick="openAdmin()">🛡️ Configurações Master</button>
        </div>

        <!-- TELA 2: ADMIN -->
        <div id="screen-admin" class="hidden">
            <h3>Configurações Globais</h3>
            <label>Token do Bot:</label><input type="password" id="cfg-token">
            <label>ID do Canal (ex: -100...):</label><input type="text" id="cfg-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR CONFIGURAÇÃO</button>
            <button class="btn-admin" onclick="location.reload()">VOLTAR</button>
        </div>

        <!-- TELA 3: DASHBOARD USUÁRIO -->
        <div id="screen-user" class="hidden">
            <div style="display:flex; justify-content: space-between; align-items: center;">
                <strong id="user-display"></strong>
                <button onclick="location.reload()" style="width:auto; padding:5px 10px;">Sair</button>
            </div>
            <hr>
            
            <label>Frases Prontas (Clique para usar):</label>
            <div class="phrase-box" id="phrases-list"></div>
            
            <textarea id="msg-text" rows="3" placeholder="Sua mensagem principal..."></textarea>
            
            <input type="text" id="link-text" placeholder="Texto que vira link (Ex: CLIQUE AQUI)">
            <input type="url" id="link-url" placeholder="https://seu-link-afiliado.com">
            
            <label>Foto da Galeria:</label>
            <input type="file" id="msg-photo" accept="image/*">
            
            <div style="display:flex; gap:10px;">
                <div style="flex:1"><label>Início:</label><input type="datetime-local" id="msg-date"></div>
                <div style="flex:1"><label>Qtd de Envios:</label><input type="number" id="msg-total" value="1"></div>
            </div>
            
            <label>Intervalo Personalizado:</label>
            <div style="display:flex; gap:5px;">
                <input type="number" id="freq-val" value="30" style="flex:1">
                <select id="freq-unit" style="flex:1">
                    <option value="s">Segundos</option>
                    <option value="m">Minutos</option>
                    <option value="h">Horas</option>
                </select>
            </div>
            
            <button class="btn-blue" onclick="schedule()">PROGRAMAR DISPAROS</button>
            
            <h4 style="margin-top:20px;">Fila de Envios (Pendente):</h4>
            <div id="history"></div>
        </div>

    </div>
</div>

<script>
    let currentUser = "";
    let config = {};
    const frasesProntas = [
        "🚀 Venha conferir essa oportunidade única!",
        "💰 BÔNUS DE 100% PARA NOVOS USUÁRIOS!",
        "🚨 ÚLTIMAS VAGAS! Não perca.",
        "💎 Estratégia VIP liberada. Veja!",
        "🔥 O mercado está pagando muito hoje!",
        "🎯 Aproveite a promoção agora!"
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
        location.reload();
    }

    async function openAdmin() {
        if(prompt("Senha Master:") === "123456") {
            document.getElementById('screen-login').classList.add('hidden');
            document.getElementById('screen-admin').classList.remove('hidden');
            const res = await fetch('/api/config').then(r => r.json());
            document.getElementById('cfg-token').value = res.token || '';
            document.getElementById('cfg-chat').value = res.chat || '';
        }
    }

    async function saveAdmin() {
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                token: document.getElementById('cfg-token').value, 
                chat: document.getElementById('cfg-chat').value
            })
        });
        alert("Salvo!"); location.reload();
    }

    async function openUser(name) {
        config = await fetch('/api/config').then(r => r.json());
        if(!config.token) return alert("Erro: O Admin não configurou o BOT!");
        
        currentUser = name;
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('user-display').innerText = "Perfil: " + name;
        
        const list = document.getElementById('phrases-list');
        list.innerHTML = "";
        frasesProntas.forEach(f => {
            let d = document.createElement('div'); d.className = 'phrase-item'; d.innerText = f;
            d.onclick = () => document.getElementById('msg-text').value = f;
            list.appendChild(d);
        });
        updateHistory();
    }

    async function schedule() {
        const startInput = document.getElementById('msg-date').value;
        if(!startInput) return alert("Selecione data/hora!");

        const file = document.getElementById('msg-photo').files[0];
        const photo = file ? await toBase64(file) : null;
        const start = new Date(startInput).getTime();
        const total = parseInt(document.getElementById('msg-total').value);
        const freqVal = parseFloat(document.getElementById('freq-val').value);
        const freqUnit = document.getElementById('freq-unit').value;
        
        let interval = freqVal * 1000;
        if(freqUnit === 'm') interval *= 60;
        if(freqUnit === 'h') interval *= 3600;

        const baseText = document.getElementById('msg-text').value;
        const lText = document.getElementById('link-text').value;
        const lUrl = document.getElementById('link-url').value;
        
        // Monta o texto com link HTML apenas se preenchido corretamente
        let finalText = baseText;
        if(lText && lUrl) {
            finalText += `\\n\\n<a href="${lUrl}">${lText}</a>`;
        }

        for(let i=0; i<total; i++) {
            const data = {
                id: Date.now() + i,
                user: currentUser,
                token: config.token,
                chat: config.chat,
                text: finalText,
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
        alert("Agendado!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch(`/api/jobs?user=${currentUser}`).then(r => r.json());
        const div = document.getElementById('history');
        div.innerHTML = "";
        jobs.sort((a,b) => a.time - b.time).forEach(j => {
            div.innerHTML += `<div class="job-card">
                <span>📅 ${new Date(j.time).toLocaleString()}</span>
                <button onclick="delJob(${j.id})" style="background:red; color:white; border:none; padding:5px 10px; border-radius:5px;">🗑️</button>
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
