import os, time, threading, base64, requests
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
            pending_jobs = db.search((Job.sent == False) & (Job.time <= now))
            
            for job in pending_jobs:
                token = job['token']
                chat_id = job['chat']
                text = job['full_text']
                url = f"https://api.telegram.org/bot{token}/"
                
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
                
                if resp.status_code == 200:
                    db.update({'sent': True, 'sent_at': datetime.now().strftime('%d/%m %H:%M')}, Job.id == job['id'])
        except Exception as e:
            print(f"Erro no robô: {e}")
        time.sleep(20)

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

# --- INTERFACE MASTER COM HISTÓRICO ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ads Manager Pro</title>
    <style>
        :root { --blue: #0088cc; --red: #e74c3c; --green: #2ecc71; }
        body { font-family: sans-serif; background: #f0f2f5; margin: 0; padding: 10px; }
        .app { max-width: 600px; margin: auto; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--blue); color: white; padding: 20px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; }
        input, textarea, select { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 10px; box-sizing: border-box; }
        button { width: 100%; padding: 15px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; margin-top: 10px; transition: 0.3s; }
        .btn-blue { background: var(--blue); color: white; }
        .btn-green { background: var(--green); color: white; }
        .btn-gray { background: #6c757d; color: white; }
        
        .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .profile-card { background: #f8f9fa; border: 2px solid #eee; padding: 15px; border-radius: 12px; text-align: center; cursor: pointer; }
        .phrase-box { background: #f8f9fa; padding: 10px; border-radius: 12px; max-height: 120px; overflow-y: auto; border: 1px solid #eee; margin-bottom: 10px; }
        .phrase-item { font-size: 13px; padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }

        /* HISTÓRICO COMPLETO */
        .history-section { margin-top: 30px; border-top: 3px solid #eee; padding-top: 20px; }
        .job-card { background: white; border: 1px solid #ddd; padding: 15px; border-radius: 15px; margin-bottom: 15px; position: relative; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
        .job-card img { width: 70px; height: 70px; border-radius: 10px; float: left; margin-right: 15px; object-fit: cover; border: 1px solid #eee; }
        .job-info { font-size: 12px; }
        .job-info strong { color: var(--blue); font-size: 14px; display: block; margin-bottom: 5px; }
        .btn-trash { position: absolute; top: 10px; right: 10px; background: #fee; color: var(--red); border: 1px solid #fcc; border-radius: 50%; width: 35px; height: 35px; cursor: pointer; font-size: 18px; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 5px; font-weight: bold; margin-top: 5px; font-size: 10px; }
        .badge-wait { background: #fff3cd; color: #856404; }
        .badge-sent { background: #d4edda; color: #155724; }
    </style>
</head>
<body>
<div class="app">
    <div class="header"><h1>Ads Master Cloud</h1></div>
    <div class="p-20">
        <!-- TELA LOGIN -->
        <div id="screen-login">
            <label>Quem está acessando?</label>
            <div id="profiles" class="profile-grid"></div>
            <button class="btn-green" onclick="addProfile()">+ Adicionar Administrador</button>
            <button class="btn-gray" onclick="openAdmin()">⚙️ Configurações</button>
        </div>

        <!-- TELA ADMIN -->
        <div id="screen-admin" class="hidden">
            <label>Token do Bot:</label><input type="password" id="c-token">
            <label>ID do Canal (Ex: -100...):</label><input type="text" id="c-chat">
            <button class="btn-blue" onclick="saveAdmin()">SALVAR CONFIGURAÇÃO</button>
            <button onclick="location.reload()">Voltar</button>
        </div>

        <!-- TELA USUÁRIO -->
        <div id="screen-user" class="hidden">
            <h3 id="u-tag"></h3>
            <div class="phrase-box" id="u-phrases"></div>
            <textarea id="u-msg" rows="3" placeholder="Escreva sua mensagem..."></textarea>
            <label>Texto do Link:</label><input type="text" id="u-ltxt" placeholder="Ex: 👉 CLIQUE E GANHE BÔNUS!">
            <label>URL do Link:</label><input type="url" id="u-lurl">
            <label>Foto da Galeria:</label><input type="file" id="u-img" accept="image/*">
            
            <div style="display:flex; gap:10px;">
                <div style="flex:2"><label>Primeiro Envio:</label><input type="datetime-local" id="u-date"></div>
                <div style="flex:1"><label>Total:</label><input type="number" id="u-qty" value="1"></div>
            </div>
            <label>De quantas em quantas horas?</label><input type="number" id="u-interval" value="24">

            <button class="btn-blue" onclick="schedule()">PROGRAMAR AGORA</button>

            <!-- HISTÓRICO APARECE AQUI -->
            <div class="history-section">
                <h3>📋 Histórico de Mensagens</h3>
                <div id="history-list"></div>
            </div>
            
            <button class="btn-gray" onclick="location.reload()" style="margin-top:20px;">Sair</button>
        </div>
    </div>
</div>

<script>
    let botCfg = {token:'', chat:''};
    let currentUser = "";
    let profiles = JSON.parse(localStorage.getItem('profiles_v3')) || ["Admin Principal", "Marketing"];
    const frases = ["🚀 Ganhe bônus de 100%!", "🔥 Promoção exclusiva hoje!", "🎯 Apostas grátis liberadas!", "💰 Link VIP atualizado!", "🚨 ÚLTIMAS VAGAS!"];

    function init() {
        const div = document.getElementById('profiles'); div.innerHTML = "";
        profiles.forEach(p => div.innerHTML += `<div class="profile-card" onclick="openUser('${p}')">${p}</div>`);
    }

    function addProfile() {
        const n = prompt("Nome do novo Administrador:");
        if(n) { profiles.push(n); localStorage.setItem('profiles_v3', JSON.stringify(profiles)); init(); }
    }

    async function openAdmin() {
        if(prompt("Digite a senha:") === "123456") {
            document.getElementById('screen-login').classList.add('hidden');
            document.getElementById('screen-admin').classList.remove('hidden');
            const r = await fetch('/api/config').then(res=>res.json());
            document.getElementById('c-token').value = r.token;
            document.getElementById('c-chat').value = r.chat;
        }
    }

    async function saveAdmin() {
        await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:document.getElementById('c-token').value, chat:document.getElementById('c-chat').value})});
        alert("Configuração Salva!"); location.reload();
    }

    async function openUser(n) {
        botCfg = await fetch('/api/config').then(r=>r.json());
        if(!botCfg.token) return alert("Configure o Bot no Admin!");
        currentUser = n;
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('u-tag').innerText = "Logado como: " + n;
        const pBox = document.getElementById('u-phrases'); pBox.innerHTML = "";
        frases.forEach(f => {
            let d = document.createElement('div'); d.className='phrase-item'; d.innerText=f;
            d.onclick=()=>document.getElementById('u-msg').value=f;
            pBox.appendChild(d);
        });
        updateHistory();
    }

    async function schedule() {
        const file = document.getElementById('u-img').files[0];
        const img = file ? await toB64(file) : null;
        const start = new Date(document.getElementById('u-date').value).getTime();
        const qty = parseInt(document.getElementById('u-qty').value);
        const interval = parseInt(document.getElementById('u-interval').value) * 60 * 60 * 1000;
        
        const msg = document.getElementById('u-msg').value;
        const linkTxt = document.getElementById('u-ltxt').value;
        const linkUrl = document.getElementById('u-lurl').value;

        for(let i=0; i<qty; i++) {
            const data = {
                id: Date.now() + i,
                user: currentUser,
                token: botCfg.token, chat: botCfg.chat,
                full_text: msg + `\\n\\n<a href="${linkUrl}">${linkTxt}</a>`,
                phrase: msg,
                time: start + (i * interval),
                photo: img, sent: false
            };
            await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
        }
        alert("Programado!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch('/api/jobs').then(r=>r.json());
        const div = document.getElementById('history-list'); div.innerHTML = "";
        
        jobs.sort((a,b)=>b.time - a.time).forEach(j => {
            const status = j.sent ? `<span class="badge badge-sent">ENVIADO (${j.sent_at})</span>` : `<span class="badge badge-wait">AGUARDANDO</span>`;
            const img = j.photo ? `<img src="${j.photo}">` : `<div style="width:70px;height:70px;background:#eee;float:left;margin-right:15px;border-radius:10px;"></div>`;
            
            div.innerHTML += `
                <div class="job-card">
                    <button class="btn-trash" onclick="delJob(${j.id})">🗑️</button>
                    ${img}
                    <div class="job-info">
                        <strong>👤 ${j.user}</strong>
                        <span>📅 ${new Date(j.time).toLocaleString()}</span><br>
                        <span>💬 ${j.phrase.substring(0,40)}...</span><br>
                        ${status}
                    </div>
                    <div style="clear:both;"></div>
                </div>
            `;
        });
    }

    async function delJob(id) {
        if(confirm("Deseja apagar do histórico e cancelar o envio?")) {
            await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
            updateHistory();
        }
    }

    const toB64 = f => new Promise(r => { const rd = new FileReader(); rd.readAsDataURL(f); rd.onload = () => r(rd.result); });
    init();
</script>
</body>
</html>
