import asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from typing import List
import pandas as pd
from pyppeteer import launch

# -----------------------------
# CONFIGURACIÓN
# -----------------------------
CHROME_PATH = r"C:/Program Files/Google/Chrome/Application/chrome.exe"
BROWSER_ARGS = ['--no-sandbox', '--disable-setuid-sandbox']

app = FastAPI(title="API Consulta SUNAT", version="1.0")

# -----------------------------
# FUNCIONES DE CONSULTA
# -----------------------------
async def process_ruc(page, ruc, tipo, serie, numero, fecha, monto):
    """Completa el formulario y devuelve los resultados"""
    try:
        await page.goto('https://ww1.sunat.gob.pe/ol-ti-itconsultaunificadalibre/consultaUnificadaLibre/consulta',
                        timeout=60000)
        await page.waitForSelector('#numRuc', timeout=15000)

        await page.type('#numRuc', ruc)
        await page.select('#codComp', tipo)
        await page.type('#numeroSerie', serie)
        await page.type('#numero', numero)
        await page.type('#fechaEmision', fecha)
        await page.type('#monto', monto)
        await page.click('#btnConsultar')

        await page.waitForSelector('#resEstado', timeout=15000)
        initial_estado = await page.evaluate(
            'document.querySelector("#resEstado").innerText.trim()')  # DE DENTRO AFUERA, CONSIGUE EL VALOR DE resEstado DE SUNAT Y LUEGO SE LA PASA A PHITON QUIEN LA GUARDA EN LA VARIABLE initial_estado
        await page.waitForFunction(
            f'document.querySelector("#resEstado").innerText.trim() !== "{initial_estado}"',
            timeout=15000
        )
        estado = await page.evaluate('document.querySelector("#resEstado").innerText.trim()')
        estado_ruc = await page.evaluate('document.querySelector("#resEstadoRuc").innerText.trim()')
        condicion = await page.evaluate('document.querySelector("#resCondicion").innerText.trim()')

        return {"estado": estado, "estado_ruc": estado_ruc, "condicion": condicion}
    except Exception as e:
        return {"estado": "Sin respuesta", "estado_ruc": "-", "condicion": "-"}


async def main_async(data_list):
    """Ejecuta todas las consultas secuencialmente"""
    browser = await launch(
        headless=True,
        executablePath=CHROME_PATH if Path(CHROME_PATH).exists() else None,
        args=BROWSER_ARGS
    )

    page = await browser.newPage()
    results = []
    for item in data_list:
        ruc, tipo, serie, numero, fecha, monto = item
        try:
            res = await process_ruc(page, ruc, tipo, serie, numero, fecha, monto)
        except Exception:
            res = {"estado": "Error", "estado_ruc": "-", "condicion": "-"}
        res.update({
            "ruc": ruc,
            "tipo": tipo,
            "serie": serie,
            "numero": numero,
            "fecha": fecha,
            "monto": monto
        })
        results.append(res)
        await asyncio.sleep(3)  # pequeña pausa entre consultas
    await browser.close()
    return results

# -----------------------------
# ENDPOINTS DE API
# -----------------------------

@app.post("/consultar_txt/")
async def consultar_desde_txt(file: UploadFile = File(...)):
    """
    Subir un archivo .txt con líneas tipo:
    RUC,Tipo,Serie,Número,Fecha,Monto
    """
    content = (await file.read()).decode("utf-8").strip().splitlines()
    data_list = []
    for line in content:
        try:
            data_list.append([x.strip() for x in line.split(",")])
        except Exception:
            pass

    results = await main_async(data_list)
    return {"cantidad": len(results), "resultados": results}


@app.post("/consultar_json/")
async def consultar_desde_json(data: List[List[str]]):
    """
    Enviar un JSON directamente:
    [
        ["20256211310","03","B021","16916","07-10-2025","29390.00"]
    ]
    """
    results = await main_async(data)
    return {"cantidad": len(results), "resultados": results}
