/** Cliente HTTP del backend. Todos los errores se convierten en `ErrorApi` con mensaje legible. */

export type Estado = 'Exitosa' | 'Sin información suficiente' | 'Bloqueada por seguridad';

export interface Fuente {
  documento: string;
  archivo: string;
  seccion: string;
  puntaje: number;
  extracto?: string;
}

export interface RespuestaConsulta {
  id: number;
  respuesta: string;
  fuentes: Fuente[];
  estado: Estado;
  fecha_hora: string;
  latencia_ms: number;
  modo: string;
}

export interface RegistroHistorial {
  id: number;
  pregunta: string;
  fecha_hora: string;
  respuesta: string;
  fuentes: Fuente[];
  estado: Estado;
  latencia_ms: number;
}

export class ErrorApi extends Error {
  constructor(
    mensaje: string,
    public readonly codigo: string,
    public readonly status: number,
  ) {
    super(mensaje);
    this.name = 'ErrorApi';
  }
}

const BASE = (import.meta.env?.VITE_API_URL as string | undefined) ?? '';
/** Tiempo máximo de una petición (RF-U12): con LLM una respuesta tarda pocos segundos; 45 s es un fallo. */
export const TIEMPO_MAXIMO_MS = 45_000;
const MENSAJE_INVALIDA = 'La respuesta del servidor no es válida. Intenta de nuevo.';

async function solicitar<T>(ruta: string, init?: RequestInit, esValida?: (datos: unknown) => boolean): Promise<T> {
  const controlador = new AbortController();
  const temporizador = setTimeout(() => controlador.abort(), TIEMPO_MAXIMO_MS);
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, { ...init, signal: controlador.signal });
  } catch {
    if (controlador.signal.aborted) {
      throw new ErrorApi(
        'El servidor tardó demasiado en responder. Intenta de nuevo en unos segundos.',
        'TIEMPO_AGOTADO',
        0,
      );
    }
    throw new ErrorApi(
      'No se pudo conectar con el servidor. Verifica que el backend esté en ejecución.',
      'SIN_CONEXION',
      0,
    );
  } finally {
    clearTimeout(temporizador);
  }
  let datos: unknown = null;
  let esJson = true;
  try {
    datos = await respuesta.json();
  } catch {
    esJson = false;
  }
  if (!respuesta.ok) {
    const cuerpo = datos as { error?: unknown; codigo?: unknown } | null;
    const mensaje =
      typeof cuerpo?.error === 'string' ? cuerpo.error : `El servidor respondió con error ${respuesta.status}.`;
    throw new ErrorApi(mensaje, typeof cuerpo?.codigo === 'string' ? cuerpo.codigo : 'ERROR', respuesta.status);
  }
  if (!esJson || (esValida && !esValida(datos))) {
    throw new ErrorApi(MENSAJE_INVALIDA, 'RESPUESTA_INVALIDA', respuesta.status);
  }
  return datos as T;
}

const esObjeto = (datos: unknown): datos is Record<string, unknown> => typeof datos === 'object' && datos !== null;

/** Forma mínima que la interfaz necesita para pintar una respuesta sin romperse. */
export function esRespuestaConsulta(datos: unknown): datos is RespuestaConsulta {
  return (
    esObjeto(datos) &&
    typeof datos.respuesta === 'string' &&
    typeof datos.estado === 'string' &&
    Array.isArray(datos.fuentes) &&
    datos.fuentes.every((f) => esObjeto(f) && typeof f.documento === 'string' && typeof f.seccion === 'string')
  );
}

/** `contexto`: preguntas anteriores de la conversación (opcional); sin él se envía solo `{ pregunta }`. */
export function consultar(pregunta: string, contexto: string[] = []): Promise<RespuestaConsulta> {
  return solicitar<RespuestaConsulta>(
    '/api/consultar',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(contexto.length ? { pregunta, contexto } : { pregunta }),
    },
    esRespuestaConsulta,
  );
}

export async function obtenerHistorial(limite = 10): Promise<RegistroHistorial[]> {
  const datos = await solicitar<{ consultas: RegistroHistorial[] }>(
    `/api/historial?limite=${limite}`,
    undefined,
    (d) => esObjeto(d) && Array.isArray(d.consultas),
  );
  return datos.consultas;
}

/** Cuota informada por el proveedor en su última respuesta (`null` = desconocido). */
export interface CuotaLlm {
  solicitudes_limite: number | null;
  solicitudes_restantes: number | null;
  solicitudes_reinicio_s: number | null;
  tokens_limite: number | null;
  tokens_restantes: number | null;
  tokens_reinicio_s: number | null;
  actualizado: string;
}

export interface EstadoLlm {
  proveedor: string | null;
  modelo: string | null;
  activo: boolean;
  modo: string;
  llamadas: number;
  cuota: CuotaLlm | null;
}

export function esEstadoLlm(datos: unknown): datos is EstadoLlm {
  const estado = datos as Partial<EstadoLlm> | null;
  return !!estado && typeof estado.activo === 'boolean' && 'proveedor' in estado;
}

export function obtenerEstadoLlm(): Promise<EstadoLlm> {
  return solicitar<EstadoLlm>('/api/llm');
}

export function cambiarModoLlm(activo: boolean): Promise<EstadoLlm> {
  return solicitar<EstadoLlm>('/api/llm', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ activo }),
  });
}
