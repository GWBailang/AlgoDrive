from flask import Flask, request, send_from_directory, session, redirect, url_for, render_template, Request
# from werkzeug.utils import secure_filename
from urllib.parse import quote
from werkzeug.security import check_password_hash
from threading import Timer
import re
import os
import datetime
import shutil
import json
import time

class RealIPMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        real_ip = environ.get('HTTP_CF_CONNECTING_IP')
        
        if real_ip:# 强行覆盖原始环境中的远程地址属性
            environ['REMOTE_ADDR'] = real_ip
            
        return self.app(environ, start_response)

app = Flask(__name__)
app.wsgi_app = RealIPMiddleware(app.wsgi_app)

def load_config(): # 获取 config.json 的数据
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = load_config()

app.config['MAX_CONTENT_LENGTH']= CONFIG['MAX_CONTENT_LENTH_MB'] * 1024 * 1024
# 由于 Cloudflared 的限制实际可能只能上传 100MB
CHUNK_SIZE = CONFIG['CHUNK_SIZE_MB'] * 1024 * 1024
MAX_TOTAL_CHUNKS = CONFIG['MAX_CONTENT_LENTH_MB'] // CONFIG['CHUNK_SIZE_MB'] + 1
CLEANUP_S = CONFIG.get('TEMP_CLEANUP_HOURS', 24) * 3600
app.secret_key = CONFIG['SECRET_KEY']
STORAGE_DIR = CONFIG.get('STORAGE_DIR', 'files') # 存储网盘文件的文件夹
USER_DB = CONFIG['USER'] # 账号
LOGIN_CD = CONFIG['LOGIN_CD_S']

TEMP_DIR = CONFIG.get('TEMP_DIR', 'temp')


def log_request(action, detail=f""): # 显示真实 ip 的日志
    ip = get_real_ip()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now}] IP: {ip} | {action} | {detail}")

def get_real_ip(): # 通过 cf 的 header 获取真实 ip
    real_ip = request.headers.get('CF-Connecting-IP')

    if not real_ip:
        real_ip = request.remote_addr
    
    return real_ip

def clean_filename(name): # 过滤非法字符(替换为`_`)
    # 白名单: 中文(\u4e00-\u9fa5), 英文, 数字, ._-[]()
    pattern = r'[^\u4e00-\u9fa5a-zA-Z0-9\._\-\[\]\(\)]'

    cleaned = re.sub(pattern, '_', name)

    if not cleaned or cleaned in ('.', '..'):
        cleaned = "unnamed_folder"
    
    return cleaned[:150]

def is_save_path(path, base_dir):
    return os.path.abspath(path).startswith(os.path.abspath(base_dir))

def clean_temp_dir():# 清理临时上传文件
    temp_dir = CONFIG.get('TEMP_DIR', 'temp')
    expiry_seconds = CONFIG.get('TEMP_CLEANUP_HOURS', 12) * 3600
    if not os.path.exists(temp_dir):
        print(f"[{time.ctime()}] 目录 {temp_dir} 不存在")
        return
    
    now = time.time()
    count = 0

    for d in os.listdir(temp_dir):
        d_path = os.path.join(temp_dir, d)

        if os.path.isdir(d_path):
            mtime = os.path.getmtime(d_path)
            
            if now - mtime > expiry_seconds:
                try:
                    shutil.rmtree(d_path)
                    print(f"[{time.ctime()}] 清理过期目录 {d}")
                    count += 1
                except Exception as e:
                    print(f"[{time.ctime()}] 删除 {d} 失败: {e}")
    
    if count > 0:
        print(f"[{time.ctime()}] 清理了 {count} 个过期目录")

def schedule_cleanup(): # 定时清理 temp 文件夹
    try:
        clean_temp_dir()
    except Exception as e:
        wbx = 'ryh'
    
    t = Timer(3600, schedule_cleanup)
    t.daemon = True
    t.start()

@app.route('/ip/') # 测试 IP
def ip():
    ip = get_real_ip()
    print(f"TEST_IP: {ip}")
    return f"your ip: {ip}"

last_login_times = {}

@app.route('/login/', methods=['GET', 'POST']) # 登录账号
def login():
    ip = get_real_ip()
    now = time.time()

    if request.method == 'POST':
        last_time = last_login_times.get(ip, 0)
        if now - last_time < LOGIN_CD: # 冷却时间
            return f"未过冷却时间(cd: {LOGIN_CD} s)", 429

        user = request.form.get('username')
        pwd = request.form.get('password')

        stored_hash = USER_DB["password_hash"]

        if user == USER_DB["username"] and check_password_hash(stored_hash, pwd):
            log_request("LOGIN", f"username:{user}")
            session['logged_in'] = True
            last_login_times.pop(ip, None)
            return redirect(url_for('root'))
        
        last_login_times[ip] = now
        log_request("LOGIN_FAILED", f"username:{ip}")
        return "账号或密码错误", 401
    
    if session.get('logged_in', False):
        return redirect(url_for('root'))

    return render_template('login.html')

@app.route('/logout/')
def logout():
    if not session.get('logged_in', False):
        return "本来就没登录", 403
    log_request("LOGOUT")
    session.pop('logged_in', None)
    return redirect(url_for('root'))

@app.route('/')
def root():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    return redirect(url_for('view'))

@app.route('/view/')
@app.route('/view/<path:subpath>')
def view(subpath=''):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    real_path = os.path.join(STORAGE_DIR, subpath)

    if not is_save_path(real_path, STORAGE_DIR):
        return "非法路径", 403

    if os.path.isfile(real_path):
        return redirect(url_for('download', subpath = subpath))

    if os.path.isdir(real_path):
        log_request("VIEW", f"path: {subpath}")
        visible_files = os.listdir(real_path)

        visible_files.sort()
        items_data = []

        for f in visible_files:
            item_path = os.path.join(real_path, f)
            url_path = quote(os.path.join(subpath, f))

            is_dir = os.path.isdir(item_path)
            items_data.append({
                "name": f + ("/" if is_dir else ""),
                "url_path": url_path,
                "icon": "📁" if is_dir else "📄"
            })

        parent_path = os.path.dirname(subpath)

        return render_template('view.html',
                               subpath=subpath,
                               parent_path=parent_path,
                               items=items_data,
                               chunk_size=CHUNK_SIZE,
                               max_total_chunks=MAX_TOTAL_CHUNKS)
    return "路径不存在", 403

@app.route('/mkdir/', methods=['POST'])
@app.route('/mkdir/<path:subpath>', methods=['POST'])
def mkdir(subpath=''):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # print(f"DEBUG: 所有表单数据: {request.form}")

    folder_name = request.form.get('dir')
    if not folder_name:
        return "文件夹名不可为空", 400

    folder_name = clean_filename(folder_name)
    real_dir = os.path.join(STORAGE_DIR, subpath, folder_name)
    if not is_save_path(real_dir, STORAGE_DIR):
        return "非法路径", 403

    if os.path.exists(real_dir):
        return "文件已存在", 400
    
    os.makedirs(real_dir)
    log_request("MKDIR", f"dir: {real_dir}")

    return redirect(url_for('view', subpath=subpath))


@app.route('/upload/', methods=['POST'])
@app.route('/upload/<path:subpath>', methods=['POST'])
def upload(subpath=''):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    real_dir = os.path.join(STORAGE_DIR, subpath)

    if not is_save_path(real_dir, STORAGE_DIR):
        return "非法路径", 403
    if not os.path.exists(real_dir):
        os.makedirs(real_dir)
        log_request("MKDIR", f"dir: {real_dir}")

    file = request.files.get('the_file')
    if not file or file.filename == '':
        return "未选择文件或文件名为空", 400
    filename = clean_filename(file.filename)
    if file:
        save_path = os.path.join(real_dir, filename)
        if not is_save_path(real_dir, STORAGE_DIR):
            return "非法路径", 403
        file.save(save_path)
        log_request("UPLOAD", f"save_path: {save_path}")
        return redirect(url_for('view', subpath=subpath))
    return "未选择文件", 400

@app.route('/upload_chunk', methods=['POST'])
def upload_chunk():
    if not session.get('logged_in'):
        return "未登录", 401

    total_chunks = int(request.form.get('total_chunks', 0))
    if total_chunks * CHUNK_SIZE > CONFIG['MAX_CONTENT_LENTH_MB'] * 1024 * 1024:
        return "文件总大小超出限制", 413

    file_chunk = request.files.get('file_chunk') # 段
    index = request.form.get('index') # 第几段
    upload_id = request.form.get('upload_id') # 任务唯一 ID

    if not file_chunk or not upload_id or not index:
        return "缺少参数", 400
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', upload_id):
        return "非法的上传 ID", 403
    if not re.match(r'^[0-9]+$', index):
        return "非法的索引", 403

    file_chunk.seek(0, os.SEEK_END)
    actual_size = file_chunk.tell()
    file_chunk.seek(0)

    if actual_size == 0:
        return "检测到空段", 400

    temp_dir = os.path.join(TEMP_DIR, upload_id)
    if os.path.exists(temp_dir):
        existing_chunks_count = len(os.listdir(temp_dir))
        if existing_chunks_count >= MAX_TOTAL_CHUNKS:
            return "上传段数过多，拒绝接收", 403

    temp_dir = os.path.join(TEMP_DIR, upload_id)

    if not is_save_path(temp_dir, TEMP_DIR):
        return "非法路径", 403
    
    os.makedirs(temp_dir, exist_ok=True)

    chunk_path = os.path.join(temp_dir, str(index))
    file_chunk.save(chunk_path)

    return "保存成功", 200

@app.route('/merge_chunks', methods=['POST'])
def merge_chunks():
    if not session.get('logged_in'):
        return "未登录", 401
    
    # data = request.json
    data = request.get_json(force=True)
    if not data:
        return "无效的 JSON 数据", 400

    upload_id = data.get('upload_id')
    filename = clean_filename(data.get('filename', 'unnamed'))
    # total_chunks = int(data.get('total_chunks'))
    try:
        total_chunks = int(data.get('total_chunks', 0))
    except ValueError:
        return "非法的段数格式", 403

    subpath = data.get('subpath', '')

    temp_dir = os.path.join(TEMP_DIR, upload_id)
    final_dir = os.path.join(STORAGE_DIR, subpath)
    final_path = os.path.join(final_dir, filename)

    if not is_save_path(temp_dir, TEMP_DIR):
        return "非法的临时路径", 403
    if not is_save_path(final_path, STORAGE_DIR):
        return "非法路径", 403

    if total_chunks == 0:
        try:
            os.makedirs(final_dir, exist_ok=True)
            with open(final_path, 'wb') as f:
                pass
            log_request("MERGE_SUCCESS", f"empty_file: {filename}")
            return "合并成功(空文件)", 200
        except Exception as e:
            return f"创建空文件失败：{str(e)}", 500

    if not os.path.exists(temp_dir):
        log_request("MERGE_ERROR", f"Missing temp_dir for {upload_id}")
        return "找不到临时上传目录", 400

    # total_chunks = int(data.get('total_chunks', 0))
    try:
        actual_chunks = os.listdir(temp_dir)
        if len(actual_chunks) != total_chunks:
            return f"碎片数量不匹配：期待 {total_chunks}，实际 {len(actual_chunks)}", 400
    except Exception as e:
        return f"读取碎片列表失败：{str(e)}", 500

    if total_chunks > MAX_TOTAL_CHUNKS:
        return "段数过多", 400
    
    try:
        os.makedirs(final_dir, exist_ok=True)

        with open(final_path, 'wb') as target_file:
            for i in range(total_chunks):
                chunk_path = os.path.join(temp_dir, str(i))
                if not os.path.exists(chunk_path):
                    return f"碎片 {i} 缺失，合并失败", 400
                
                with open(chunk_path, 'rb') as source_file:
                    shutil.copyfileobj(source_file, target_file)

                os.remove(chunk_path)
        
        os.rmdir(temp_dir)
        log_request("MERGE_SUCCESS", f"file: {filename}")
        return "合并成功", 200
    
    except Exception as e:
        log_request("MERGE_FAILED", str(e))
        return f"合并出错: {str(e)}", 500

@app.route('/download/<path:subpath>')
def download(subpath):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    real_path = os.path.join(STORAGE_DIR, subpath)

    if not os.path.isfile(real_path):
        return "文件不存在", 403
    
    log_request("DOWNLOAD", f"path: {real_path}")
    return send_from_directory(STORAGE_DIR, subpath, as_attachment = True)

@app.route('/delete/<path:subpath>')
def delete(subpath):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if not subpath or subpath.strip() == "":
        return "禁止删除根目录", 403
    
    real_path = os.path.join(STORAGE_DIR,subpath)

    if not is_save_path(real_path, STORAGE_DIR):
        return "非法路径", 403
    
    try:
        if os.path.isdir(real_path):
            shutil.rmtree(real_path) # 递归删除文件夹
            log_request("DELETE_DIR", f"path: {subpath}")
        elif os.path.isfile(real_path):
            os.remove(real_path)
            log_request("DELETE_FILE", f"path: {subpath}")
        else:
            return "目标不存在", 404
        
        parent_dir = os.path.dirname(subpath)
        return redirect(url_for('view', subpath=parent_dir))
    except Exception as e:
        return f"删除失败: {str(e)}", 500


@app.errorhandler(404)
def page_not_found(e):
    log_request("404_NOT_FOUND", f"访问了不存在的路径: {request.path}")
    return "404NotFound", 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return "文件过大(最大上传 1GB, 由于 Cloudflared 的限制实际可能只能上传 100MB)", 413


os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

if __name__ == '__main__':
    schedule_cleanup()

    allow_lan = CONFIG.get('ALLOW_LAN', False)
    host_ip = '0.0.0.0' if allow_lan else '127.0.0.1'

    port = CONFIG.get('PORT', 8080)

    app.run(host=host_ip, port=port)