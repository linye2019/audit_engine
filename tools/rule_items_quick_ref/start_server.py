#!/usr/bin/env python3
"""
启动本地HTTP服务器，用于访问医保智能审核目录查询页面
运行方式: python3 start_server.py
然后浏览器打开: http://localhost:8080
"""
import http.server
import socketserver
import os
import webbrowser
import threading

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def log_message(self, format, *args):
        # 减少日志输出
        pass

def open_browser():
    """延迟打开浏览器"""
    import time
    time.sleep(1)
    webbrowser.open(f'http://localhost:{PORT}')

if __name__ == '__main__':
    print(f"医保智能审核目录查询")
    print(f"服务地址: http://localhost:{PORT}")
    print(f"按 Ctrl+C 停止服务")
    print()
    
    # 自动打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n服务已停止")
