from flask import Flask, request, send_from_directory, session, redirect, url_for, render_template
# from werkzeug.utils import secure_filename
from urllib.parse import quote
from werkzeug.security import check_password_hash
import re
import os
import datetime
import shutil
import json
import time

app = Flask(__name__)

def load_config(): # 获取 config.json 的数据
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = load_config()

app.config['MAX_CONTENT_LENGTH']= CONFIG['MAX_CONTENT_LENTH_MB'] * 1024 * 1024
# 由于 Cloudflared 的限制实际可能只能上传 100MB
app.secret_key = CONFIG['SECRET_KEY']
STORAGE_DIR = CONFIG['STORAGE_DIR'] # 存储网盘文件的文件夹
USER_DB = CONFIG['USER'] # 账号
LOGIN_CD = CONFIG['LOGIN_CD_S']


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

def is_save_path(path):
    return os.path.abspath(path).startswith(os.path.abspath(STORAGE_DIR))

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

    # if not os.path.abspath(real_path).startswith(os.path.abspath(STORAGE_DIR)):
    #     return "非法路径", 403
    if not is_save_path(real_path):
        return "非法路径", 403

    if os.path.isfile(real_path):
        return redirect(url_for('download', subpath = subpath))

    if os.path.isdir(real_path):
        log_request("VIEW", f"path: {subpath}")
        visible_files = os.listdir(real_path)

        visible_files.sort()
        items_data = []

        # if subpath != "":
        #     parent_dir = os.path.dirname(subpath)
        #     back_url = url_for('view', subpath=parent_dir) if parent_dir else url_for('view')
        #     file_links += f'<li>🔙<a href="{back_url}">/..</a></li>'

        for f in visible_files:
            item_path = os.path.join(real_path, f)
            url_path = quote(os.path.join(subpath, f))

            is_dir = os.path.isdir(item_path)
            items_data.append({
                "name": f + ("/" if is_dir else ""),
                "url_path": url_path,
                "icon": "📁" if is_dir else "📄"
            })

            # if os.path.isdir(item_real_path):
            #     icon = "📁"
            #     display_name = f + '/'
            # else:
            #     icon = "📄"
            #     display_name = f
            
            # delete_link = f'''<a href="/delete/{os.path.join(subpath, f)}"
            #                      class="del-btn"
            #                      onclick="return confirm('确定永久删除 {f} 吗?')">
            #                      [delete]
            #                   </a>'''

            # new_path = os.path.join(subpath, f)
            # save_path = quote(new_path)
            # file_links += f'<li>{icon}<a href="/view/{save_path}">{display_name}</a>{delete_link}</li>'

        parent_path = os.path.dirname(subpath)

        # upload_url = url_for('upload', subpath=subpath)
        # mkdir_url = url_for('mkdir', subpath=subpath)
        # return f'''
        #     <link rel="stylesheet" href="/static/style.css">
        #     <h3>当前位置: /{subpath}</h3>
        #     <a href="/logout/">logout</a>
        #     <br><br>
        #     <form action="{upload_url}" method="post" enctype="multipart/form-data">
        #         <input type="file" name="the_file">
        #         <input type="submit" value="上传">
        #     </form>
        #     <form action="{mkdir_url}" method="post">
        #         <input type="text" name="dir" required>
        #         <input type="submit" value="创建文件夹">
        #     </form>
        #     <ul>{file_links}</ul>
        # '''
        return render_template('view.html',
                               subpath=subpath,
                               parent_path=parent_path,
                               items=items_data)
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
    # if not os.path.abspath(real_dir).startswith(os.path.abspath(STORAGE_DIR)):
    #     return "非法路径", 403
    if not is_save_path(real_dir):
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

    # if not os.path.abspath(real_dir).startswith(os.path.abspath(STORAGE_DIR)):
    #     return "非法路径", 403
    if not is_save_path(real_dir):
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
        # if not os.path.abspath(real_dir).startswith(os.path.abspath(STORAGE_DIR)):
        #     return "非法路径", 403
        if not is_save_path(real_dir):
            return "非法路径", 403
        file.save(save_path)
        log_request("UPLOAD", f"save_path: {save_path}")
        return redirect(url_for('view', subpath=subpath))
    return "未选择文件", 400

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

    if not is_save_path(real_path):
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


@app.errorhandler(413)
def request_entity_too_large(error):
    return "文件过大(最大上传 1GB, 由于 Cloudflared 的限制实际可能只能上传 100MB)", 413

if not os.path.exists(STORAGE_DIR): # 如果存储文件夹不存在，则创建
    os.makedirs(STORAGE_DIR)
    log_request("MKDIR", f"dir: {STORAGE_DIR}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)