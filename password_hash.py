from werkzeug.security import generate_password_hash

# 把 'your_password' 换成你真正的强密码
hash_val = generate_password_hash('your_password')
print(hash_val) # 将整段内容复制到 config.json 中