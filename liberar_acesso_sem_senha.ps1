# ============================================================================
# J.A.R.V.I.S. - Liberar Credenciais de Rede para o PC Principal (192.168.100.142)
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"

# 1. Elevacao para Administrador
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs -Wait
    exit
}

$log = "C:\Backup-PC-Principal\status_credenciais.log"
"Configurando usuarios e acesso de rede em $(Get-Date)" | Out-File $log -Encoding utf8

# 2. Criar usuarios locais dedicados: 'backup' e 'Thiag' com senha 'jarvis'
$users = @("backup", "Thiag")
foreach ($u in $users) {
    $exists = Get-LocalUser -Name $u -ErrorAction SilentlyContinue
    if (-not $exists) {
        net user $u jarvis /add /comment:"Usuario para conexao de Backup" /passwordchg:no | Out-Null
    } else {
        net user $u jarvis | Out-Null
        Enable-LocalUser -Name $u -ErrorAction SilentlyContinue
    }
    wmic useraccount where "Name='$u'" set PasswordExpires=FALSE | Out-Null
}

# 3. Ativar conta Convidado (Guest)
net user Convidado /active:yes | Out-Null
Enable-LocalUser -Name "Convidado" -ErrorAction SilentlyContinue

# 4. Remover conta Convidado do bloqueio de logon pela rede (SeDenyNetworkLogonRight)
$secInf = "$env:TEMP\sec_rights.inf"
$secSdb = "$env:TEMP\sec_rights.sdb"
secedit /export /cfg $secInf /areas USER_RIGHTS | Out-Null
if (Test-Path $secInf) {
    $content = Get-Content $secInf -Raw
    # Remove SID do Guest (*S-1-5-32-546) da lista de negados
    $content = $content -replace "\*S-1-5-32-546,?", ""
    # Adiciona Everyone (*S-1-1-0) e Guest (*S-1-5-32-546) no SeNetworkLogonRight
    if ($content -match "SeNetworkLogonRight\s*=\s*(.*)") {
        $existing = $matches[1].Trim()
        $content = $content -replace "SeNetworkLogonRight\s*=.*", "SeNetworkLogonRight = $existing,*S-1-1-0,*S-1-5-32-546"
    }
    Set-Content -Path $secInf -Value $content -Encoding ascii
    secedit /configure /db $secSdb /cfg $secInf /areas USER_RIGHTS | Out-Null
}

# 5. Politicas do Registro para Acesso Livre na Rede Local
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "LimitBlankPasswordUse" -Value 0 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name "everyoneincludesanonymous" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" -Name "LocalAccountTokenFilterPolicy" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters" -Name "RestrictNullSessAccess" -Value 0 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" -Name "AllowInsecureGuestAuth" -Value 1 -PropertyType DWord -Force | Out-Null

# 6. Conceder Permissoes NTFS Totais para os novos usuarios
$folders = @("C:\Backup-PC-Principal", "$env:USERPROFILE\Desktop\SISTEMA_BACKUP_REDE")
foreach ($f in $folders) {
    if (-not (Test-Path $f)) { New-Item -ItemType Directory -Path $f -Force | Out-Null }
    icacls $f /grant "backup:(OI)(CI)F" /T /C /Q | Out-Null
    icacls $f /grant "Thiag:(OI)(CI)F" /T /C /Q | Out-Null
    icacls $f /grant "Thiago:(OI)(CI)F" /T /C /Q | Out-Null
    icacls $f /grant "*S-1-1-0:(OI)(CI)F" /T /C /Q | Out-Null
    icacls $f /grant "Convidado:(OI)(CI)F" /T /C /Q | Out-Null
}

# 7. Atualizar Permissoes dos Compartilhamentos SMB
$shares = @("Backup", "Backups", "Backup_Projetos", "SISTEMA_BACKUP_REDE")
foreach ($sn in $shares) {
    Grant-SmbShareAccess -Name $sn -AccountName "backup" -AccessRight Full -Force -ErrorAction SilentlyContinue | Out-Null
    Grant-SmbShareAccess -Name $sn -AccountName "Thiag" -AccessRight Full -Force -ErrorAction SilentlyContinue | Out-Null
    Grant-SmbShareAccess -Name $sn -AccountName "Thiago" -AccessRight Full -Force -ErrorAction SilentlyContinue | Out-Null
    Grant-SmbShareAccess -Name $sn -AccountName "Everyone" -AccessRight Full -Force -ErrorAction SilentlyContinue | Out-Null
}

"Credenciais configuradas com sucesso em $(Get-Date)" | Out-File $log -Append -Encoding utf8
