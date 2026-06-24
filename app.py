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
    print("🤖 Robô de disparos iniciado...")
    while True:
        try:
            # Pega o timestamp atual
            now = datetime.now().timestamp() * 1000
            Job = Query()
            
            # Busca jobs que NÃO foram enviados e que já estão no horário (ou atrasados)
            # Simplifiquei a busca para evitar erros com campos inexistentes
            all_data = db.all()
            pending_jobs = [j for j in all_data if j.get('sent') == False and j.get('time', 9999999999999) <= now]

            for job in pending_jobs:
                print(f"🚀 Tentando enviar mensagem agendada para agora...")
                success = send_telegram(job)
                if success:
                    db.update({'sent': True}, Job.id == job['id'])
                    print(f"✅ Mensagem enviada com sucesso!")
                else:
                    # Se falhou, marca como enviado para não travar o robô, 
                    # ou você pode implementar uma lógica de tentativa depois.
                    db.update({'sent': True}, Job.id == job['id'])
                    print(f"❌ Falha crítica no envio. Verifique o Token/ID.")
        except Exception as e:
            print(f"⚠️ Erro no loop do robô: {e}")
        
        time.sleep(5) # Checa a cada 5 segundos

def send_telegram(job):
    token = job.get('token')
    chat_id = job.get('chat')
    text = job.get('text', '')
    url = f"https://api.telegram.org/bot{token}/"
    
    try:
        # Se houver foto
        if job.get('photo'):
            header, encoded = job['photo'].split(",", 1)
            data = base64.b64decode(encoded)
            files = {'photo': ('image.jpg', data)}
            payload = {'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}
            r = requests.post(url + "sendPhoto", data=payload, files=files)
        else:
            payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            r = requests.post(url + "sendMessage", data=payload)
        
        if r.status_code != 200:
            print(f"🔴 Erro do Telegram: {r.text}")
            return False
        return True
    except Exception as e:
        print(f"🔴 Erro de conexão: {e}")
        return False

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
    # Retorna apenas agendamentos do usuário logado que ainda não foram enviados
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

# --- INTERFACE HTML ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Marketing Pro</title>
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
        .job-card { border-left: 4px solid var(--primary); padding: 10px; background: #fff; margin-top: 10px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    </style>
</head>
<body>
<div class="card">
    <div class="header"><h2>Marketing Automático</h2></div>
    <div class="p-20">
        
        <!-- LOGIN -->
        <div id="screen-login">
            <h3 style="text-align:center">Escolha seu Perfil</h3>
            <div id="profile-container"></div>
            <hr>
            <input type="text" id="new-profile-name" placeholder="Nome do novo perfil">
            <button class="btn-blue" onclick="addProfile()">+ Novo Perfil</button>
            <button class="btn-admin" onclick="openAdmin()">🛡️ Configurações Master</button>
        </div>

        <!-- ADMIN -->
        <div id="screen-admin" class="hidden">
            <h3>Configurar Bot Principal</h3>
            <label>Token:</label><input type="password" id="cfg-token">
            <label>ID do Canal:</label><input type="text" id="cfg-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR</button>
            <button class="btn-admin" onclick="location.reload()">VOLTAR</button>
        </div>

        <!-- DASHBOARD -->
        <div id="screen-user" class="hidden">
            <div style="display:flex; justify-content: space-between; align-items: center;">
                <strong id="user-display"></strong>
                <button onclick="location.reload()" style="width:auto; padding:5px;">Sair</button>
            </div>
            <hr>
            
            <textarea id="msg-text" rows="3" placeholder="Mensagem principal..."></textarea>
            <input type="text" id="link-text" placeholder="Texto do Link (opcional)">
            <input type="url" id="link-url" placeholder="https://link-do-seu-afiliado.com (opcional)">
            
            <label>Foto:</label>
            <input type="file" id="msg-photo" accept="image/*">
            
            <div style="display:flex; gap:10px;">
                <div style="flex:1"><label>Início:</label><input type="datetime-local" id="msg-date"></div>
                <div style="flex:1"><label>Total de Envios:</label><input type="number" id="msg-total-count" value="1"></div>
            </div>
            
            <label>Intervalo:</label>
            <select id="msg-freq">
                <option value="30s">A cada 30 segundos</option>
                <option value="1m">A cada 1 minuto</option>
                <option value="5m">A cada 5 minutos</option>
                <option value="1">1 vez ao dia</option>
                <option value="24">24 vezes ao dia (1h em 1h)</option>
            </select>
            
            <button class="btn-blue" onclick="schedule()">PROGRAMAR DISPAROS</button>
            
            <h4 style="margin-top:20px;">Minha Fila de Envios:</h4>
            <div id="history"></div>
        </div>

    </div>
</div>

<script>
    let currentUser = "";
    let config = {};

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
        if(prompt("Senha:") === "123456") {
            document.getElementById('screen-login').classList.add('hidden');
            document.getElementById('screen-admin').classList.remove('hidden');
            const res = await fetch('/api/config').then(r => r.json());
            document.getElementById('cfg-token').value = res.token;
            document.getElementById('cfg-chat').value = res.chat;
        }
    }

    async function saveAdmin() {
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token: document.getElementById('cfg-token').value, chat: document.getElementById('cfg-chat').value})
        });
        location.reload();
    }

    async function openUser(name) {
        config = await fetch('/api/config').then(r => r.json());
        if(!config.token) return alert("Configure o Bot no Admin!");
        currentUser = name;
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('user-display').innerText = "Perfil: " + name;
        updateHistory();
    }

    async function schedule() {
        const file = document.getElementById('msg-photo').files[0];
        const photo = file ? await toBase64(file) : null;
        const startInput = document.getElementById('msg-date').value;
        if(!startInput) return alert("Escolha a data de início!");

        const start = new Date(startInput).getTime();
        const total = parseInt(document.getElementById('msg-total-count').value);
        const freq = document.getElementById('msg-freq').value;
        
        let interval = 0;
        if(freq === "30s") interval = 30 * 1000;
        else if(freq === "1m") interval = 60 * 1000;
        else if(freq === "5m") interval = 5 * 60 * 1000;
        else interval = (24 / parseInt(freq)) * 60 * 60 * 1000;

        const baseText = document.getElementById('msg-text').value;
        const lText = document.getElementById('link-text').value;
        const lUrl = document.getElementById('link-url').value;
        
        // Só monta o link se ambos os campos estiverem preenchidos
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
        alert("Envios Agendados!"); 
        updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch(`/api/jobs?user=${currentUser}`).then(r => r.json());
        const div = document.getElementById('history');
        div.innerHTML = "";
        jobs.sort((a,b) => a.time - b.time).forEach(j => {
            div.innerHTML += `<div class="job-card">
                <span>📅 ${new Date(j.time).toLocaleString()}</span>
                <button onclick="delJob(${j.id})" style="background:red; color:white; border:none; padding:5px; border-radius:5px;">🗑️</button>
            </div>`;
        });
    }

    async function delJob(id) {
        await fetch('/api/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id}) });
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
