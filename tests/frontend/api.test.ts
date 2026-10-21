import { afterEach, describe, expect, it, vi } from 'vitest';
import { consultar, ErrorApi, obtenerHistorial } from '../../src/frontend/src/api';

afterEach(() => vi.unstubAllGlobals());

describe('api', () => {
  it('consultar envía la pregunta como JSON y devuelve la respuesta', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ id: 1, respuesta: 'r', fuentes: [], estado: 'Exitosa' }) }));
    vi.stubGlobal('fetch', fetchMock);
    const datos = await consultar('¿Qué es PQR?');
    expect(datos.respuesta).toBe('r');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/consultar');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({ pregunta: '¿Qué es PQR?' });
  });

  it('convierte errores HTTP en ErrorApi con el mensaje del backend', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 400, json: async () => ({ error: 'La pregunta no puede estar vacía.', codigo: 'PREGUNTA_VACIA' }) })));
    await expect(consultar('')).rejects.toMatchObject({ name: 'ErrorApi', codigo: 'PREGUNTA_VACIA', status: 400, message: 'La pregunta no puede estar vacía.' });
  });

  it('convierte fallos de red en ErrorApi SIN_CONEXION', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    await expect(consultar('x')).rejects.toBeInstanceOf(ErrorApi);
    await expect(consultar('x')).rejects.toMatchObject({ codigo: 'SIN_CONEXION' });
  });

  it('obtenerHistorial devuelve la lista de consultas', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ consultas: [{ id: 1 }] }) })));
    expect(await obtenerHistorial(5)).toEqual([{ id: 1 }]);
  });
});
