"""Motor de Pesquisa Inteligente (RAG) do J.A.R.V.I.S. — DuckDuckGo + Wikipédia PT-BR em paralelo, sem chave de API."""
import html
import json
import re
import threading
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def _clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _wiki_search(query: str, timeout: int = 5) -> list[dict]:
    """Busca resumo enciclopédico verificado na Wikipédia em Português."""
    try:
        q_clean = re.sub(
            r"^(?:jarvis[, ]*)?(?:pesquise|busque|quem [eé]|quem foi|o que [eé]|o que foi|me fale sobre|explique|hist[oó]ria d[eoas])\s+",
            "", query.strip(), flags=re.I
        ).strip(" ?!.,") or query.strip()
        api_url = (
            "https://pt.wikipedia.org/w/api.php?action=query&list=search&srsearch="
            + urllib.parse.quote(q_clean)
            + "&utf8=1&format=json&srlimit=2"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": UA})
        data = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore"))
        items = data.get("query", {}).get("search", [])
        results = []
        for it in items[:2]:
            title = it.get("title", "")
            if not title:
                continue
            sum_url = "https://pt.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"))
            sreq = urllib.request.Request(sum_url, headers={"User-Agent": UA})
            sdata = json.loads(urllib.request.urlopen(sreq, timeout=timeout).read().decode("utf-8", "ignore"))
            extract = (sdata.get("extract") or _clean(it.get("snippet", ""))).strip()
            page_url = sdata.get("content_urls", {}).get("desktop", {}).get("page") or f"https://pt.wikipedia.org/wiki/{urllib.parse.quote(title)}"
            if extract:
                results.append({
                    "title": f"Wikipédia: {title}",
                    "url": page_url,
                    "snippet": extract[:520],
                })
        return results
    except Exception:
        return []


def _ddg_search(query: str, n: int = 5, timeout: int = 8) -> list[dict]:
    """Busca resultados ao vivo no DuckDuckGo Brasil."""
    req = urllib.request.Request(
        "https://html.duckduckgo.com/html/",
        data=urllib.parse.urlencode({"q": query, "kl": "br-pt"}).encode(),
        headers={"User-Agent": UA},
    )
    try:
        page = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    except Exception:
        return []
    out = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=class="result__a"|$)', page, re.S):
        href, title, rest = m.groups()
        href = html.unescape(href)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        url = q["uddg"][0] if "uddg" in q else href
        if url.startswith("//"):
            url = "https:" + url
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
        out.append({"title": _clean(title), "url": url, "snippet": _clean(sn.group(1)) if sn else ""})
        if len(out) >= n:
            break
    return out


def search(query, n=5, timeout=8):
    """Executa busca híbrida em paralelo (Wikipédia PT + DuckDuckGo) e retorna [{'title','url','snippet'}]."""
    wiki_res, ddg_res = [], []

    def run_wiki():
        nonlocal wiki_res
        wiki_res = _wiki_search(query, timeout=min(5, timeout))

    def run_ddg():
        nonlocal ddg_res
        ddg_res = _ddg_search(query, n=n, timeout=timeout)

    t1 = threading.Thread(target=run_wiki, daemon=True)
    t2 = threading.Thread(target=run_ddg, daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=timeout)
    t2.join(timeout=timeout)

    combined = wiki_res + ddg_res
    if not combined:
        raise RuntimeError("Não foi possível obter resultados da web no momento.")
    return combined[: n + 1]


def as_context(results):
    lines = [f"[{i}] {r['title']}: {r['snippet']} ({r['url']})" for i, r in enumerate(results, 1)]
    return (
        "\n\n[DADOS VERIFICADOS EM TEMPO REAL (RAG / WEB) — Use estas informações factuais para fundamentar sua resposta]:\n"
        + "\n".join(lines)
    )
