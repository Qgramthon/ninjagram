from flask import Flask, jsonify, request
import os
import json
from shared import active_clients, user_info_cache, command_stats, DATA_DIR

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        'status': 'running',
        'sessions': list(active_clients.keys()),
        'total_sessions': len(active_clients)
    })

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'active': len(active_clients)})

@app.route('/sessions')
def get_sessions():
    return jsonify({
        'sessions': list(active_clients.keys()),
        'count': len(active_clients)
    })

@app.route('/stats')
def get_stats():
    return jsonify({
        'command_stats': {k: dict(v) for k, v in command_stats.items()},
        'user_info_count': len(user_info_cache)
    })

@app.route('/info/<phone>')
def get_user_info(phone):
    if phone in user_info_cache:
        return jsonify(user_info_cache[phone])
    return jsonify({'error': 'not found'}), 404
