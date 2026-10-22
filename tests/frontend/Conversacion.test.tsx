import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/frontend/src/App';

type Respuesta = { ok: boolean; status: number; json: () => Promise<unknown> };

const respuestaJson = (status: number, cuerpo: unknown): Respuesta => ({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(cuerpo),
});

const exitosa = (id: number) =>
  respuestaJson(200, {
    id, respuesta: `respuesta ${id}`, fuentes: [], estado: 'Exitosa',
    fecha_hora: '2026-10-22T10:00:00+00:00', latencia_ms: 1, modo: 'extractivo',
  });

/** Registra los cuerpos enviados a /api/consultar; `fallar` devuelve 400 para esa pregunta. */
function simularBackend(fallar: string[] = []) {
  const cuerpos: Array<Record<string, unknown>> = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit): Promise<Respuesta> => {
      if (String(url).includes('/api/consultar')) {
        const cuerpo = JSON.parse(String(init?.body));
        cuerpos.push(cuerpo);
        if (fallar.includes(cuerpo.pregunta)) return respuestaJson(400, { error: 'inválida', codigo: 'X' });
        return exitosa(cuerpos.length);
      }
      return respuestaJson(200, { consultas: [] });
    }),
  );
  return cuerpos;
}

async function preguntar(texto: string) {
  const campo = screen.getByLabelText('Pregunta');
  await userEvent.clear(campo);
  await userEvent.type(campo, texto);
  await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Consultar' })).toBeEnabled());
}

describe('Memoria de conversación', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('la primera consulta envía solo la pregunta y las siguientes el contexto', async () => {
    const cuerpos = simularBackend();
    render(<App />);
    await preguntar('¿Cuál es el monto máximo del Crédito Productivo Impulso?');
    await preguntar('¿Y el más bajo?');
    expect(cuerpos[0]).toEqual({ pregunta: '¿Cuál es el monto máximo del Crédito Productivo Impulso?' });
    expect(cuerpos[1]).toEqual({
      pregunta: '¿Y el más bajo?',
      contexto: ['¿Cuál es el monto máximo del Crédito Productivo Impulso?'],
    });
  });

  it('envía como máximo las 3 preguntas más recientes', async () => {
    const cuerpos = simularBackend();
    render(<App />);
    for (const p of ['p1', 'p2', 'p3', 'p4', 'p5']) await preguntar(p);
    expect(cuerpos[4].contexto).toEqual(['p2', 'p3', 'p4']);
  });

  it('una consulta con error no entra en el contexto', async () => {
    const cuerpos = simularBackend(['mala']);
    render(<App />);
    await preguntar('buena');
    await preguntar('mala');
    await preguntar('¿Y el plazo?');
    expect(cuerpos[2].contexto).toEqual(['buena']);
  });

  it('«Nueva conversación» borra el contexto', async () => {
    const cuerpos = simularBackend();
    render(<App />);
    expect(screen.queryByRole('button', { name: 'Nueva conversación' })).not.toBeInTheDocument();
    await preguntar('¿Cuál es el monto máximo del Crédito Productivo Impulso?');
    const conversacion = screen.getByRole('log', { name: 'Conversación' });
    expect(within(conversacion).getByText('¿Cuál es el monto máximo del Crédito Productivo Impulso?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Nueva conversación' }));
    expect(within(conversacion).queryAllByRole('article', { name: 'Mensaje del asesor' })).toHaveLength(0);
    await preguntar('¿Y el plazo?');
    expect(cuerpos[1]).toEqual({ pregunta: '¿Y el plazo?' });
  });
});
