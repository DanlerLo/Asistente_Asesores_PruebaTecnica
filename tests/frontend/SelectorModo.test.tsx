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

const CUOTA = {
  solicitudes_limite: 1000,
  solicitudes_restantes: 997,
  solicitudes_reinicio_s: 179.56,
  tokens_limite: 8000,
  tokens_restantes: 7500,
  tokens_reinicio_s: 7.66,
  actualizado: '2026-10-22T10:00:00+00:00',
};

const estadoGroq = (activo: boolean, cuota: typeof CUOTA | null = CUOTA) => ({
  proveedor: 'groq',
  modelo: 'openai/gpt-oss-20b',
  activo,
  modo: activo ? 'groq' : 'extractivo',
  llamadas: 3,
  cuota,
});

const CONEXION = 'Modo conexión (Groq)';
const SIN_CONEXION = 'Modo sin conexión';

/** Simula el backend: /api/llm devuelve `estado` (PUT lo cambia); el resto, historial vacío. */
function simularBackend(estadoInicial: unknown, opciones: { llmFalla?: boolean } = {}) {
  let estado = estadoInicial as ReturnType<typeof estadoGroq>;
  const mock = vi.fn(async (url: string, init?: RequestInit): Promise<Respuesta> => {
    if (String(url).includes('/api/llm')) {
      if (opciones.llmFalla) return respuestaJson(500, { error: 'falla', codigo: 'ERROR_INTERNO' });
      if (init?.method === 'PUT') {
        const { activo } = JSON.parse(String(init.body));
        estado = { ...estado, activo, modo: activo ? 'groq' : 'extractivo' };
      }
      return respuestaJson(200, estado);
    }
    return respuestaJson(200, { consultas: [] });
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

const presionado = (nombre: string) => screen.getByRole('button', { name: nombre }).getAttribute('aria-pressed');

describe('Selector de modo (conexión / sin conexión)', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('muestra el modo conexión activo y las llamadas restantes', async () => {
    simularBackend(estadoGroq(true));
    render(<App />);
    expect(await screen.findByText('Quedan 997 de 1000 llamadas hoy')).toBeInTheDocument();
    expect(presionado(CONEXION)).toBe('true');
    expect(presionado(SIN_CONEXION)).toBe('false');
  });

  it('indica que la cuota se conocerá después de la primera consulta', async () => {
    simularBackend(estadoGroq(true, null));
    render(<App />);
    expect(await screen.findByText(/se conocerá después de la primera consulta/)).toBeInTheDocument();
  });

  it('avisa cuando queda menos del 10 % de la cuota', async () => {
    simularBackend(estadoGroq(true, { ...CUOTA, solicitudes_restantes: 40 }));
    render(<App />);
    expect(await screen.findByText(/Quedan pocas llamadas/)).toBeInTheDocument();
  });

  it('formatea el tiempo de recarga sin "60 min"', async () => {
    simularBackend(estadoGroq(true, { ...CUOTA, solicitudes_reinicio_s: 7190 }));
    render(<App />);
    expect(await screen.findByText(/recarga en ~2 h$/)).toBeInTheDocument();
  });

  it('al pasar a modo sin conexión muestra un pop-up explicativo y permite volver', async () => {
    const fetchMock = simularBackend(estadoGroq(true));
    render(<App />);
    await userEvent.click(await screen.findByRole('button', { name: SIN_CONEXION }));

    const popup = await screen.findByRole('dialog', { name: SIN_CONEXION });
    expect(popup).toHaveTextContent('solo con la documentación oficial');
    expect(popup).toHaveTextContent('Groq');
    expect(presionado(SIN_CONEXION)).toBe('true');
    const put = fetchMock.mock.calls.find(([url, init]) => String(url).includes('/api/llm') && init?.method === 'PUT');
    expect(JSON.parse(String(put![1]?.body))).toEqual({ activo: false });

    await userEvent.click(within(popup).getByRole('button', { name: 'Entendido' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: CONEXION }));
    await waitFor(() => expect(presionado(CONEXION)).toBe('true'));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(); // el pop-up solo explica el modo sin conexión
  });

  it('sin proveedor configurado muestra «Modo sin conexión» sin botones', async () => {
    simularBackend({ proveedor: null, modelo: null, activo: false, modo: 'extractivo', llamadas: 0, cuota: null });
    render(<App />);
    expect(await screen.findByText(SIN_CONEXION)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Modo/ })).not.toBeInTheDocument();
  });

  it('si /api/llm falla, el selector no se muestra y la aplicación sigue funcionando', async () => {
    simularBackend(null, { llmFalla: true });
    render(<App />);
    await waitFor(() => expect(screen.getByLabelText('Pregunta')).toBeInTheDocument());
    expect(screen.queryByRole('group', { name: 'Modo del asistente' })).not.toBeInTheDocument();
  });

  it('una respuesta vieja de GET /api/llm no pisa el modo recién cambiado', async () => {
    let estado = estadoGroq(true);
    let soltarGetViejo: () => void = () => {};
    let getsLlm = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit): Promise<Respuesta> => {
        if (String(url).includes('/api/llm')) {
          if (init?.method === 'PUT') {
            estado = { ...estado, activo: JSON.parse(String(init.body)).activo, modo: 'extractivo' };
            return respuestaJson(200, estado);
          }
          getsLlm += 1;
          if (getsLlm === 2) {
            const viejo = { ...estado }; // foto del estado ANTES del PUT (activo)
            return new Promise<Respuesta>((resolve) => {
              soltarGetViejo = () => resolve(respuestaJson(200, viejo));
            });
          }
          return respuestaJson(200, estado);
        }
        if (String(url).includes('/api/consultar')) {
          return respuestaJson(200, {
            id: 1, respuesta: 'r', fuentes: [], estado: 'Exitosa', fecha_hora: '2026-10-22T10:00:00+00:00', latencia_ms: 1, modo: 'groq',
          });
        }
        return respuestaJson(200, { consultas: [] });
      }),
    );
    render(<App />);
    await screen.findByRole('button', { name: CONEXION });
    await userEvent.type(screen.getByLabelText('Pregunta'), 'pregunta');
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    await waitFor(() => expect(getsLlm).toBe(2)); // GET posterior a la consulta, todavía sin respuesta
    await userEvent.click(screen.getByRole('button', { name: SIN_CONEXION }));
    await waitFor(() => expect(presionado(SIN_CONEXION)).toBe('true'));
    soltarGetViejo();
    await new Promise((r) => setTimeout(r, 20));
    expect(presionado(SIN_CONEXION)).toBe('true');
  });

  it('al reintentar con éxito se borra el error anterior de cambio de modo', async () => {
    let fallar = true;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit): Promise<Respuesta> => {
        if (String(url).includes('/api/llm')) {
          if (init?.method === 'PUT') {
            if (fallar) {
              fallar = false;
              return respuestaJson(500, { error: 'Ocurrió un error interno.', codigo: 'ERROR_INTERNO' });
            }
            return respuestaJson(200, estadoGroq(false));
          }
          return respuestaJson(200, estadoGroq(true));
        }
        return respuestaJson(200, { consultas: [] });
      }),
    );
    render(<App />);
    await userEvent.click(await screen.findByRole('button', { name: SIN_CONEXION }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ocurrió un error interno.');
    await userEvent.click(screen.getByRole('button', { name: SIN_CONEXION }));
    await waitFor(() => expect(presionado(SIN_CONEXION)).toBe('true'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
