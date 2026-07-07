"""
Gerenciamento de Jobs da Web UI
-------------------------------
Modelo de Job/Pack em memória, eventos para SSE e execução em worker thread.
"""
import os
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from config import WEBJOBS_DIR
from modules.utils import garantir_pasta
from modules.anotacoes import listar_anotacoes
from webui.pipeline import run_pack, gerar_artefato

# Jobs com mais de 24h são removidos na inicialização
JOB_MAX_IDADE_SEGUNDOS = 24 * 3600


@dataclass
class Pack:
    ident: str
    files: dict = field(default_factory=dict)  # {'capa': path, 'miolo': path, 'epub': path}
    warnings: list = field(default_factory=list)
    skipped: bool = False
    progress: float = 0.0
    status: str = 'pendente'  # pendente | processando | concluido | pulado | erro
    error: str = ''
    artifacts: list = field(default_factory=list)  # [{key, label, status, error, files}]

    @property
    def outputs(self):
        """Todos os arquivos gerados, achatados (usado para compatibilidade)."""
        return [f for a in self.artifacts for f in a['files']]

    def to_dict(self):
        return {
            'ident': self.ident,
            'files': {k: os.path.basename(v) for k, v in self.files.items() if v},
            'warnings': self.warnings,
            'skipped': self.skipped,
            'progress': round(self.progress * 100, 1),
            'status': self.status,
            'error': self.error,
            'artifacts': self.artifacts,
            'outputs': self.outputs,
        }


@dataclass
class Job:
    id: str
    mode: str  # 'capa' | 'packshots'
    options: dict
    dir: str
    ai_model: str = None  # modelo de IA preferido para o sumário
    packs: list = field(default_factory=list)
    status: str = 'scanning'
    events: list = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def input_dir(self):
        return os.path.join(self.dir, 'entrada')

    @property
    def output_dir(self):
        return os.path.join(self.dir, 'saida')

    def emit(self, event: dict):
        with self.lock:
            self.events.append(event)

    def eventos_desde(self, indice: int):
        with self.lock:
            return self.events[indice:]

    def overall_pct(self):
        ativos = [p for p in self.packs if not p.skipped]
        if not ativos:
            return 100.0
        return round(sum(p.progress for p in ativos) / len(ativos) * 100, 1)

    def to_dict(self):
        return {
            'job_id': self.id,
            'mode': self.mode,
            'status': self.status,
            'overall_pct': self.overall_pct(),
            'packs': [p.to_dict() for p in self.packs],
        }


class JobManager:
    def __init__(self):
        self.jobs = {}
        self.executor = ThreadPoolExecutor(max_workers=1)
        garantir_pasta(WEBJOBS_DIR)
        self._purgar_antigos()

    def _purgar_antigos(self):
        agora = time.time()
        for nome in os.listdir(WEBJOBS_DIR):
            caminho = os.path.join(WEBJOBS_DIR, nome)
            try:
                if os.path.isdir(caminho) and agora - os.path.getmtime(caminho) > JOB_MAX_IDADE_SEGUNDOS:
                    shutil.rmtree(caminho, ignore_errors=True)
            except OSError:
                pass

    def criar_job(self, mode: str, options: dict, ai_model: str = None) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job_dir = os.path.join(WEBJOBS_DIR, job_id)
        garantir_pasta(os.path.join(job_dir, 'entrada'))
        garantir_pasta(os.path.join(job_dir, 'saida'))
        job = Job(id=job_id, mode=mode, options=options, dir=job_dir, ai_model=ai_model)
        self.jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job:
        return self.jobs.get(job_id)

    def escanear_anotacoes(self, job: Job):
        """Verifica anotações em todos os PDFs de cada pack. Retorna packs com avisos."""
        com_avisos = []
        for pack in job.packs:
            for tipo_arquivo, caminho in pack.files.items():
                if caminho and caminho.lower().endswith('.pdf'):
                    anotacoes = listar_anotacoes(caminho)
                    if anotacoes:
                        pack.warnings.append({
                            'arquivo': os.path.basename(caminho),
                            'anotacoes': anotacoes,
                        })
            if pack.warnings:
                com_avisos.append(pack)
        return com_avisos

    def submeter(self, job: Job):
        """Envia o job para processamento em background."""
        job.status = 'queued'
        job.emit({'type': 'status', 'status': 'queued'})
        self.executor.submit(self._processar_job, job)

    def decidir(self, job: Job, action: str):
        """Aplica a decisão do usuário sobre packs com avisos."""
        if action == 'stop':
            job.status = 'stopped'
            job.emit({'type': 'status', 'status': 'stopped'})
            return
        if action == 'skip_flagged':
            for pack in job.packs:
                if pack.warnings:
                    pack.skipped = True
                    pack.status = 'pulado'
        self.submeter(job)

    def _processar_job(self, job: Job):
        job.status = 'processing'
        job.emit({'type': 'status', 'status': 'processing'})

        for pack in job.packs:
            if job.status == 'stopped':
                break
            if pack.skipped:
                job.emit({'type': 'pack_skipped', 'ident': pack.ident})
                continue

            pack.status = 'processando'
            job.emit({'type': 'pack_start', 'ident': pack.ident})

            def on_progress(mensagem, fracao, _pack=pack):
                _pack.progress = min(max(fracao, 0.0), 1.0)
                job.emit({
                    'type': 'pack_progress',
                    'ident': _pack.ident,
                    'pct': round(_pack.progress * 100, 1),
                    'overall_pct': job.overall_pct(),
                    'message': mensagem,
                })

            try:
                run_pack(job, pack, on_progress)
                pack.progress = 1.0
                # Concluído se ao menos um artefato saiu; erro se todos falharam.
                houve_ok = any(a['status'] == 'ok' for a in pack.artifacts)
                pack.status = 'concluido' if houve_ok else 'erro'
                if not houve_ok and pack.artifacts:
                    pack.error = pack.artifacts[0].get('error', 'Nenhum artefato gerado.')
                job.emit({
                    'type': 'pack_done',
                    'ident': pack.ident,
                    'overall_pct': job.overall_pct(),
                    'artifacts': pack.artifacts,
                })
            except Exception as e:
                pack.status = 'erro'
                pack.error = str(e)
                pack.progress = 1.0
                job.emit({'type': 'pack_error', 'ident': pack.ident, 'message': str(e)})

        if job.status != 'stopped':
            job.status = 'done'
            job.emit({
                'type': 'job_done',
                'zip_url': f'/api/jobs/{job.id}/download',
                'overall_pct': 100.0,
            })

    def retry_artefato(self, job: Job, ident: str, key: str, model: str = None):
        """Reprocessa um único artefato de um pack. Retorna o artefato atualizado ou None."""
        pack = next((p for p in job.packs if p.ident == ident), None)
        if not pack:
            return None

        novo = gerar_artefato(job, pack, key, model=model)

        # Substitui na lista existente ou adiciona
        for i, a in enumerate(pack.artifacts):
            if a['key'] == key:
                pack.artifacts[i] = novo
                break
        else:
            pack.artifacts.append(novo)

        # Reavalia status do pack
        if any(a['status'] == 'ok' for a in pack.artifacts):
            pack.status = 'concluido'
        return novo


manager = JobManager()
