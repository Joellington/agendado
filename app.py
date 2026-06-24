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

# --- ROBÔ DE DISPARO REFORÇADO ---
def bot_worker():
    while True:
        try:
            now = datetime.now().timestamp() * 1000
            Job = Query()
            # Pega mensagens agendadas
            pending_jobs = db.search((Job.sent == False) & (Job.time <= now))
            
            for job in pending_jobs:
                token = job['token']
                chat_id = job['chat']
                text = job['full_text'] # Texto com HTML para o link
                url = f"https://api.telegram.org/bot{token}/"
                
                # Tenta enviar com foto
                if job.get('photo'):
                    try:
                        header, encoded = job['photo'].split(",", 1)
                        photo_data = base64.b64decode(encoded)
                        files = {'photo': ('image.jpg', photo_data)}
                        resp = requests.post(url + "sendPhoto", data={'chat_id': chat_id, 'caption': text, 'parse_mode': 'HTML'}, files=files, timeout=10)
                    except:
                        resp = requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
                else:
                    resp = requests.post(url + "sendMessage", data={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
                
                # Só marca como enviado se o Telegram aceitar ou se houver erro de chat
                if resp.status_code == 200 or resp.status_code == 400:
                    db.update({'sent': True, 'sent_at': datetime.now().strftime('%d/%m %H:%M')}, Job.id == job['id'])
        except Exception as e:
            print(f"Erro crítico no robô: {e}")
        time.sleep(15) # Checa a cada 15 segundos

# --- API ---
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

# --- INTERFACE MASTER ---
HTML_CODE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Ads Master</title>
    <style>
        :root { --blue: #0088cc; --green: #2ecc71; --red: #e74c3c; --bg: #f0f2f5; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .container { max-width: 600px; margin: auto; background: white; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: var(--blue); color: white; padding: 20px; text-align: center; }
        .p-20 { padding: 20px; }
        .hidden { display: none; }
        
        label { display: block; margin: 15px 0 5px; font-weight: bold; }
        input, textarea, select { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 10px; box-sizing: border-box; font-size: 14px; }
        
        button { width: 100%; padding: 15px; border: none; border-radius: 10px; cursor: pointer; font-weight: bold; transition: 0.3s; margin-top: 10px; }
        .btn-blue { background: var(--blue); color: white; }
        .btn-green { background: var(--green); color: white; }
        .btn-gray { background: #6c757d; color: white; }
        
        .profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .profile-card { background: #f8f9fa; border: 2px solid #eee; padding: 15px; border-radius: 12px; text-align: center; cursor: pointer; }
        .profile-card:hover { border-color: var(--blue); }

        .phrase-box { background: #f8f9fa; padding: 10px; border-radius: 12px; max-height: 150px; overflow-y: auto; border: 1px solid #eee; margin-bottom: 10px; }
        .phrase-item { font-size: 13px; padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }
        .phrase-item:hover { background: #eef; color: var(--blue); }

        /* Histórico Detalhado */
        .history-list { margin-top: 30px; border-top: 2px solid #eee; padding-top: 20px; }
        .job-card { background: white; border: 1px solid #eee; padding: 15px; border-radius: 15px; margin-bottom: 15px; position: relative; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
        .job-card img { width: 50px; height: 50px; border-radius: 8px; float: left; margin-right: 15px; object-fit: cover; }
        .job-info { font-size: 12px; line-height: 1.4; }
        .job-info strong { color: var(--blue); }
        .status-badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-top: 5px; }
        .status-wait { background: #fff3cd; color: #856404; }
        .status-sent { background: #d4edda; color: #155724; }
        .btn-del { position: absolute; top: 10px; right: 10px; background: #fee; color: var(--red); border: 1px solid #fcc; border-radius: 50%; width: 30px; height: 30px; cursor: pointer; }
    </style>
</head>
<body>
<div class="container">
    <div class="header"><h1>Ads Cloud Master</h1></div>
    <div class="p-20">
        
        <!-- TELA LOGIN -->
        <div id="screen-login">
            <label>Selecione seu Perfil:</label>
            <div id="profiles" class="profile-grid"></div>
            <button class="btn-green" onclick="addAdmin()">+ Adicionar Administrador</button>
            <button class="btn-gray" onclick="openConfig()">⚙️ Bot Setup (Senha: 123456)</button>
        </div>

        <!-- TELA CONFIG -->
        <div id="screen-admin" class="hidden">
            <label>Bot Token:</label><input type="password" id="c-token">
            <label>Chat ID do Grupo/Canal:</label><input type="text" id="c-chat">
            <button class="btn-blue" onclick="saveConfig()">SALVAR CONFIGURAÇÃO</button>
            <button class="btn-gray" onclick="location.reload()">Voltar</button>
        </div>

        <!-- TELA AGENDADOR -->
        <div id="screen-user" class="hidden">
            <h3 id="u-tag"></h3>
            
            <label>Frases de Impacto (Pré-programadas):</label>
            <div class="phrase-box" id="u-phrases"></div>
            
            <textarea id="u-msg" rows="3" placeholder="Escreva a mensagem aqui..."></textarea>
            
            <label>Frase do Link (Vira o Link):</label>
            <input type="text" id="u-ltxt" placeholder="Ex: 🤑 PEGAR MEU BÔNUS AGORA!">
            
            <label>URL do Link de Afiliado:</label>
            <input type="url" id="u-lurl" placeholder="https://...">

            <label>Foto da Galeria:</label>
            <input type="file" id="u-img" accept="image/*">

            <div style="display:flex; gap:10px;">
                <div style="flex:2"><label>Primeiro Envio:</label><input type="datetime-local" id="u-date"></div>
                <div style="flex:1"><label>Total de Envios:</label><input type="number" id="u-qty" value="1" min="1"></div>
            </div>

            <label>Intervalo entre envios (Horas):</label>
            <input type="number" id="u-interval" value="24" min="1" placeholder="Ex: 1 para cada hora, 24 para diário">

            <button class="btn-blue" onclick="schedule()">PROGRAMAR DISPAROS</button>

            <div class="history-list">
                <h4>📜 Histórico e Fila de Mensagens</h4>
                <div id="history"></div>
            </div>

            <button class="btn-gray" onclick="location.reload()">Sair</button>
        </div>

    </div>
</div>

<script>
    let botCfg = {token:'', chat:''};
    let currentUser = "";
    let profiles = JSON.parse(localStorage.getItem('profiles_v2')) || ["Admin Principal", "Marketing VIP"];
    const frasesProntas = [
        "🚀 Venha conferir essa oportunidade única!",
        "💰 BÔNUS DE 100% PARA NOVOS USUÁRIOS!",
        "🚨 ÚLTIMAS VAGAS! O acesso será fechado.",
        "💎 Estratégia VIP liberada. Veja os resultados!",
        "🔥 O mercado está pagando muito hoje, aproveite!",
        "🎯 Apostas grátis liberadas para quem entrar agora.",
        "📍 Link atualizado! Acesse e garanta sua vaga.",
        "💸 Quer mudar sua realidade financeira? Clique abaixo.",
        "👑 Método testado e aprovado por milhares.",
        "⚠️ Atenção: Promoção válida por apenas 30 minutos!"
    ];

    function init() {
        const div = document.getElementById('profiles'); div.innerHTML = "";
        profiles.forEach(p => div.innerHTML += `<div class="profile-card" onclick="openUser('${p}')">${p}</div>`);
    }

    function addAdmin() {
        const n = prompt("Nome do novo Administrador:");
        if(n) { profiles.push(n); localStorage.setItem('profiles_v2', JSON.stringify(profiles)); init(); }
    }

    async function openConfig() {
        if(prompt("Senha:") === "123456") {
            document.getElementById('screen-login').classList.add('hidden');
            document.getElementById('screen-admin').classList.remove('hidden');
            const r = await fetch('/api/config').then(res=>res.json());
            document.getElementById('c-token').value = r.token;
            document.getElementById('c-chat').value = r.chat;
        }
    }

    async function saveConfig() {
        await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:document.getElementById('c-token').value, chat:document.getElementById('c-chat').value})});
        alert("Configuração Salva!"); location.reload();
    }

    async function openUser(name) {
        botCfg = await fetch('/api/config').then(r=>r.json());
        if(!botCfg.token) return alert("Erro: O Admin precisa configurar o Token e o Chat ID!");
        currentUser = name;
        document.getElementById('screen-login').classList.add('hidden');
        document.getElementById('screen-user').classList.remove('hidden');
        document.getElementById('u-tag').innerText = "Logado como: " + name;
        const box = document.getElementById('u-phrases'); box.innerHTML = "";
        frasesProntas.forEach(f => {
            let d = document.createElement('div'); d.className='phrase-item'; d.innerText=f;
            d.onclick=()=>document.getElementById('u-msg').value=f;
            box.appendChild(d);
        });
        updateHistory();
    }

    async function schedule() {
        const file = document.getElementById('u-img').files[0];
        const img = file ? await toB64(file) : null;
        const start = new Date(document.getElementById('u-date').value).getTime();
        const qty = parseInt(document.getElementById('u-qty').value);
        const hours = parseInt(document.getElementById('u-interval').value);
        const intervalMs = hours * 60 * 60 * 1000;

        const msgBase = document.getElementById('u-msg').value;
        const linkTxt = document.getElementById('u-ltxt').value;
        const linkUrl = document.getElementById('u-lurl').value;

        if(!start || !linkUrl) return alert("Selecione a data e insira o link!");

        for(let i=0; i<qty; i++) {
            const data = {
                id: Date.now() + i,
                user: currentUser,
                token: botCfg.token, chat: botCfg.chat,
                full_text: msgBase + `\\n\\n<a href="${linkUrl}">${linkTxt}</a>`,
                phrase: msgBase,
                time: start + (i * intervalMs),
                photo: img, sent: false
            };
            await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
        }
        alert(qty + " envios programados!"); updateHistory();
    }

    async function updateHistory() {
        const jobs = await fetch('/api/jobs').then(r=>r.json());
        const div = document.getElementById('history'); div.innerHTML = "";
        
        jobs.sort((a,b)=>b.time - a.time).forEach(j => {
            const date = new Date(j.time).toLocaleString();
            const status = j.sent ? `<span class="status-badge status-sent">ENVIADO (${j.sent_at})</span>` : `<span class="status-badge status-wait">AGUARDANDO</span>`;
            const img = j.photo ? `<img src="${j.photo}">` : `<div style="width:50px;height:50px;background:#eee;float:left;margin-right:15px;border-radius:8px;"></div>`;
            
            div.innerHTML += `
                <div class="job-card">
                    <button class="btn-del" onclick="delJob(${j.id})">×</button>
                    ${img}
                    <div class="job-info">
                        <strong>👤 ${j.user}</strong>
                        <span>📅 ${date}</span><br>
                        <span>💬 ${j.phrase.substring(0,30)}...</span><br>
                        ${status}
                    </div>
                    <div style="clear:both;"></div>
                </div>
            `;
        });
    }

    async function delJob(id) {
        if(confirm("Deseja apagar esse registro e cancelar o envio?")) {
            await fetch('/api/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
            updateHistory();
        }
    }

    const toB64 = f => new Promise(r => { const rd = new FileReader(); rd.readAsDataURL(f); rd.onload = () => r(rd.result); });
    init();
</script>
</body>
</html>
"""

if __name__ == '__main__':
    threading.Thread(target=bot_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
