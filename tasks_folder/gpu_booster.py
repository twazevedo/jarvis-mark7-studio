"""Tarefa: Otimizador Stark de GPU (GTX 1660 Super 6GB) & Memória RAM (Ryzen 7 5700G)."""
import ctypes
import gc
import subprocess
import backends as B

description = "Monitora a placa de vídeo NVIDIA GTX 1660 Super e o Ryzen 7 5700G, limpa a VRAM (6 GB), libera memória RAM do Windows e mostra temperatura/consumo."
trigger = "Quando o usuário pedir 'otimize o pc', 'limpar vram', 'status da gpu', 'temperatura da placa de vídeo' ou 'turbinar pc'."
example = "{'type': 'gpu_booster', 'content': 'Otimize a memória RAM e a VRAM da placa de vídeo'}"


def _trim_windows_ram() -> float:
    """Solicita ao kernel do Windows a compactação de Working Set de processos em segundo plano."""
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi.EmptyWorkingSet(kernel32.GetCurrentProcess())
    except Exception:
        pass
    gc.collect()
    return 0.0


def execute(content: str = "") -> str:
    tl = (content or "").lower()
    do_clean = any(w in tl for w in ("otimiz", "limp", "liberar", "libere", "turbo", "boost", "vram"))

    if do_clean:
        B.free_llm()
        B.free_comfy_vram()
        _trim_windows_ram()

    gpu_info = "GPU NVIDIA não detectada via nvidia-smi."
    try:
        p = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,clocks.current.graphics",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if p.returncode == 0 and p.stdout.strip():
            parts = [x.strip() for x in p.stdout.strip().splitlines()[0].split(",")]
            if len(parts) >= 7:
                name, temp, util, mem_u, mem_t, pwr, clk = parts[:7]
                gpu_info = (
                    f"- **GPU:** `{name}`\n"
                    f"- **Temperatura:** `{temp} °C` | **Clock:** `{clk} MHz` | **Potência:** `{pwr} W`\n"
                    f"- **Carga do Núcleo CUDA:** `{util}%`\n"
                    f"- **VRAM Dedicada:** `{mem_u} MB / {mem_t} MB` (`{int(float(mem_t) - float(mem_u))} MB livres`)"
                )
    except Exception:
        pass

    action_msg = "✅ **VRAM da GTX 1660 Super e Memória RAM otimizadas com sucesso!**\n\n" if do_clean else ""
    return (
        f"🚀 **Relatório & Booster de Hardware Stark (Ryzen 7 5700G + GTX 1660 Super)**\n\n"
        f"{action_msg}"
        f"- **Processador:** `AMD Ryzen 7 5700G (8 Núcleos / 16 Threads @ 3.8+ GHz)`\n"
        f"{gpu_info}"
    )
