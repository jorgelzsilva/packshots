"""
Servidor Web do Packshots
-------------------------
FastAPI: upload, verificação de anotações, processamento com progresso via SSE
e download dos resultados.
"""
import asyncio
import json
import os
import zipfile

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import KEYWORDS_MIOLO, KEYWORDS_CAPA, EXPORTAR_CAPA, AI_MODEL, AI_FALLBACK_MODELS
from modules.utils import extrair_identificador
from webui.jobs import manager, Pack

app = FastAPI(title="Packshots Web UI")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/models")
def listar_modelos():
    """Lista os modelos de IA disponíveis (principal + reservas)."""
    modelos = [AI_MODEL] + [m for m in AI_FALLBACK_MODELS if m != AI_MODEL]
    return {'models': modelos, 'default': AI_MODEL}


def _salvar_uploads(job, files):
    """Salva os uploads na pasta de entrada do job. Retorna {nome: caminho}."""
    salvos = {}
    for f in files:
        nome = os.path.basename(f.filename or '').replace('\\', '_')
        if not nome:
            continue
        destino = os.path.join(job.input_dir, nome)
        with open(destino, 'wb') as out:
            out.write(f.file.read())
        salvos[nome] = destino
    return salvos


def _montar_packs_capa(job, salvos):
    """Modo 'Apenas Capa': cada PDF vira um pack."""
    for nome, caminho in salvos.items():
        if not nome.lower().endswith('.pdf'):
            continue
        ident = extrair_identificador(nome)
        job.packs.append(Pack(ident=ident, files={'capa': caminho}))


def _montar_packs_slots(job, salvos, slots):
    """Modo 'Packshots' com slots nomeados: um único pack."""
    files = {}
    for nome, slot in slots.items():
        nome = os.path.basename(nome)
        if slot in ('miolo', 'capa', 'epub') and nome in salvos:
            files[slot] = salvos[nome]
    if not files.get('miolo'):
        raise HTTPException(400, "O arquivo de Miolo é obrigatório no modo Packshots.")
    ident = extrair_identificador(os.path.basename(files['miolo']))
    job.packs.append(Pack(ident=ident, files=files))


def _montar_packs_lote(job, salvos):
    """Modo 'Packshots' em lote: agrupa por identificador, espelhando o CLI."""
    identificadores = {}
    for nome in salvos:
        nome_lower = nome.lower()
        if nome_lower.endswith('.pdf') and any(kw in nome_lower for kw in KEYWORDS_MIOLO):
            identificadores[extrair_identificador(nome)] = nome

    usados = set()
    for ident, nome_miolo in sorted(identificadores.items()):
        files = {'miolo': salvos[nome_miolo]}
        usados.add(nome_miolo)
        for nome in salvos:
            if nome in usados or not nome.startswith(ident):
                continue
            nome_lower = nome.lower()
            if nome_lower.endswith('.pdf') and any(kw in nome_lower for kw in KEYWORDS_CAPA):
                files['capa'] = salvos[nome]
                usados.add(nome)
            elif nome_lower.endswith('.epub'):
                files['epub'] = salvos[nome]
                usados.add(nome)
        job.packs.append(Pack(ident=ident, files=files))

    ignorados = [n for n in salvos if n not in usados]
    if ignorados:
        job.emit({
            'type': 'warning',
            'message': f"Arquivos sem miolo correspondente foram ignorados: {', '.join(ignorados)}",
        })


@app.post("/api/jobs")
async def criar_job(
    files: list[UploadFile] = File(...),
    mode: str = Form(...),
    options: str = Form("{}"),
    slots: str = Form(""),
    ai_model: str = Form(""),
):
    if mode not in ('capa', 'packshots'):
        raise HTTPException(400, "Modo inválido. Use 'capa' ou 'packshots'.")

    try:
        opcoes = json.loads(options) if options else {}
    except json.JSONDecodeError:
        raise HTTPException(400, "Campo 'options' não é um JSON válido.")

    if mode == 'capa':
        config_exportar = dict(EXPORTAR_CAPA)
        config_exportar['debug'] = False
        for chave in ('capa', 'quarta_capa', 'lombada', 'orelha_esq', 'orelha_dir'):
            if chave in opcoes:
                config_exportar[chave] = bool(opcoes[chave])
    else:
        config_exportar = {}

    job = manager.criar_job(mode, config_exportar, ai_model=(ai_model or None))
    salvos = await asyncio.to_thread(_salvar_uploads, job, files)

    if not salvos:
        raise HTTPException(400, "Nenhum arquivo recebido.")

    if mode == 'capa':
        _montar_packs_capa(job, salvos)
    else:
        mapa_slots = {}
        if slots:
            try:
                mapa_slots = json.loads(slots)
            except json.JSONDecodeError:
                raise HTTPException(400, "Campo 'slots' não é um JSON válido.")
        if mapa_slots:
            _montar_packs_slots(job, salvos, mapa_slots)
        else:
            _montar_packs_lote(job, salvos)

    if not job.packs:
        raise HTTPException(400, "Nenhum pack identificado nos arquivos enviados.")

    com_avisos = await asyncio.to_thread(manager.escanear_anotacoes, job)

    if com_avisos:
        job.status = 'awaiting_decision'
        avisos = [{'ident': p.ident, 'warnings': p.warnings} for p in com_avisos]
        job.emit({'type': 'warnings', 'packs': avisos})
        return JSONResponse({**job.to_dict(), 'warnings': avisos})

    manager.submeter(job)
    return JSONResponse(job.to_dict())


@app.get("/api/jobs/{job_id}")
def estado_job(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/events")
async def eventos_job(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")

    async def gerar():
        indice = 0
        while True:
            novos = job.eventos_desde(indice)
            for evento in novos:
                yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
            indice += len(novos)
            if job.status in ('done', 'stopped', 'error') and not job.eventos_desde(indice):
                yield "event: close\ndata: {}\n\n"
                break
            await asyncio.sleep(0.2)

    return StreamingResponse(gerar(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/jobs/{job_id}/decision")
async def decisao_job(job_id: str, payload: dict):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    if job.status != 'awaiting_decision':
        raise HTTPException(409, f"Job não está aguardando decisão (status: {job.status}).")

    action = payload.get('action')
    if action not in ('continue_all', 'stop', 'skip_flagged'):
        raise HTTPException(400, "Ação inválida. Use continue_all, stop ou skip_flagged.")

    manager.decidir(job, action)
    return job.to_dict()


@app.post("/api/jobs/{job_id}/packs/{ident}/retry")
async def retry_artefato(job_id: str, ident: str, payload: dict):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")

    key = payload.get('artifact')
    if not key:
        raise HTTPException(400, "Informe o artefato a reprocessar em 'artifact'.")

    model = payload.get('model') or None
    artefato = await asyncio.to_thread(manager.retry_artefato, job, ident, key, model)
    if artefato is None:
        raise HTTPException(404, "Pacote não encontrado.")
    return {'artifact': artefato}


@app.get("/api/jobs/{job_id}/results")
def resultados_job(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")
    return {
        'job_id': job.id,
        'status': job.status,
        'zip_url': f'/api/jobs/{job.id}/download',
        'packs': [p.to_dict() for p in job.packs],
    }


@app.get("/api/jobs/{job_id}/files/{ident}/{filename}")
def baixar_arquivo(job_id: str, ident: str, filename: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")

    caminho = os.path.realpath(os.path.join(job.output_dir, ident, filename))
    raiz = os.path.realpath(job.output_dir)
    if not caminho.startswith(raiz + os.sep) or not os.path.isfile(caminho):
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(caminho, filename=filename)


@app.get("/api/jobs/{job_id}/download")
def baixar_zip(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado.")

    caminho_zip = os.path.join(job.dir, f"packshots_{job.id}.zip")
    with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for raiz_dir, _dirs, nomes in os.walk(job.output_dir):
            for nome in nomes:
                caminho = os.path.join(raiz_dir, nome)
                zf.write(caminho, os.path.relpath(caminho, job.output_dir))
    return FileResponse(caminho_zip, filename=f"packshots_{job.id}.zip")
