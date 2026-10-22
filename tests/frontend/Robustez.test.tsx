import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/frontend/src/App';
import { LimiteErrores } from '../../src/frontend/src/components/LimiteErrores';

type Respuesta = { ok: boolean; status: number; json: () => Promise<unknown> };
const respuestaJson = (status: number, cuerpo: unknown): Respuesta => ({
  ok: status >= 200 && status < 300,
  status,
  json: () => Promise.resolve(cuerpo),
});

describe('Robustez de la interfaz (RF-U12)', () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.unstubAllGlobals());

  it('una respuesta inválida muestra un error y no deja «Procesando…» colgado', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        String(url).includes('/api/consultar') ? respuestaJson(200, { respuesta: 'r', fuentes: null }) : respuestaJson(200, { consultas: [] }),
      ),
    );
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), 'pregunta{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent('La respuesta del servidor no es válida');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Pregunta')).toHaveValue('pregunta');
  });

  it('un error de pintado no deja la página en blanco', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const Roto = () => {
      throw new Error('fallo al pintar');
    };
    render(
      <LimiteErrores>
        <Roto />
      </LimiteErrores>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Algo salió mal al mostrar la respuesta');
  });

  it('mientras se procesa, el historial no lanza otra consulta ni pisa el borrador', async () => {
    let consultas = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (String(url).includes('/api/historial')) {
          return Promise.resolve(
            respuestaJson(200, {
              consultas: [{ id: 1, pregunta: 'pregunta del historial', fecha_hora: '2026-10-22T10:00:00+00:00', respuesta: 'r', fuentes: [], estado: 'Exitosa', latencia_ms: 1 }],
            }),
          );
        }
        if (String(url).includes('/api/consultar')) {
          consultas += 1;
          return new Promise<Respuesta>(() => {}); // queda en curso
        }
        return Promise.resolve(respuestaJson(200, { consultas: [] }));
      }),
    );
    render(<App />);
    const historial = await screen.findByRole('button', { name: 'pregunta del historial' });
    await userEvent.type(screen.getByLabelText('Pregunta'), 'primera{Enter}');
    await waitFor(() => expect(consultas).toBe(1));
    expect(historial).toBeDisabled();
    await userEvent.click(historial);
    expect(consultas).toBe(1);
  });

  it('al terminar una consulta el foco vuelve a la caja de texto', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        String(url).includes('/api/consultar')
          ? respuestaJson(200, { id: 1, respuesta: 'r', fuentes: [], estado: 'Exitosa', fecha_hora: '2026-10-22T10:00:00+00:00', latencia_ms: 1, modo: 'extractivo' })
          : respuestaJson(200, { consultas: [] }),
      ),
    );
    render(<App />);
    await userEvent.type(screen.getByLabelText('Pregunta'), 'pregunta{Enter}');
    await screen.findByRole('article', { name: 'Respuesta del asistente' });
    await waitFor(() => expect(screen.getByLabelText('Pregunta')).toHaveFocus());
  });
});
