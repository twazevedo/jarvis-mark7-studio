# ============================================================================
# Receptor de Backup HTTP na porta 9000 (Versao PowerShell Nativa)
# Salva automaticamente na Area de Trabalho e em C:\Backup-PC-Principal
# ============================================================================
netsh advfirewall firewall add rule name="Backup9000" dir=in action=allow protocol=TCP localport=9000 | Out-Null
$l = New-Object System.Net.HttpListener
$l.Prefixes.Add("http://+:9000/")
$l.Start()

Clear-Host
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   RECEPTOR DE BACKUP ONLINE NA PORTA 9000 (SEM SENHA)      " -ForegroundColor Green
Write-Host "   Aguardando envio do PC Principal (192.168.100.142)...    " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

while($true) {
    $ctx = $l.GetContext()
    $dt = Get-Date -Format "yyyyMMdd_HHmmss"
    $desk = [Environment]::GetFolderPath("Desktop")
    $p = "$desk\backup_projetos_$dt.zip"
    $fs = [System.IO.File]::Create($p)
    $ctx.Request.InputStream.CopyTo($fs)
    $fs.Close()

    # Copia para C:\Backup-PC-Principal tambem
    Copy-Item $p "C:\Backup-PC-Principal\" -Force -ErrorAction SilentlyContinue

    Write-Host "[OK] Backup recebido e salvo com sucesso em: $p" -ForegroundColor Green
    $b = [System.Text.Encoding]::UTF8.GetBytes('{"status":"ok","saved_to":"' + $p.Replace('\','\\') + '"}')
    $ctx.Response.ContentType = "application/json"
    $ctx.Response.OutputStream.Write($b, 0, $b.Length)
    $ctx.Response.Close()
}
