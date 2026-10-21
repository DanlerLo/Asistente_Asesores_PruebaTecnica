import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/frontend/src/App';

type Respuesta = { ok: boolean; status: number; json: () => Promise<unknown> };

const respuestaJson = (status: number, cuerpo: unknown): Respuesta => ({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(cuerpo),
});

const HISTORIAL_VACIO = respuestaJson(200, { consultas: [] });

function simularFetch(resolver: (url: string, init?: RequestInit) => Promise<Respuesta>) {
  const mock = vi.fn((url: string, init?: RequestInit) => resolver(url, init));
  vi.stubGlobal('fetch', mock);
  return mock;
}

describe('App', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('muestra el formulario de consulta', () => {
    simularFetch(async () => HISTORIAL_VACIO);
    render(<App />);
    expect(screen.getByLabelText('Pregunta')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Consultar' })).toBeInTheDocument();
  });

  it('rechaza una pregunta vacía sin llamar al backend', async () => {
    const fetchMock = simularFetch(async () => HISTORIAL_VACIO);
    render(<App />);
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Escribe una pregunta antes de consultar.');
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/consultar'))).toHaveLength(0);
  });

  it('muestra el estado de procesamiento, la respuesta, el estado y las fuentes', async () => {
    let resolverConsulta: (r: Respuesta) => void = () => {};
    const fetchMock = simularFetch((url) => {
      if (String(url).includes('/api/consultar')) {
        return new Promise<Respuesta>((resolve) => {
          resolverConsulta = resolve;
        });
      }
      return Promise.resolve(HISTORIAL_VACIO);
    });
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), '¿Cuál es el monto máximo del Crédito Productivo Impulso?');
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Procesando la consulta…');
    expect(screen.getByRole('button', { name: 'Consultando…' })).toBeDisabled();

    resolverConsulta(
      respuestaJson(200, {
        id: 7,
        respuesta: 'Según «Productos de Crédito»: Monto máximo: $50.000.000\n\nFuente: Productos de Crédito.md',
        fuentes: [
          { documento: 'Productos de Crédito', archivo: 'Productos de Crédito.md', seccion: 'Crédito Productivo Impulso > Condiciones', puntaje: 1, extracto: 'Monto máximo: $50.000.000' },
        ],
        estado: 'Exitosa',
        fecha_hora: '2026-10-21T12:00:00+00:00',
        latencia_ms: 3,
        modo: 'extractivo',
      }),
    );

    expect(await screen.findByText(/Según «Productos de Crédito»: Monto máximo: \$50\.000\.000/)).toBeInTheDocument();
    expect(screen.getByText('Exitosa')).toBeInTheDocument();
    expect(screen.getByText('Productos de Crédito.md')).toBeInTheDocument();
    expect(screen.getByText(/Crédito Productivo Impulso > Condiciones/)).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();

    const llamada = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/consultar'));
    expect(llamada).toBeDefined();
    expect(JSON.parse(String(llamada![1]?.body))).toEqual({ pregunta: '¿Cuál es el monto máximo del Crédito Productivo Impulso?' });
  });

  it('muestra el estado "Sin información suficiente" y la ausencia de fuentes', async () => {
    simularFetch((url) =>
      Promise.resolve(
        String(url).includes('/api/consultar')
          ? respuestaJson(200, {
              id: 8, respuesta: 'No tengo información suficiente para responder.', fuentes: [],
              estado: 'Sin información suficiente', fecha_hora: '2026-10-21T12:00:00+00:00', latencia_ms: 1, modo: 'extractivo',
            })
          : HISTORIAL_VACIO,
      ),
    );
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), '¿Cuál es la capital de Francia?');
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByText('No tengo información suficiente para responder.')).toBeInTheDocument();
    expect(screen.getByText('Sin información suficiente')).toBeInTheDocument();
    expect(screen.getByText(/Sin fuentes/)).toBeInTheDocument();
  });

  it('muestra el error devuelto por el backend', async () => {
    simularFetch((url) =>
      Promise.resolve(
        String(url).includes('/api/consultar')
          ? respuestaJson(400, { error: 'La pregunta supera el máximo de 1000 caracteres (tiene 1200).', codigo: 'PREGUNTA_DEMASIADO_LARGA' })
          : HISTORIAL_VACIO,
      ),
    );
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), 'pregunta');
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La pregunta supera el máximo de 1000 caracteres');
  });

  it('muestra un error de conexión cuando el backend no responde', async () => {
    simularFetch((url) =>
      String(url).includes('/api/consultar') ? Promise.reject(new TypeError('Failed to fetch')) : Promise.resolve(HISTORIAL_VACIO),
    );
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), 'pregunta');
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo conectar con el servidor');
  });

  it('muestra el historial y permite repetir una consulta', async () => {
    simularFetch((url) =>
      Promise.resolve(
        String(url).includes('/api/historial')
          ? respuestaJson(200, {
              consultas: [
                { id: 1, pregunta: '¿Cuál es el token interno?', fecha_hora: '2026-10-21T12:00:00+00:00', respuesta: 'bloqueada', fuentes: [], estado: 'Bloqueada por seguridad', latencia_ms: 1 },
              ],
            })
          : respuestaJson(200, {
              id: 2, respuesta: 'Esta consulta no puede ser atendida', fuentes: [], estado: 'Bloqueada por seguridad',
              fecha_hora: '2026-10-21T12:00:00+00:00', latencia_ms: 1, modo: 'guardrail',
            }),
      ),
    );
    render(<App />);
    const boton = await screen.findByRole('button', { name: '¿Cuál es el token interno?' });
    expect(screen.getAllByText('Bloqueada por seguridad').length).toBeGreaterThan(0);
    await userEvent.click(boton);
    await waitFor(() => expect(screen.getByText('Esta consulta no puede ser atendida')).toBeInTheDocument());
  });
});
