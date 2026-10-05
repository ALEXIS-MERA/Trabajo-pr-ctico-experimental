import os
import unicodedata

from models import Estudiante
from shared.json_manager import GestorJSON
from shared.herramientas import es_email_valido

CARPETA_DATOS = os.path.join(os.path.dirname(__file__), "data")
gestor = GestorJSON(os.path.join(CARPETA_DATOS, "estudiantes.json"))
RUTA_ULTIMO_ID = os.path.join(CARPETA_DATOS, "ultimo_id.txt")

CAMPOS_ESTUDIANTE = ("nombre", "apellido", "email", "carnet")
CAMPOS_OBLIGATORIOS = ("nombre", "apellido", "email", "carnet")
CAMPOS_BUSCABLES = ("nombre", "apellido", "email", "carnet")

RANGO_NOTA = (0, 20)


def clave(texto):
    letras = unicodedata.normalize("NFD", str(texto).strip().casefold())
    resultado = []
    for caracter in letras:
        if unicodedata.combining(caracter) and not (caracter == "\u0303" and resultado[-1:] == ["n"]):
            continue
        resultado.append(caracter)
    return unicodedata.normalize("NFC", "".join(resultado))


def emails_registrados(excepto_id=None):
    return {
        registro["email"].lower()
        for registro in gestor.leer()
        if registro["id"] != excepto_id
    }


def carnets_registrados(excepto_id=None):
    return {
        registro["carnet"].lower()
        for registro in gestor.leer()
        if registro["id"] != excepto_id
    }


def siguiente_id():
    ids = [registro["id"] for registro in gestor.leer()]
    try:
        with open(RUTA_ULTIMO_ID, "r", encoding="utf-8") as archivo:
            ids.append(int(archivo.read()))
    except (OSError, ValueError):
        pass
    return max(ids) + 1 if ids else 1


def archivo_danado():
    gestor.leer()
    return gestor.danado


def error_al_guardar():
    if gestor.danado:
        return "El archivo de datos está dañado: repárelo antes de guardar (no se modificó nada)"
    return "No se pudo escribir el archivo"


def guardar_ultimo_id(id_usado):
    try:
        with open(RUTA_ULTIMO_ID, "w", encoding="utf-8") as archivo:
            archivo.write(str(id_usado))
    except OSError:
        pass


def crear_estudiante(datos):
    try:
        valores = {campo: str(datos.get(campo, "")).strip() for campo in CAMPOS_ESTUDIANTE}

        faltantes = [campo for campo in CAMPOS_OBLIGATORIOS if not valores[campo]]
        if faltantes:
            return False, f"Faltan campos obligatorios: {', '.join(faltantes)}"

        if not es_email_valido(valores["email"]):
            return False, f"El email '{valores['email']}' no tiene un formato válido"

        if valores["email"].lower() in emails_registrados():
            return False, "Ese email ya está registrado"
        if valores["carnet"].lower() in carnets_registrados():
            return False, f"El carnet {valores['carnet']} ya está registrado"

        estudiante = Estudiante(siguiente_id(), **valores)

        registros = gestor.leer()
        registros.append(estudiante.a_diccionario())
        if not gestor.guardar(registros):
            return False, error_al_guardar()
        guardar_ultimo_id(estudiante.id)

        return True, f"Estudiante {estudiante.obtener_nombre_completo()} creado con id {estudiante.id}"

    except Exception as error:
        return False, f"Error inesperado: {error}"


def obtener_todos():
    return [Estudiante.desde_diccionario(registro) for registro in gestor.leer()]


def obtener_por_id(id_estudiante):
    for estudiante in obtener_todos():
        if estudiante.id == id_estudiante:
            return estudiante
    return None


def buscar_estudiantes(termino):
    termino = clave(termino)
    if not termino:
        return []

    encontrados = []
    for registro in gestor.leer():
        for campo in CAMPOS_BUSCABLES:
            if termino in clave(registro.get(campo, "")):
                encontrados.append(Estudiante.desde_diccionario(registro))
                break
    return encontrados


def actualizar_estudiante(id_estudiante, cambios):
    try:
        desconocidos = set(cambios) - set(CAMPOS_ESTUDIANTE)
        if desconocidos:
            return False, f"Campos no válidos: {', '.join(sorted(desconocidos))}"

        if not cambios:
            return False, "No se indicó ningún cambio"

        cambios = {campo: str(valor).strip() for campo, valor in cambios.items()}

        vacios = [campo for campo in cambios if campo in CAMPOS_OBLIGATORIOS and not cambios[campo]]
        if vacios:
            return False, f"No se pueden dejar vacíos: {', '.join(vacios)}"

        if "email" in cambios:
            if not es_email_valido(cambios["email"]):
                return False, "El email no tiene un formato válido"
            if cambios["email"].lower() in emails_registrados(excepto_id=id_estudiante):
                return False, "Ese email ya lo usa otro estudiante"

        if "carnet" in cambios:
            if cambios["carnet"].lower() in carnets_registrados(excepto_id=id_estudiante):
                return False, f"El carnet {cambios['carnet']} ya lo usa otro estudiante"

        registros = gestor.leer()
        posicion = None
        for indice, registro in enumerate(registros):
            if registro["id"] == id_estudiante:
                posicion = indice
                break

        if posicion is None:
            return False, f"No existe un estudiante con id {id_estudiante}"

        registros[posicion].update(cambios)
        if not gestor.guardar(registros):
            return False, error_al_guardar()
        return True, f"Estudiante {id_estudiante} actualizado ({len(cambios)} campo/s)"

    except Exception as error:
        return False, f"Error inesperado: {error}"


def eliminar_estudiante(id_estudiante):
    registros = gestor.leer()
    quedan = [registro for registro in registros if registro["id"] != id_estudiante]

    if len(quedan) == len(registros):
        return False, f"No existe un estudiante con id {id_estudiante}"

    if not gestor.guardar(quedan):
        return False, error_al_guardar()
    return True, f"Estudiante {id_estudiante} eliminado"


def agregar_nota(id_estudiante, materia, nota):
    try:
        materia = str(materia).strip()
        if not materia:
            return False, "La materia es obligatoria"

        existentes = {clave(m): m for m in materias_ofertadas()}
        materia = existentes.get(clave(materia), materia)

        try:
            nota = float(str(nota).replace(",", "."))
        except (TypeError, ValueError):
            return False, f"La nota '{nota}' no es un número"

        minimo, maximo = RANGO_NOTA
        if not minimo <= nota <= maximo:
            return False, f"La nota debe estar entre {minimo} y {maximo}"
        if nota.is_integer():
            nota = int(nota)

        registros = gestor.leer()
        for indice, registro in enumerate(registros):
            if registro["id"] == id_estudiante:
                estudiante = Estudiante.desde_diccionario(registro)
                estudiante.agregar_nota(materia, nota)
                registros[indice] = estudiante.a_diccionario()
                if not gestor.guardar(registros):
                    return False, error_al_guardar()
                return True, f"Nota {nota} agregada en {materia} a {estudiante.obtener_nombre_completo()}"

        return False, f"No existe un estudiante con id {id_estudiante}"

    except Exception as error:
        return False, f"Error inesperado: {error}"


def materias_ofertadas():
    materias = set()
    for estudiante in obtener_todos():
        materias |= estudiante.materias
    return materias


def estudiantes_en_comun(id_a, id_b):
    if id_a == id_b:
        return False, "Elija dos estudiantes distintos"
    estudiante_a = obtener_por_id(id_a)
    if not estudiante_a:
        return False, f"No existe un estudiante con id {id_a}"
    estudiante_b = obtener_por_id(id_b)
    if not estudiante_b:
        return False, f"No existe un estudiante con id {id_b}"

    return True, estudiante_a.materias_en_comun(estudiante_b)


def estadisticas():
    registros = gestor.leer()
    dominios = {r["email"].split("@")[1].lower() for r in registros if "@" in r["email"]}
    sin_notas = [r["nombre"] for r in registros if not r.get("notas")]

    return {
        "total": len(registros),
        "materias": sorted(materias_ofertadas(), key=clave),
        "dominios": sorted(dominios),
        "sin_notas": sin_notas,
    }
