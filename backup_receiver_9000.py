"""Servidor Receptor de Backup HTTP na porta 9000.
Recebe os arquivos .zip enviados do PC Principal (192.168.100.142) e salva direto na Área de Trabalho e em C:\\Backup-PC-Principal.
Sem pedir usuário nem senha!
"""
import json
import os
import shutil
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DESKTOP = Path(os.environ.get("USERPROFILE", "C:/Users/Thiago")) / "Desktop"
BACKUP_DIR = Path("C:/Backup-PC-Principal")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
DESKTOP.mkdir(parents=True, exist_ok=True)

PORT = 9000

class BackupHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[RECEPTOR 9000] {self.address_string()} - {format % args}")

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        resp = {
            "status": "online",
            "server": "J.A.R.V.I.S. Backup Receiver v1.0",
            "destination_desktop": str(DESKTOP),
            "destination_folder": str(BACKUP_DIR),
            "port": PORT
        }
        self.wfile.write(json.dumps(resp, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_POST(self):
        try:
            cl = int(self.headers.get("Content-Length", 0))
            dt = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backup_projetos_{dt}.zip"
            dest_desktop = DESKTOP / filename
            dest_backup = BACKUP_DIR / filename

            print(f"[*] Recebendo backup de {self.client_address[0]} ({cl / (1024*1024):.2f} MB)...")

            with open(dest_desktop, "wb") as f:
                if cl > 0:
                    remaining = cl
                    while remaining > 0:
                        chunk = self.rfile.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)
                else:
                    while True:
                        chunk = self.rfile.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)

            # Copia uma duplicata segura para C:\Backup-PC-Principal
            try:
                shutil.copy2(dest_desktop, dest_backup)
            except Exception:
                pass

            file_size_mb = dest_desktop.stat().st_size / (1024 * 1024)
            print(f"[OK] Backup recebido e salvo com sucesso em: {dest_desktop} ({file_size_mb:.2f} MB)")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            resp = {
                "status": "ok",
                "message": "Backup recebido com sucesso!",
                "file": filename,
                "size_mb": round(file_size_mb, 2),
                "saved_to": str(dest_desktop)
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            print(f"[ERRO] Falha ao receber backup: {e}")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))

def run():
    server = HTTPServer(("0.0.0.0", PORT), BackupHandler)
    print(f"============================================================")
    print(f" J.A.R.V.I.S. RECEPTOR DE BACKUP ONLINE NA PORTA {PORT}")
    print(f" Salvando automaticamente em: {DESKTOP}")
    print(f" URL: http://0.0.0.0:{PORT}/ (LAN: http://192.168.100.63:{PORT}/)")
    print(f"============================================================")
    server.serve_forever()

if __name__ == "__main__":
    run()
