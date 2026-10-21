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

async function solicitar<T>(ruta: string, init?: RequestInit): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, init);
  } catch {
    throw new ErrorApi(
      'No se pudo conectar con el servidor. Verifica que el backend esté en ejecución.',
      'SIN_CONEXION',
      0,
    );
  }
  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    const mensaje = (datos?.error as string | undefined) ?? `El servidor respondió con error ${respuesta.status}.`;
    throw new ErrorApi(mensaje, (datos?.codigo as string | undefined) ?? 'ERROR', respuesta.status);
  }
  return datos as T;
}

export function consultar(pregunta: string): Promise<RespuestaConsulta> {
  return solicitar<RespuestaConsulta>('/api/consultar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pregunta }),
  });
}

export async function obtenerHistorial(limite = 10): Promise<RegistroHistorial[]> {
  const datos = await solicitar<{ consultas: RegistroHistorial[] }>(`/api/historial?limite=${limite}`);
  return datos.consultas;
}
