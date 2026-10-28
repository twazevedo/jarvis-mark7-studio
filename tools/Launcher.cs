using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;

class JarvisLauncher {
    static string ResolveRoot() {
        string here = AppDomain.CurrentDomain.BaseDirectory;
        if (File.Exists(Path.Combine(here, "server.py"))) return here;
        string fallback = @"C:\Users\Thiago\.gemini\antigravity\scratch\jarvis";
        if (File.Exists(Path.Combine(fallback, "server.py"))) return fallback;
        return here;
    }
    static string Root = ResolveRoot();

    [STAThread]
    static int Main(string[] args) {
        string forcedProfile = Environment.GetEnvironmentVariable("JARVIS_LAUNCH_PROFILE") ?? "";
#if FORCE_PRO
        forcedProfile = "pro";
#elif FORCE_LITE
        forcedProfile = "lite";
#endif
        if (args.Length > 0 && (args[0] == "pro" || args[0] == "lite")) {
            forcedProfile = args[0];
        }
        string profile = !string.IsNullOrEmpty(forcedProfile) ? forcedProfile : (HasNvidia() ? "pro" : "lite");
        Environment.SetEnvironmentVariable("JARVIS_PROFILE", profile);

        // Verifica se precisa rodar o setup pela primeira vez neste PC
        string venvPy = Path.Combine(Root, ".venv", "Scripts", "python.exe");
        bool needsSetup = !File.Exists(venvPy)
            || (profile == "pro" && !Directory.Exists(Path.Combine(Root, "ComfyUI")))
            || (profile == "lite" && !File.Exists(Path.Combine(Root, "tools", "sd", "sd-cli.exe")));

        if (needsSetup) {
            var ans = MessageBox.Show(
                "J.A.R.V.I.S. detectou que os componentes do perfil [" + profile.ToUpper() + "] ainda não foram instalados neste PC.\n\n" +
                "Deseja instalar e baixar todos os modelos automaticamente agora?",
                "J.A.R.V.I.S. — Instalação Inicial (" + profile.ToUpper() + ")",
                MessageBoxButtons.YesNo, MessageBoxIcon.Information);
            if (ans != DialogResult.Yes) return 0;

            var setup = Process.Start(new ProcessStartInfo {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(Root, "setup.ps1") + "\" -Profile " + profile,
                WorkingDirectory = Root,
                UseShellExecute = true
            });
            setup.WaitForExit();
        }

        // 1) Garante que o Ollama esteja rodando
        EnsureOllama();

        // 2) Se for PRO, garante que o ComfyUI esteja rodando
        if (profile == "pro") {
            EnsureComfyUI();
        }

        // 3) Garante que o servidor do Jarvis v4.5 esteja rodando na porta 8766
        string statusJson = HttpGet("http://127.0.0.1:8766/api/status", 800);
        if (statusJson != null && !statusJson.Contains("\"4.5\"")) {
            HttpPost("http://127.0.0.1:8766/api/shutdown", 600);
            Thread.Sleep(500);
            statusJson = null;
        }

        if (statusJson == null) {
            string py = File.Exists(venvPy) ? venvPy : "python.exe";
            var psi = new ProcessStartInfo {
                FileName = py,
                Arguments = "\"" + Path.Combine(Root, "server.py") + "\"",
                WorkingDirectory = Root,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            psi.EnvironmentVariables["JARVIS_PROFILE"] = profile;
            Process.Start(psi);

            for (int i = 0; i < 25; i++) {
                if (HttpGet("http://127.0.0.1:8766/api/status", 500) != null) break;
                Thread.Sleep(300);
            }
        }

        // 4) Abre o HUD estilo janela de aplicativo nativa (Edge/Chrome --app)
        OpenHudWindow("http://127.0.0.1:8766");
        return 0;
    }

    static bool HasNvidia() {
        try {
            var p = Process.Start(new ProcessStartInfo {
                FileName = "nvidia-smi",
                CreateNoWindow = true,
                UseShellExecute = false
            });
            p.WaitForExit(1500);
            return p.ExitCode == 0;
        } catch { return false; }
    }

    static void EnsureOllama() {
        if (HttpGet("http://127.0.0.1:11434/api/tags", 700) != null) return;
        string localOllama = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs", "Ollama", "ollama.exe");
        string exe = File.Exists(localOllama) ? localOllama : "ollama";
        try {
            Process.Start(new ProcessStartInfo {
                FileName = exe,
                Arguments = "serve",
                CreateNoWindow = true,
                UseShellExecute = false
            });
        } catch { }
    }

    static void EnsureComfyUI() {
        if (HttpGet("http://127.0.0.1:8188/system_stats", 700) != null) return;
        string comfyPy = Path.Combine(Root, "ComfyUI", "venv", "Scripts", "python.exe");
        string comfyDir = Path.Combine(Root, "ComfyUI");
        if (!File.Exists(comfyPy)) return;
        try {
            Process.Start(new ProcessStartInfo {
                FileName = comfyPy,
                Arguments = "main.py --lowvram --listen 127.0.0.1 --port 8188",
                WorkingDirectory = comfyDir,
                WindowStyle = ProcessWindowStyle.Minimized,
                UseShellExecute = true
            });
        } catch { }
    }

    static string HttpGet(string url, int timeoutMs) {
        try {
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.Timeout = timeoutMs;
            using (var resp = (HttpWebResponse)req.GetResponse())
            using (var sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8)) {
                return sr.ReadToEnd();
            }
        } catch { return null; }
    }

    static void HttpPost(string url, int timeoutMs) {
        try {
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.Method = "POST";
            req.Timeout = timeoutMs;
            req.ContentType = "application/json";
            byte[] b = Encoding.UTF8.GetBytes("{}");
            req.ContentLength = b.Length;
            using (var s = req.GetRequestStream()) s.Write(b, 0, b.Length);
            using (var resp = req.GetResponse()) { }
        } catch { }
    }

    static void OpenHudWindow(string url) {
        string[] browsers = new string[] {
            @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            @"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            @"C:\Program Files\Google\Chrome\Application\chrome.exe",
            @"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        };
        foreach (var b in browsers) {
            if (File.Exists(b)) {
                Process.Start(new ProcessStartInfo {
                    FileName = b,
                    Arguments = "--app=" + url + " --window-size=1380,850 --autoplay-policy=no-user-gesture-required --use-fake-ui-for-media-stream",
                    UseShellExecute = true
                });
                return;
            }
        }
        Process.Start(new ProcessStartInfo { FileName = url, UseShellExecute = true });
    }
}
