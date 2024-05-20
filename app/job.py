import time
import threading

from app import logger
from app.collection import Analysis
import app.smrtlink as smrtlink
from app.state import AnalysisModel, LastJobUpdate, ProjectDataset

def _get_job_project_dataset(job_id):
    rows = (AnalysisModel.select(AnalysisModel.project_id,
                                 AnalysisModel.dataset_id)
                         .where(AnalysisModel.analysis_id == job_id)
                         .execute())
    if not rows:
        return None
    for row in rows:
        yield row.project_id, row.dataset_id

def get_analyses(datasets, project_id):
    for ds in datasets:
        jobs = smrtlink.get_dataset_jobs(ds.id)
        ids_to_ignore = (AnalysisModel.select(AnalysisModel.analysis_id)
                                      .where(AnalysisModel.dataset_id == ds.id,
                                             AnalysisModel.project_id == project_id)
                                      .execute())
        for job_d in [j for j in jobs if j['id'] not in ids_to_ignore]:
            if job_d['state'] == 'SUCCESSFUL':
                files = smrtlink.get_job_files(job_d['id'])
                yield Analysis(ds.dir_path, 
                                job_d['name'], 
                                job_d['id'], 
                                files)

def _get_new_jobs():
    try:
        jobs = smrtlink.get_jobs_created_after(LastJobUpdate.time())
    except Exception as e:
        logger.error(f'Cannot get new jobs: {e}')
        return []
    if not jobs:
        return []
    else:
        latest_timestamp = sorted([job['createdAt'] for job in jobs])[-1]
        LastJobUpdate.set(latest_timestamp)
        return jobs

def _get_dataset_dirs(id):
    return (ProjectDataset.select(ProjectDataset.staging_dir)
                         .where(ProjectDataset.dataset_id == id)
                         .execute())

def get_analyses():
    completed = []
    pending = []
    for job in _get_new_jobs():
        dataset_ids = smrtlink.get_job_datasets(job['id'])
        for dataset_id in dataset_ids:
            dirs = _get_dataset_dirs(dataset_id)
            if not dirs:
                continue # skip jobs for datasets not in the database, i.e. not in a project
            if job['state'] in {'FAILED', 'TERMINATED', 'ABORTED'}:
                continue 
            files = smrtlink.get_job_files(job['id'])
            for dir in dirs:
                if job['state'] == 'SUCCESSFUL':
                    completed.append(Analysis(dir, job['name'], job['id'], files))
                elif job['state'] in {'CREATED', 'SUBMITTED', 'RUNNING'}:
                    pending.append(Analysis(dir, job['name'], job['id'], files))
                else:
                    raise ValueError(f"Unexpected job state: {job['state']}")
    return completed, pending

MAX_POLLING_TIME = 86400
POLL_RATE = 30

def _poll(analysis, staging_function):
    t_start = time.time()
    while True:
        job = smrtlink.get_job(analysis.id)
        if not job:
            logger.error(f'Cannot handle job {analysis.id}: Job not found in SMRT Link.')
            return
        state = job["state"]
        if state in {"SUCCESSFUL", "FAILED", "TERMINATED", "ABORTED"}:
            if state == "SUCCESSFUL":
                staging_function(analysis)
                return
        t_current = time.time()
        if t_current - t_start > MAX_POLLING_TIME:
            logger.error(f"Failed to handle analysis {analysis.id}: Max polling time ({MAX_POLLING_TIME}s) exceeded.")
            return
        time.sleep(POLL_RATE)

def track(pending_analyses, staging_function):
    for analysis in pending_analyses:
        poll_thread = threading.Thread(target=_poll, args=(analysis, staging_function))
        poll_thread.start()