"""Buchón: vigila publicaciones de organismos fiscales y avisa en Discord.

Uso:
  python buchon.py revisar            baja las fuentes, compara con lo ya visto y deja lo nuevo en pendientes.json
  python buchon.py leer <url|bo:N>    muestra el texto de una norma (o de la página N del Boletín Oficial del día)
  python buchon.py avisar <archivo>   publica en Discord, con @everyone, los avisos urgentes y semiurgentes de un JSON (ver criterio.md)
  python buchon.py decir "<texto>"    publica un mensaje simple
  python buchon.py cerrar             vacía pendientes.json una vez evaluado todo
"""
import difflib
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ESTADO = BASE / "estado"
PAGINAS = ESTADO / "paginas"
VISTOS = ESTADO / "vistos.json"
PENDIENTES = BASE / "pendientes.json"
BO_PDF = ESTADO / "boletin_del_dia.pdf"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9",
}
DOC_EXT = re.compile(r"\.(pdf|xlsx?|docx?|zip|rar|7z|exe|txt|wsdl|xsd|csv)(\?|$)", re.I)
COLORES = {"alto": 0xD93025, "medio": 0xF2A900}
ICONOS = {"alto": "🔴", "medio": "🟡"}
URGENCIA = {"alto": "Urgente", "medio": "Semiurgente"}


# ---------- utilidades ----------

def bajar(url, timeout=40):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError:
        raise
    except OSError:  # corte de red o de DNS: un segundo intento antes de darla por caída
        time.sleep(4)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()


def a_texto(crudo):
    try:
        return crudo.decode("utf-8")
    except UnicodeDecodeError:
        return crudo.decode("cp1252", "replace")


def limpiar(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def html_a_lineas(t, url):
    """Texto visible de una página, una línea por bloque, con los links al lado del texto."""
    t = re.sub(r"<(script|style|noscript|svg|head)\b.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)

    def link(m):
        destino = urllib.parse.urljoin(url, html.unescape(m.group(1) or m.group(2) or m.group(3)))
        destino = re.sub(r"[?&](itok|v|t|_)=[^&#]*", "", destino)
        return f" {limpiar(m.group(4))} [{destino}] "

    def marco(m):
        return f" [{urllib.parse.urljoin(url, html.unescape(m.group(1)))}] "

    t = re.sub(r"\s+", " ", t)  # una etiqueta partida en varios renglones no tiene que quedar como texto
    t = re.sub(r'<iframe\b[^>]*?src="([^"]+)"[^>]*>', marco, t, flags=re.I)  # PDF embebidos
    # el href puede venir con comillas dobles, simples o sin comillas
    t = re.sub(r'''<a\b[^>]*?href=(?:"([^"#][^"]*)"|'([^'#][^']*)'|([^\s>"'#][^\s>]*))[^>]*>(.*?)</a>''', link, t, flags=re.S | re.I)
    # cierres de bloque de HTML y de un feed RSS
    t = re.sub(r"<(br|/p|/div|/li|/tr|/h\d|/td|/section|/article|/item|/title|/link|/description|/pubDate|/lastBuildDate)\b[^>]*>", "\n", t, flags=re.I)
    lineas = []
    for l in t.split("\n"):
        l = limpiar(l)
        if len(l) > 2:
            lineas.append(l)
    return lineas


def json_a_lineas(dato, url, campos=None):
    """Un renglón por ítem de una respuesta JSON, para compararla igual que una página."""
    if isinstance(dato, list):
        return [l for x in dato for l in json_a_lineas(x, url, campos)]
    if not isinstance(dato, dict):
        return [limpiar(str(dato))] if str(dato).strip() else []
    simples, hijos = [], []
    for k, v in dato.items():
        if isinstance(v, str) and v.lstrip()[:1] in ("[", "{"):
            try:
                v = json.loads(v)  # JSON guardado como texto dentro de otro JSON
            except ValueError:
                pass
        if isinstance(v, dict) and set(v) == {"rendered"}:
            v = v["rendered"]  # títulos de WordPress
        if isinstance(v, (list, dict)):
            hijos += json_a_lineas(v, url, campos)
        elif campos and k not in campos:
            continue
        elif isinstance(v, str) and re.search(r"<(p|a|div|li|br|table|h\d)\b", v, re.I):
            hijos += html_a_lineas(v, url)  # HTML guardado dentro del JSON
        elif v not in (None, ""):
            simples.append(f"{k}: {limpiar(str(v))[:400]}")
    return ([" | ".join(simples)] if simples else []) + hijos


def a_lineas(crudo, url, campos=None):
    if crudo.lstrip()[:1] in ("[", "{"):
        try:
            return json_a_lineas(json.loads(crudo), url, campos)
        except ValueError:
            pass
    return html_a_lineas(crudo, url)


def cargar_json(ruta, defecto):
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return defecto


def guardar_json(ruta, dato):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(dato, ensure_ascii=False, indent=1), encoding="utf-8")


def webhook():
    """El webhook sale de la variable de entorno (GitHub) o, si no está, del archivo .env (corrida local)."""
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        # tolera que el secreto se haya cargado copiando el renglón entero del .env
        return os.environ["DISCORD_WEBHOOK_URL"].strip().removeprefix("DISCORD_WEBHOOK_URL=").strip()
    env = BASE / ".env"
    if env.exists():
        for l in env.read_text(encoding="utf-8").splitlines():
            if l.startswith("DISCORD_WEBHOOK_URL="):
                return l.split("=", 1)[1].strip()
    sys.exit("Falta DISCORD_WEBHOOK_URL (variable de entorno o archivo .env)")


def publicar(cuerpo):
    req = urllib.request.Request(
        webhook() + "?wait=true",
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "buchon/0.1"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# ---------- fuentes ----------

def fuente_arca_rg(f, vistos):
    """Novedades de la Biblioteca Electrónica de ARCA: últimas resoluciones generales."""
    t = a_texto(bajar(f["url"]))
    nuevos = []
    for href, num, desc in re.findall(r'<a href="([^"]+)"[^>]*><h2>(.*?)</h2><p>(.*?)</p>', t, flags=re.S):
        clave = limpiar(num)
        if clave in vistos:
            continue
        vistos.append(clave)
        fecha = re.search(r"f:(\d\d/\d\d/\d{4})", href)
        nuevos.append({
            "titulo": clave,
            "detalle": limpiar(desc),
            "fecha": fecha.group(1) if fecha else "",
            "link": urllib.parse.urljoin(f["url"], html.unescape(href)).replace("|", "%7C"),
        })
    return nuevos


def fuente_boletin(f, vistos):
    """Sumario de la primera sección del Boletín Oficial del día (se lee del PDF)."""
    from pypdf import PdfReader

    crudo = bajar(f["url"], timeout=120)
    lector = PdfReader(io.BytesIO(crudo))
    tapa = lector.pages[0].extract_text() or ""
    edicion = re.search(r"N[úu]mero\s+([\d.]+)", tapa)
    edicion = edicion.group(1) if edicion else hashlib.md5(crudo).hexdigest()[:10]
    if edicion in vistos:
        return []
    vistos.append(edicion)
    ESTADO.mkdir(parents=True, exist_ok=True)
    BO_PDF.write_bytes(crudo)
    fecha = re.search(r"(\d{1,2} de \w+ de \d{4})", tapa)

    secciones = re.compile(f["secciones"], re.I)
    organismos = re.compile(f["organismos"], re.I)
    nuevos, seccion, acumulado = [], "", ""
    for n in range(1, min(8, len(lector.pages))):
        texto = lector.pages[n].extract_text() or ""
        if not re.search(r"\.{8,}\s*\d+\s*$", texto, flags=re.M):
            break
        for linea in texto.splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("BOLETÍN OFICIAL N") or linea in ("SUMARIO", "Avisos Nuevos"):
                continue
            fin = re.search(r"\s*\.{5,}\s*(\d+)\s*$", linea)
            if not fin:
                if not acumulado and len(linea) < 45 and not linea.endswith("."):
                    seccion = linea
                else:
                    acumulado += " " + linea
                continue
            entrada = (acumulado + " " + linea[: fin.start()]).strip()
            acumulado = ""
            if entrada and (secciones.search(seccion) or organismos.search(entrada)):
                nuevos.append({
                    "titulo": f"{seccion}: {entrada[:140]}",
                    "detalle": entrada,
                    "fecha": fecha.group(1) if fecha else "",
                    "link": f["url"],
                    "leer": f"bo:{fin.group(1)}",
                })
    return nuevos


def fuente_pagina(f, vistos):
    """Página que se compara contra la foto anterior: avisa líneas y documentos que cambian."""
    url = f["url"]
    lineas = a_lineas(a_texto(bajar(url)), url, f.get("campos"))
    foto = PAGINAS / f"{f['id']}.txt"
    anterior = foto.read_text(encoding="utf-8").splitlines() if foto.exists() else None
    previos = {l.split(" | ")[0]: l for l in anterior or [] if l.startswith("DOCUMENTO ")}

    docs = list(f.get("documentos", []))  # documentos que la página no enlaza pero hay que vigilar igual
    for l in lineas:
        for d in re.findall(r"\[(https?://[^\]]+)\]", l):
            # en Google Drive la página de vista no dice nada; la de descarga da nombre, tamaño y fecha
            drive = re.match(r"https://drive\.google\.com/file/d/([\w-]+)", d)
            if drive:
                d = f"https://drive.google.com/uc?export=download&id={drive.group(1)}"
            if (drive or DOC_EXT.search(d)) and d not in docs:
                docs.append(d)

    def cabecera(d):
        try:
            req = urllib.request.Request(urllib.parse.quote(d, safe=":/?&=%#"), headers=HEADERS, method="HEAD")
            with urllib.request.urlopen(req, timeout=20) as r:
                if not r.headers.get("Content-Length"):
                    return None  # respuesta armada en el momento: su fecha es la de ahora y daría falsa alarma
                nombre = re.search(r'filename="([^"]+)"', r.headers.get("Content-Disposition", ""))
                nombre = f" | archivo {nombre.group(1)}" if nombre else ""
                # solo el día: los servidores espejo de un mismo sitio difieren en minutos y eso no es un cambio
                try:
                    fecha = parsedate_to_datetime(r.headers["Last-Modified"]).strftime("%d/%m/%Y")
                except Exception:
                    fecha = "?"
                return f"DOCUMENTO {d}{nombre} | tamaño {r.headers['Content-Length']} | modificado {fecha}"
        except Exception:
            return previos.get(f"DOCUMENTO {d}")  # un documento que no responde hoy no cuenta como cambio

    if f.get("sin_documentos"):
        docs = []  # páginas con cientos de archivos que se renuevan todos los meses
    with ThreadPoolExecutor(8) as pool:
        lineas += [c for c in pool.map(cabecera, docs[:250]) if c]

    ignorar = re.compile(f["ignorar"], re.I) if f.get("ignorar") else None
    if ignorar:
        lineas = [l for l in lineas if not ignorar.search(l)]

    PAGINAS.mkdir(parents=True, exist_ok=True)
    foto.write_text("\n".join(lineas), encoding="utf-8")
    if anterior is None:
        return []  # primera vez: solo se guarda la foto
    agregadas = [l[2:] for l in difflib.ndiff(anterior, lineas) if l.startswith("+ ")]
    quitadas = [l[2:] for l in difflib.ndiff(anterior, lineas) if l.startswith("- ")]
    if not agregadas and not quitadas:
        return []
    return [{
        "titulo": f"Cambió la página: {f['nombre']}",
        "detalle": "Comparar lo agregado con lo quitado: si cambia una versión, un nombre de archivo, un tamaño o una fecha de un documento técnico, es un cambio real.",
        "agregado": agregadas[:60],
        "quitado": quitadas[:60],
        "fecha": datetime.now().strftime("%d/%m/%Y"),
        "link": url,
    }]


def fuente_boletin_caba(f, vistos):
    """Boletín Oficial de la Ciudad por su API: leyes y normas de AGIP. Recupera las ediciones que se hayan salteado."""
    filtro = re.compile(f["filtro"], re.I)

    def edicion(cual):
        return json.loads(a_texto(bajar(f"{f['url']}/{cual}/true", timeout=90)))

    def normas(nodo, ruta=()):
        if isinstance(nodo, list):
            for n in nodo:
                if isinstance(n, dict) and "id_norma" in n:
                    yield ruta, n
        elif isinstance(nodo, dict):
            for k, v in nodo.items():
                yield from normas(v, ruta + (k,))

    hoy = edicion(0)
    ultimo = int(hoy["boletin"]["numero"])
    desde = max(int(vistos[-1]) + 1, ultimo - 9) if vistos else ultimo
    nuevos = []
    for numero in range(desde, ultimo + 1):
        try:
            dato = hoy if numero == ultimo else edicion(numero)
        except Exception:
            continue  # número sin boletín
        for ruta, n in normas(dato["normas"]["normas"]):
            if "Ley" in ruta or filtro.search(n.get("nombre", "")):
                nuevos.append({
                    "titulo": n.get("nombre", ""),
                    "detalle": limpiar(n.get("sumario", "")),
                    "fecha": dato["boletin"].get("fecha_publicacion", ""),
                    "link": n.get("url_norma", "").replace("http://", "https://"),
                })
    vistos.append(str(ultimo))
    return nuevos


TIPOS = {"arca_rg": fuente_arca_rg, "boletin": fuente_boletin, "boletin_caba": fuente_boletin_caba, "pagina": fuente_pagina}


# ---------- comandos ----------

def revisar():
    fuentes = json.loads((BASE / "fuentes.json").read_text(encoding="utf-8"))
    estado = cargar_json(VISTOS, {"vistos": {}, "fallas": {}})
    pendientes = cargar_json(PENDIENTES, [])
    nuevos, errores = 0, []
    for f in fuentes:
        estado["vistos"].setdefault(f["id"], [])

    def una(f):
        try:
            return f, TIPOS[f["tipo"]](f, estado["vistos"][f["id"]]), None
        except Exception as e:
            return f, [], e

    with ThreadPoolExecutor(5) as pool:  # varias fuentes a la vez para que la corrida no pase de un minuto
        resultados = list(pool.map(una, fuentes))
    for f, items, error in resultados:
        if error is not None:
            n = estado["fallas"].get(f["id"], 0) + 1
            estado["fallas"][f["id"]] = n
            errores.append({"fuente": f["nombre"], "error": repr(error)[:200], "fallas_seguidas": n})
            continue
        estado["fallas"][f["id"]] = 0
        del estado["vistos"][f["id"]][:-400]
        for it in items:
            it.update(fuente=f["nombre"], organismo=f["organismo"])
            pendientes.append(it)
            nuevos += 1
    guardar_json(VISTOS, estado)
    guardar_json(PENDIENTES, pendientes)
    resumen = {}
    if (ESTADO / "modo_prueba").exists():
        resumen["modo_prueba"] = ("Hay un simulacro en curso. Las novedades marcadas como simulacro se evalúan igual que si fueran reales; "
                                  "los avisos salen marcados como prueba y no quedan registrados.")
    print(json.dumps(resumen | {
        "fuentes_revisadas": len(fuentes) - len(errores),
        "novedades_de_esta_corrida": nuevos,
        "pendientes_en_total": len(pendientes),
        "errores": errores,
    }, ensure_ascii=False, indent=1))


def leer(destino, maximo=14000):
    if destino.startswith("bo:"):
        from pypdf import PdfReader

        pagina = int(destino[3:])
        lector = PdfReader(str(BO_PDF))
        texto = "\n".join(lector.pages[n].extract_text() or "" for n in range(pagina - 1, min(pagina + 3, len(lector.pages))))
    else:
        crudo = bajar(urllib.parse.quote(destino, safe=":/?&=%#|"), timeout=90)
        if crudo[:5] == b"%PDF-":
            from pypdf import PdfReader

            texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(crudo)).pages[:12])
        else:
            texto = "\n".join(a_lineas(a_texto(crudo), destino))
    print(texto[:maximo])


def avisar(archivo):
    """Publica solo lo urgente (alto) y lo semiurgente (medio), con @everyone. Lo de impacto bajo se guarda sin publicar."""
    avisos = json.loads(Path(archivo).read_text(encoding="utf-8"))
    prueba = (ESTADO / "modo_prueba").exists()  # con este archivo los avisos salen marcados como prueba y no quedan registrados
    hoy = datetime.now().strftime("%d/%m/%Y")
    publicados, callados, menciones = [], [], 0
    for a in avisos:
        impacto = a.get("impacto")
        if impacto not in URGENCIA:
            callados.append({"fecha": hoy, "titulo": a.get("titulo", ""), "impacto": impacto or "sin dato",
                             "resumen": a.get("resumen", ""), "link": a.get("link", "")})
            continue
        campos = [
            {"name": "Qué hay que tocar", "value": a.get("modulo", "A confirmar")[:1000], "inline": False},
            {"name": "Urgencia", "value": URGENCIA[impacto], "inline": True},
            {"name": "Rige desde", "value": a.get("vigencia", "No lo dice")[:200], "inline": True},
            {"name": "Organismo", "value": a.get("organismo", "")[:200] or "-", "inline": True},
        ]
        respuesta = publicar({
            "content": f"@everyone {a.get('frase', '')}"[:1900],
            "allowed_mentions": {"parse": ["everyone"]},
            "embeds": [{
                "title": f"{ICONOS[impacto]} {'[PRUEBA] ' if prueba else ''}{a['titulo']}"[:250],
                "url": a.get("link") if str(a.get("link", "")).startswith("http") else None,
                "description": a.get("resumen", "")[:3500],
                "color": COLORES[impacto],
                "fields": campos,
            }],
        })
        publicados.append({"fecha": hoy, "titulo": a["titulo"], "link": a.get("link", "")})
        menciones += bool(respuesta.get("mention_everyone"))
    if not prueba:
        # registro de lo ya avisado, para no repetir una norma que llega por dos fuentes
        guardar_json(ESTADO / "avisados.json", (cargar_json(ESTADO / "avisados.json", []) + publicados)[-300:])
        guardar_json(ESTADO / "no_publicados.json", (cargar_json(ESTADO / "no_publicados.json", []) + callados)[-300:])
    print(f"{len(publicados)} avisos publicados ({menciones} con la mención a todos confirmada por Discord); {len(callados)} de impacto bajo guardados sin publicar"
          + (" (modo prueba)" if prueba else ""))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "revisar":
        revisar()
    elif cmd == "leer" and len(sys.argv) > 2:
        leer(sys.argv[2])
    elif cmd == "avisar" and len(sys.argv) > 2:
        avisar(sys.argv[2])
    elif cmd == "decir" and len(sys.argv) > 2:
        print("publicado", publicar({"content": sys.argv[2][:1900]}).get("id"))
    elif cmd == "cerrar":
        guardar_json(PENDIENTES, [])
        print("pendientes en cero")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
