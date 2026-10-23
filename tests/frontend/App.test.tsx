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

const HISTORIAL_VACIO = respuestaJson(200, { consultas: [] });

function simularFetch(resolver: (url: string, init?: RequestInit) => Promise<Respuesta>) {
  const mock = vi.fn((url: string, init?: RequestInit) => resolver(url, init));
  vi.stubGlobal('fetch', mock);
  return mock;
}

describe('App', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('muestra el formulario de consulta, sin logo de marca', async () => {
    const fetchMock = simularFetch(async () => HISTORIAL_VACIO);
    render(<App />);
    expect(screen.queryByRole('img', { name: 'Banco W' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Pregunta')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Consultar' })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled()); // deja terminar las cargas iniciales (sin aviso act)
  });

  it('usa el límite de longitud que informa el backend (RF-U13)', async () => {
    const fetchMock = simularFetch(async (url) =>
      String(url).includes('/api/salud') ? respuestaJson(200, { estado: 'ok', max_longitud_pregunta: 50 }) : HISTORIAL_VACIO,
    );
    render(<App />);
    expect(await screen.findByText('0 / 50')).toBeInTheDocument();
    const campo = screen.getByLabelText('Pregunta');
    await userEvent.click(campo);
    await userEvent.paste('a'.repeat(51));
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La pregunta supera el máximo de 50 caracteres.');
    expect(fetchMock.mock.calls.filter(([u]) => String(u).includes('/api/consultar'))).toHaveLength(0);
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
    // Mensaje amigable con las especialidades (la frase canónica del backend se conserva intacta arriba).
    const ayuda = screen.getByRole('note', { name: 'Especialidades del asistente' });
    expect(ayuda).toHaveTextContent('Puedo ayudarte con créditos, microseguros, procedimientos operativos y políticas internas');
    expect(ayuda).not.toHaveTextContent('Soy un asistente'); // tono directo, sin hablar de sí mismo
    // Las sugerencias se pulsan y quedan en la caja de texto, listas para enviar.
    const sugerencia = within(ayuda).getByRole('button', { name: '¿Cuál es el plazo máximo del Crédito Agro Crece?' });
    await userEvent.click(sugerencia);
    expect(screen.getByLabelText('Pregunta')).toHaveValue('¿Cuál es el plazo máximo del Crédito Agro Crece?');
  });

  it('no muestra las especialidades cuando la respuesta es exitosa', async () => {
    simularFetch((url) =>
      Promise.resolve(
        String(url).includes('/api/consultar')
          ? respuestaJson(200, {
              id: 9, respuesta: 'Monto máximo: $50.000.000', fuentes: [],
              estado: 'Exitosa', fecha_hora: '2026-10-21T12:00:00+00:00', latencia_ms: 1, modo: 'extractivo',
            })
          : HISTORIAL_VACIO,
      ),
    );
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), '¿Monto máximo?');
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByText('Monto máximo: $50.000.000')).toBeInTheDocument();
    expect(screen.queryByRole('note', { name: 'Especialidades del asistente' })).not.toBeInTheDocument();
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

  it('rechaza una pregunta de más de 1000 caracteres sin llamar al backend', async () => {
    const fetchMock = simularFetch(async () => HISTORIAL_VACIO);
    render(<App />);
    const campo = screen.getByLabelText('Pregunta');
    await userEvent.click(campo);
    await userEvent.paste('a'.repeat(1001));
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La pregunta supera el máximo de 1000 caracteres.');
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/consultar'))).toHaveLength(0);
  });

  it('muestra caracteres especiales como texto literal, sin interpretarlos como HTML', async () => {
    const especial = '<script>alert("x")</script> <b>negrita</b> 🚀 ñ & "comillas"';
    simularFetch((url) =>
      Promise.resolve(
        String(url).includes('/api/consultar')
          ? respuestaJson(200, {
              id: 10, respuesta: especial, fuentes: [], estado: 'Exitosa',
              fecha_hora: '2026-10-22T10:00:00+00:00', latencia_ms: 1, modo: 'extractivo',
            })
          : HISTORIAL_VACIO,
      ),
    );
    const { container } = render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), 'pregunta');
    await userEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByText(especial)).toBeInTheDocument();
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('.respuesta b')).toBeNull();
  });

  it('muestra el intercambio como chat: pregunta del asesor y respuesta del asistente', async () => {
    simularFetch((url) =>
      Promise.resolve(
        String(url).includes('/api/consultar')
          ? respuestaJson(200, {
              id: 11, respuesta: 'Monto máximo: $50.000.000', estado: 'Exitosa', latencia_ms: 1, modo: 'extractivo',
              fecha_hora: '2026-10-22T10:00:00+00:00',
              fuentes: [{ documento: 'Productos de Crédito', archivo: 'Productos de Crédito.md', seccion: 'Condiciones', puntaje: 1 }],
            })
          : HISTORIAL_VACIO,
      ),
    );
    render(<App />);
    expect(screen.getByText(/Puedo ayudarte con/)).toBeInTheDocument(); // guía inicial con la conversación vacía
    const campo = screen.getByLabelText('Pregunta');
    await userEvent.type(campo, '¿Monto máximo del Impulso?{Enter}'); // Enter envía
    const conversacion = screen.getByRole('log', { name: 'Conversación' });
    const asesor = await within(conversacion).findByRole('article', { name: 'Mensaje del asesor' });
    expect(asesor).toHaveTextContent('¿Monto máximo del Impulso?');
    const asistente = await within(conversacion).findByRole('article', { name: 'Respuesta del asistente' });
    expect(asistente).toHaveTextContent('Monto máximo: $50.000.000');
    expect(asistente).toHaveTextContent('Exitosa');
    expect(asistente).toHaveTextContent('Productos de Crédito.md');
    expect(campo).toHaveValue(''); // lista para la siguiente pregunta
    expect(screen.queryByText(/Puedo ayudarte con/)).not.toBeInTheDocument();
  });

  it('Shift+Enter agrega un salto de línea sin enviar', async () => {
    const fetchMock = simularFetch(async () => HISTORIAL_VACIO);
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), 'línea 1{Shift>}{Enter}{/Shift}línea 2');
    expect(screen.getByLabelText('Pregunta')).toHaveValue('línea 1\nlínea 2');
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/consultar'))).toHaveLength(0);
  });
});
