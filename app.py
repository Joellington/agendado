import os
import time
import threading
import base64
import requests
from flask import Flask, request, jsonify, render_template_string
from tinydb import TinyDB, Query
from datetime import datetime

app = Flask(__name__)
# O banco de dados fica no disco do servidor
db = TinyDB('database.json')

# --- ROBÔ DE DISPARO (24H NA NUVEM) ---
def bot_worker():
    while True:
        try:
            now = datetime.now().timestamp() * 1000
            Job = Query()
            # Busca mensagens agendadas que não foram enviadas
            pending_jobs = db.search((Job.sent == False) & (Job.time <= now))
            
            for job in pending_jobs:
                token = job['token']
                chat_id = job['chat']
                text = job['full_text']
                url = f"https://api.telegram.org/bot{token}/"
                
                # Tenta enviar com foto
                if job.get('photo'):
                    try:
                        header, encoded = job['photo'].split(",", 1)
                        photo_data = base64.b64decode(encoded)
                        files = {'photo': ('image.jpg', photo_data)}
                        resp = requests.post(url + "sendPhoto", data={'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}, files=files, timeout=15)
                    except:
                        resp = requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=15)
                else:
                    resp = requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=15)
                
                # Se enviou (Status 200) ou se o erro for do Telegram (Status 400), marca como concluído
                if resp.status_code in [200, 400]:
                    db.update({'sent': True, 'sent_at': datetime.now().strftime('%d/%m %H:%M')}, Job.id == job['id'])
        except Exception as e:
            print(f"Erro no robô: {e}")
        time.sleep(20)

# --- ROTAS DA API ---
@app.route('/')
def index(): return render_template_string(HTML_CODE)

@app.route('/api/jobs')
def get_jobs(): return jsonify(db.all())

@app.route('/api/save', methods=['POST'])
def save_job():
    db.insert(request.json)
    return jsonify({"ok": True})

@app.route('/api/delete', methods=['POST'])
def delete_job():
    db.remove(Query().id == request.json.get('id'))
    return jsonify({"ok": True})

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    C = Query()
    if request.method == 'POST':
        db.remove(C.type == 'config')
        db.insert({'type': 'config', 'token': request.json['token'], 'chat': request.json['chat']})
        return jsonify({"ok": True})
    res = db.search(C.type == 'config')
    return jsonify(res[0] if res else {"token": "", "chat": ""})

# --- INTERFACE COM HISTÓRICO E LIXEIRA ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ads Pro Cloud</title>
    <style>
        :root { --blue: #0088cc; --red: #e74c3c; --green: #2ecc71; --bg: #f0f2f5; }
        body { font-family: sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .card { max-width: 600px; margin: auto; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--blue); color: white; padding: 20px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; font-size: 14px; }
        input, textarea, select { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 10px; box-sizing: border-box; }
        button { width: 100%; padding: 15px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; margin-top: 10px; }
        .btn-blue { background: var(--blue); color: white; }
        .btn-green { background: var(--green); color: white; }
        .btn-gray { background: #6c757d; color: white; }
        
        /* Grid de Perfis */
        .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
        .profile-card { background: #f8f9fa; border: 2px solid #eee; padding: 15px; border-radius: 12px; text-align: center; cursor: pointer; font-weight: bold; }
        .profile-card:hover { border-color: var(--blue); }

        /* Estilo do Histórico */
        .history-section { margin-top: 30px; border-top: 3px solid #eee; padding-top: 20px; }
        .job-card { background: white; border: 1px solid #ddd; padding: 15px; border-radius: 15px; margin-bottom: 15px; position: relative; display: flex; align-items: center; }
        .job-card img { width: 65px; height: 65px; border-radius: 10px; object-fit: cover; margin-right: 15px; border: 1px solid #eee; }
        .job-info { font-size: 12px; flex-grow: 1; }
        .job-info strong { color: var(--blue); display: block; margin-bottom: 3px; font-size: 14px; }
        .status { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-top: 5px; }
        .status-wait { background: #fff3cd; color: #856404; }
        .status-sent { background: #d4edda; color: #155724; }
        .btn-trash { position: absolute; top: 10px; right: 10px; background: #fee; color: var(--red); border: 1px solid #fcc; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; font-size: 16px; }
    </style>
</head>
<body>
<div class="card">
    <div class="header"><h1>Ads Cloud Master</h1></div>
    <div class="p-20">
        <!-- LOGIN -->
        <div id="screen-login">
            <label>Quem vai administrar hoje?</label>
            <div id="profiles-list" class="profile-grid"></div>
            <button class="btn-green" onclick="addProfile()">+ Adicionar Novo Administrador</button>
            <button class="btn-gray" onclick="openConfig()">⚙️ Configurações do Robô</button>
        </div>

        <!-- CONFIG -->
        <div id="screen-admin" class="hidden">
            <label>Token do Bot:</label><input type="password" id="c-token">
            <label>ID do Grupo (Ex: -100...):</label><input type="text" id="c-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR CONFIGURAÇÃO</button>
            <button onclick="location.reload()">Voltar</button>
        </div>

        <!-- AGENDADOR -->
        <div id="screen-user" class="hidden">
            <h3 id="u-tag"></h3>
            <textarea id="u-msg" rows="3" placeholder="Sua mensagem de impacto..."></textarea>
            
            <label>Texto que vira Link:</label>
            <input type="text" id="u-ltxt" placeholder="Ex: 👉 CLIQUE AQUI E GANHE BÔNUS!">
            
            <label>URL do Link de Afiliado:</label>
            <input type="url" id="u-lurl" placeholder="https://...">

            <label>Foto da Galeria:</label>
            <input type="file" id="u-img" accept="image/*">

            <div style="display:flex; gap:10px;">
                <div style="flex:2"><label>Início:</label><input type="datetime-local" id="u-date"></div>
                <div style="flex:1"><label>Qtd. Envios:</label><input type="number" id="u-qty" value="1"></div>
            </div>
            <label>Intervalo (De quantas em quantas horas?):</label>
            <input type="number" id="u-interval" value="24" placeholder="Ex: 1 para cada hora">

            <button class="btn-blue" onclick="schedule()">PROGRAMAR AGORA</button>

            <!-- SEÇÃO DO HISTÓRICO -->
            <div class="history-section">
                <h3>📋 Histórico de Disparos</h3>
                <div id="history-display"></div>
            </div>
            
            <button class="btn-gray" onclick="location.reload()" style="margin-top:20px;">Sair do Perfil</button>
        </div>
    </div>
</div>

<script>
    let botCfg = {token:'', chat:''};
    let currentUser = "";
    let profiles = JSON.parse(localStorage.getItem('profiles_v4')) || ["Admin Principal", "Marketing"];

    function loadProfiles() {
        const div = document.getElementById('profiles-list'); div.innerHTML = "";
        profiles.forEach(p => div.innerHTML += `<div class="profile-card" onclick="openUser('${p}')">${p}</div>`);
    }

    function addProfile() {
        const n = prompt("Nome do novo Administrador:");
        if(n) { profiles.push(n); localStorage.setItem('profiles_v4', JSON.stringify(profiles)); loadProfiles(); }
    }

    async function openConfig() {
        if(prompt("Digite a senha do sistema:") === "123456") {
            document.getElementById('screen-login').classList.add('hidden');
            document.getElementById('screen-admin').classList.remove('hidden');
            const r = await fetch('/api/config').then(res=>res.json());
            document.getElementById('c-token').value = r.token;
            document.getElementById('c-chat').value = r.chat;
        }
    }

    async function saveAdmin() {
        const token = document.getElementById('c-token').value;
        const chat = document.getElementById('c-chat').value;
        await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token, chat})});
        alert("Configuração Salva!"); location.reload();
    }

    async function openUser(name) {
        botCfg = await fetch('/api/config').then(r=>r.json());
        if(!botCfg.token) return alert("O Admin precisa configurar o Token e o Chat ID primeiro!");
        
        currentUser = name;
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('u-tag').innerText = "Acesso: " + name;
        updateHistory();
    }

    async function schedule() {
        const file = document.getElementById('u-img').files[0];
        const img = file ? await toB64(file) : null;
        const start = new Date(document.getElementById('u-date').value).getTime();
        const qty = parseInt(document.getElementById('u-qty').value);
        const interval = parseInt(document.getElementById('u-interval').value) * 60 * 60 * 1000;
        
        const phrase = document.getElementById('u-msg').value;
        const linkTxt = document.getElementById('u-ltxt').value;
        const linkUrl = document.getElementById('u-lurl').value;

        if(!start || !linkUrl) return alert("Preencha data e link!");

        for(let i=0; i<qty; i++) {
            const data = {
                id: Date.now() + i,
                user: currentUser,
                token: botCfg.token, chat: botCfg.chat,
                full_text: phrase + `\\n\\n<a href="${linkUrl}">${linkTxt}</a>`,
                phrase: phrase,
                link: linkUrl,
                time: start + (i * interval),
                photo: img, sent: false
            };
            await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
        }
        alert(qty + " envios agendados!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch('/api/jobs').then(r=>r.json());
        const div = document.getElementById('history-display'); div.innerHTML = "";
        
        jobs.sort((a,b)=>b.time - a.time).forEach(j => {
            const status = j.sent ? `<span class="status status-sent">ENVIADO (${j.sent_at})</span>` : `<span class="status status-wait">AGUARDANDO</span>`;
            const img = j.photo ? `<img src="${j.photo}">` : `<div style="width:65px;height:65px;background:#eee;float:left;margin-right:15px;border-radius:10px;"></div>`;
            
            div.innerHTML += `
                <div class="job-card">
                    <button class="btn-trash" onclick="delJob(${j.id})">🗑️</button>
                    ${img}
                    <div class="job-info">
                        <strong>👤 Enviado por: ${j.user}</strong>
                        <span>📅 Data: ${new Date(j.time).toLocaleString()}</span><br>
                        <span>💬 Mensagem: ${j.phrase.substring(0,40)}...</span><br>
                        <a href="${j.link}" target="_blank" style="color:var(--blue); font-weight:bold; text-decoration:none;">🔗 Ver Link</a><br>
                        ${status}
                    </div>
                    <div style="clear:both;"></div>
                </div>
            `;
        });
    }

    async function delJob(id) {
        if(confirm("Deseja apagar do histórico e CANCELAR este envio?")) {
            await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
            updateHistory();
        }
    }

    const toB64 = f => new Promise(r => { const rd = new FileReader(); rd.readAsDataURL(f); rd.onload = () => r(rd.result); });
    loadProfiles();
</script>
</body>
</html>
"""

if __name__ == '__main__':
    threading.Thread(target=bot_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
