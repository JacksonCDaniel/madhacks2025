import time
import json
import traceback
from redis_queue import redis_client, set_job_status, set_job_result
from claude import build_trimmed_history, call_haiku, build_summary, insert_summary_message
from db import insert_message
from tts import synthesize_bytes


def process_tts(job):
    job_id = job['job_id']
    payload = job.get('payload', {})
    text = payload.get('text')
    try:
        # For demo, we will synthesize bytes (convert) and store result in job.result as base64
        audio_bytes = synthesize_bytes(text)
        # store small audio in job result as bytes (not recommended for prod)
        set_job_result(job_id, {'audio_bytes_present': True, 'size': len(audio_bytes)})
        set_job_status(job_id, 'done')
    except Exception as e:
        set_job_status(job_id, 'failed')
        set_job_result(job_id, {'error': str(e), 'trace': traceback.format_exc()})


def process_summarize(job):
    job_id = job['job_id']
    payload = job.get('payload', {})
    messages = payload.get('messages', [])
    conv_id = job.get('conversation_id')
    try:
        summary = build_summary(messages)
        summary_id = insert_summary_message(conv_id, summary)
        set_job_result(job_id, {'summary_id': summary_id})
        set_job_status(job_id, 'done')
    except Exception as e:
        set_job_status(job_id, 'failed')
        set_job_result(job_id, {'error': str(e), 'trace': traceback.format_exc()})


def process_long_response(job):
    job_id = job['job_id']
    conv_id = job.get('conversation_id')
    trigger_msg = job.get('message_id')
    try:
        history = build_trimmed_history(conv_id)
        assistant_text = call_haiku(history)
        assistant_id = insert_message(conversation_id=conv_id, role='assistant', content=assistant_text, metadata={})
        set_job_result(job_id, {'assistant_message_id': assistant_id})
        set_job_status(job_id, 'done')
    except Exception as e:
        set_job_status(job_id, 'failed')
        set_job_result(job_id, {'error': str(e), 'trace': traceback.format_exc()})


def run_forever(poll_interval=1):
    r = redis_client()
    print('Worker started, polling queue:jobs')
    while True:
        try:
            item = r.brpop('queue:jobs', timeout=5)
            if not item:
                time.sleep(poll_interval)
                continue
            # item is (queue_name, job_json)
            job_json = item[1]
            job = json.loads(job_json)
            job_id = job.get('job_id')
            set_job_status(job_id, 'running')
            jtype = job.get('type')
            if jtype == 'tts':
                process_tts(job)
            elif jtype == 'summarize':
                process_summarize(job)
            elif jtype == 'long_response':
                process_long_response(job)
            else:
                set_job_status(job_id, 'failed')
                set_job_result(job_id, {'error': f'unknown job type {jtype}'})
        except Exception as e:
            print('Worker loop error:', e)
            traceback.print_exc()
            time.sleep(poll_interval)


if __name__ == '__main__':
    run_forever()
