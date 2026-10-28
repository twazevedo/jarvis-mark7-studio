# ============================================================================
# J.A.R.V.I.S. Mark VII - Aceitar PC Principal (192.168.100.142) & Liberar Firewall
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"
$logFile = "C:\Backup-PC-Principal\status_desbloqueio.txt"
New-Item -ItemType Directory -Path "C:\Backup-PC-Principal" -Force | Out-Null
New-Item -ItemType Directory -Path "$env:USERPROFILE\Desktop\SISTEMA_BACKUP_REDE" -Force | Out-Null

# 1. Auto-elevacao para Administrador (UAC)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs -Wait
    exit
}

"Iniciando desbloqueio em $(Get-Date)" | Out-File $logFile -Encoding utf8

# 2. Mudar rede para Privada (via Cmdlet e via Registro do Windows)
Get-NetConnectionProfile | ForEach-Object {
    Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private
}
Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles" | ForEach-Object {
    Set-ItemProperty -Path $_.PSPath -Name "Category" -Value 1 -Type DWord -Force
}

# 3. Iniciar servicos de rede e descoberta
$services = @("fdPHost", "FDResPub", "SSDPSRV", "upnphost", "LanmanServer", "LanmanWorkstation")
foreach ($svc in $services) {
    Set-Service -Name $svc -StartupType Automatic
    Start-Service -Name $svc
}

# 4. Aceitar TOTALMENTE o PC Principal (192.168.100.142 + IPv6 da tela) e toda a sub-rede 192.168.100.0/24
$pcPrincipalIPs = @(
    "192.168.100.142",
    "192.168.100.0/24",
    "LocalSubnet",
    "fe80::8359:ffb9:d51:465e",
    "2804:90b0:3c2:4200:6b4c:5fb0:ccbe:e25",
    "2804:90b0:3c2:4200:51ee:abdc:ca37:b4e4"
)

Remove-NetFirewallRule -DisplayName "Aceitar_PC_Principal_*" -ErrorAction SilentlyContinue
Remove-NetFirewallRule -DisplayName "Jarvis_Backup_*" -ErrorAction SilentlyContinue

New-NetFirewallRule -DisplayName "Aceitar_PC_Principal_Inbound" `
    -Direction Inbound -Action Allow -Protocol Any `
    -RemoteAddress $pcPrincipalIPs -Profile Any `
    -EdgeTraversalPolicy Allow | Out-Null

New-NetFirewallRule -DisplayName "Aceitar_PC_Principal_Outbound" `
    -Direction Outbound -Action Allow -Protocol Any `
    -RemoteAddress $pcPrincipalIPs -Profile Any | Out-Null

New-NetFirewallRule -DisplayName "Jarvis_Backup_SMB_TCP" `
    -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort 445,139,135,21,22,80,873,3389,5000,5985,5986,8000,8080,8384,8765,8766,9000,9090,11434,22000 -Profile Any | Out-Null

New-NetFirewallRule -DisplayName "Jarvis_Backup_SMB_UDP" `
    -Direction Inbound -Action Allow -Protocol UDP `
    -LocalPort 137,138,1900,3702,5353,21027 -Profile Any | Out-Null

New-NetFirewallRule -DisplayName "Jarvis_Backup_ICMPv4" `
    -Direction Inbound -Action Allow -Protocol ICMPv4 -Profile Any | Out-Null

New-NetFirewallRule -DisplayName "Jarvis_Backup_ICMPv6" `
    -Direction Inbound -Action Allow -Protocol ICMPv6 -Profile Any | Out-Null

netsh advfirewall firewall set rule group="@FirewallAPI.dll,-32752" new enable=Yes | Out-Null
netsh advfirewall firewall set rule group="@FirewallAPI.dll,-28502" new enable=Yes | Out-Null
netsh advfirewall set allprofiles state off | Out-Null

# 5. Ajustar politicas de compartilhamento SMB sem bloqueio de senha/conta diferente (Thiag -> Thiago)
New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" `
    -Name "LocalAccountTokenFilterPolicy" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" `
    -Name "LimitBlankPasswordUse" -Value 0 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" `
    -Name "AllowInsecureGuestAuth" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters" `
    -Name "RestrictNullSessAccess" -Value 0 -PropertyType DWord -Force | Out-Null

Set-SmbServerConfiguration -EnableSMB2Protocol $true -RejectUnencryptedAccess $false -AutoShareServer $true -AutoShareWorkstation $true -Force | Out-Null

$guestName = ([System.Security.Principal.SecurityIdentifier]"S-1-5-32-546").Translate([System.Security.Principal.NTAccount]).Value.Split('\')[-1]
net user $guestName /active:yes | Out-Null

# 6. Permissoes NTFS e Compartilhamentos SMB
$everyone = ([System.Security.Principal.SecurityIdentifier]"S-1-1-0").Translate([System.Security.Principal.NTAccount]).Value
$folders = @("C:\Backup-PC-Principal", "$env:USERPROFILE\Desktop\SISTEMA_BACKUP_REDE")
foreach ($f in $folders) {
    icacls $f /grant "*S-1-1-0:(OI)(CI)F" /T /C /Q | Out-Null
    icacls $f /grant "*S-1-5-7:(OI)(CI)F" /T /C /Q | Out-Null
    icacls $f /grant "${env:USERNAME}:(OI)(CI)F" /T /C /Q | Out-Null
}

$shares = @{
    "Backup"              = "C:\Backup-PC-Principal"
    "Backups"             = "C:\Backup-PC-Principal"
    "Backup_Projetos"     = "C:\Backup-PC-Principal"
    "SISTEMA_BACKUP_REDE" = "$env:USERPROFILE\Desktop\SISTEMA_BACKUP_REDE"
}
foreach ($sName in $shares.Keys) {
    Remove-SmbShare -Name $sName -Force -ErrorAction SilentlyContinue
    New-SmbShare -Name $sName -Path $shares[$sName] -FullAccess $everyone,$env:USERNAME -Description "Backup do PC Principal (192.168.100.142)" | Out-Null
}

"SUCESSO: PC Principal 192.168.100.142 aceito e Firewall liberado em $(Get-Date)" | Out-File $logFile -Append -Encoding utf8
